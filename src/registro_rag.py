"""Latencia y costo del flujo RAG completo (U2.5, Bloque 28 · actividad core).

Corre consultas RAG reales y mide cada etapa por separado:
- embed_pregunta:     calcular el embedding de la pregunta (llamada por red),
- busqueda_vectorial: buscar los k chunks más cercanos en Chroma (local),
- generacion:         el modelo responde con el contexto recuperado (llamada por red).

Los tokens se toman de usage_metadata de la respuesta real del modelo (no se
estiman por caracteres). Cada consulta se agrega como una línea JSON al final
de registros_latencia_costo.jsonl.

Uso desde la raíz del repo:
    python -m src.registro_rag            # corre la batería de consultas definida abajo
    python -m src.registro_rag --resumen  # solo muestra los registros ya guardados
"""
import argparse
import json
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from src.indexar_corpus import RAIZ
from src.recuperacion import (K, PROMPT_RAG, SIN_INFORMACION, extraer_citas,
                              formatear_contexto, texto_de_salida)

load_dotenv()

ARCHIVO_REGISTROS = RAIZ / "registros_latencia_costo.jsonl"

# USD por millón de tokens (entrada, salida), los mismos de src/cliente.py.
# Revisar la tarifa vigente en la documentación oficial de Gemini antes de usarlos.
PRECIOS_POR_MILLON = {
    "gemini-3.5-flash-lite": (0.30, 2.50),
    "gemini-3.6-flash": (0.75, 3.75),
}


@contextmanager
def medir(tiempos: dict, etapa: str):
    """Mide la duración del bloque 'with' y la guarda en tiempos[etapa] (segundos)."""
    inicio = time.perf_counter()
    try:
        yield
    finally:
        tiempos[etapa] = time.perf_counter() - inicio


def calcular_costo(tokens: dict | None, modelo: str | None) -> float | None:
    """Costo en USD de la generación. None si no hay tokens o no se conoce la tarifa."""
    if not tokens or not modelo:
        return None
    precios = PRECIOS_POR_MILLON.get(modelo.removeprefix("models/"))
    if precios is None:
        return None
    entrada, salida = precios
    return (tokens.get("input_tokens", 0) * entrada + tokens.get("output_tokens", 0) * salida) / 1_000_000


def registrar_consulta(pregunta: str, k: int = K, embeddings=None, vectorstore=None, modelo=None) -> dict:
    """Corre una consulta RAG real midiendo cada etapa. Devuelve el registro (dict).

    Crear los clientes (embeddings, Chroma, modelo) queda FUERA de la medición:
    se hace una vez al iniciar el programa, no en cada consulta.
    """
    if embeddings is None:
        from src.indexar_corpus import crear_embeddings
        embeddings = crear_embeddings()
    if vectorstore is None:
        from src.indexar_corpus import cargar_vectorstore
        vectorstore = cargar_vectorstore(embeddings)
    if modelo is None:
        from src.cadena_tres_pasos import crear_modelo
        modelo = crear_modelo()

    tiempos = {}
    with medir(tiempos, "embed_pregunta"):
        vector = embeddings.embed_query(pregunta)
    with medir(tiempos, "busqueda_vectorial"):
        chunks = vectorstore.similarity_search_by_vector(vector, k=k)

    contexto, citas = formatear_contexto(chunks)
    prompt = PROMPT_RAG.format(contexto=contexto, pregunta=pregunta)

    with medir(tiempos, "generacion"):
        respuesta = modelo.invoke(prompt)

    texto = texto_de_salida(respuesta.content)
    _, citas_invalidas = extraer_citas(texto, citas)
    tokens = dict(respuesta.usage_metadata) if getattr(respuesta, "usage_metadata", None) else None
    nombre_modelo = getattr(modelo, "model", None)

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "pregunta": pregunta,
        "k": k,
        "modelo": nombre_modelo,
        "ids_recuperados": [c.id for c in chunks],
        "caracteres_prompt": len(prompt),
        "tiempos_ms": {etapa: round(s * 1000, 2) for etapa, s in tiempos.items()},
        "tiempo_total_ms": round(sum(tiempos.values()) * 1000, 2),
        "tokens": tokens,
        "costo_usd": calcular_costo(tokens, nombre_modelo),
        "sin_informacion": SIN_INFORMACION in texto,
        "citas_invalidas": citas_invalidas,
    }


def guardar_registro(registro: dict, archivo: Path = ARCHIVO_REGISTROS) -> None:
    with open(archivo, "a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False) + "\n")


def leer_registros(archivo: Path = ARCHIVO_REGISTROS) -> list[dict]:
    if not Path(archivo).exists():
        return []
    with open(archivo, encoding="utf-8") as f:
        return [json.loads(linea) for linea in f if linea.strip()]


def resumir(registros: list[dict]) -> str:
    """Tabla con una fila por consulta: k, tiempos por etapa, tokens de entrada/salida y costo."""
    lineas = [f"{'k':>2} {'embed':>7} {'busq':>6} {'gener':>7} {'total':>7} "
              f"{'tok_in':>6} {'tok_out':>7} {'costo_usd':>10}  pregunta"]
    for r in registros:
        t, tok = r["tiempos_ms"], r.get("tokens") or {}
        costo = f"{r['costo_usd']:.6f}" if r.get("costo_usd") is not None else "n/a"
        lineas.append(
            f"{r['k']:>2} {t.get('embed_pregunta', 0):>7.0f} {t.get('busqueda_vectorial', 0):>6.1f} "
            f"{t.get('generacion', 0):>7.0f} {r['tiempo_total_ms']:>7.0f} "
            f"{tok.get('input_tokens', '-'):>6} {tok.get('output_tokens', '-'):>7} {costo:>10}  "
            f"{r['pregunta'][:45]}")
    return "\n".join(lineas) + "\n(tiempos en ms)"


# Tres preguntas del conjunto de evaluación del Bloque 27 con el K elegido (3),
# y la primera repetida con k=6 para ver cómo cambian los tokens y el costo.
CONSULTAS = [
    ("¿Cómo compruebo que el equipo quedó realmente sin energía?", K),
    ("¿Qué debe hacer el vigía si alguien se desmaya dentro del estanque?", K),
    ("¿La empresa me puede cobrar los zapatos de seguridad?", K),
    ("¿Cómo compruebo que el equipo quedó realmente sin energía?", 6),
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Mide latencia y costo del flujo RAG.")
    parser.add_argument("--resumen", action="store_true", help="Solo muestra los registros guardados.")
    args = parser.parse_args()

    if not args.resumen:
        from src.cadena_tres_pasos import crear_modelo
        from src.indexar_corpus import cargar_vectorstore, crear_embeddings

        # Se crean una sola vez y se reutilizan en todas las consultas.
        embeddings = crear_embeddings()
        vectorstore = cargar_vectorstore(embeddings)
        modelo = crear_modelo()

        for i, (pregunta, k) in enumerate(CONSULTAS):
            if i:
                time.sleep(5)  # pausa para no topar el límite de peticiones por minuto
            registro = registrar_consulta(pregunta, k, embeddings, vectorstore, modelo)
            guardar_registro(registro)
            print(json.dumps(registro, indent=2, ensure_ascii=False))

        print(f"\n{len(CONSULTAS)} registros agregados a {ARCHIVO_REGISTROS.name}\n")

    print(resumir(leer_registros()))


if __name__ == "__main__":
    main()
