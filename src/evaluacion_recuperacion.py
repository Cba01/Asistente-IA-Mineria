"""Evaluación de la recuperación con precisión y recall (U2.5, Bloque 27).

Mide si la búsqueda trae los chunks que de verdad responden cada pregunta,
comparando contra etiquetas puestas a mano ANTES de ver los resultados.

- precisión@k: de los k chunks recuperados, qué fracción es relevante.
- recall@k:    de los chunks relevantes, qué fracción se recuperó.

Cada corrida se agrega al final de docs/resultados_evaluacion.txt (no se
sobrescribe), para poder comparar después de cambiar el chunking, el k o el corpus.

Uso desde la raíz del repo:  python -m src.evaluacion_recuperacion
Hace 1 llamada de embeddings por pregunta (15 en total). No usa el modelo de texto.
"""
import time
from datetime import datetime
from pathlib import Path

from src.indexar_corpus import (CHUNK_OVERLAP, CHUNK_SIZE, RAIZ, cargar_corpus,
                                partir_en_chunks)

ARCHIVO_RESULTADOS = RAIZ / "docs" / "resultados_evaluacion.txt"
VALORES_K = (3, 4, 5)
K_PRINCIPAL = 3  # el K que usa src/recuperacion.py

# Etiquetado a mano leyendo el corpus, antes de correr el retriever.
# Criterio: un chunk es relevante si, solo, alcanza para responder la pregunta
# o una parte central de ella. No basta con que comparta palabras.
# Las preguntas usan a propósito palabras distintas a las del documento.
CASOS_EVALUACION = [
    {"pregunta": "¿A partir de qué altura se considera trabajo en altura?",
     "ids_relevantes": {"pts_gen_007_altura_0"}},
    {"pregunta": "¿Por qué cada trabajador tiene que poner su propio candado?",
     "ids_relevantes": {"pts_gen_002_bloqueo_2"}},
    {"pregunta": "¿Sirve tirar el pull cord para dejar la correa bloqueada?",
     "ids_relevantes": {"pts_mec_014_correas_5", "pts_gen_002_bloqueo_6"}},
    {"pregunta": "Un compañero se fue a su casa y dejó su candado puesto, ¿quién lo puede sacar?",
     "ids_relevantes": {"pts_gen_002_bloqueo_5"}},
    {"pregunta": "¿Cómo compruebo que el equipo quedó realmente sin energía?",
     "ids_relevantes": {"pts_gen_002_bloqueo_4", "pts_mec_014_correas_3"}},
    {"pregunta": "¿Qué peligros tiene cambiar un rodillo de la correa?",
     "ids_relevantes": {"pts_mec_014_correas_2"}},
    {"pregunta": "¿Qué tengo que revisar en el arnés antes de ponérmelo?",
     "ids_relevantes": {"pts_gen_007_altura_3"}},
    {"pregunta": "¿Qué debe hacer el vigía si alguien se desmaya dentro del estanque?",
     "ids_relevantes": {"pts_gen_010_espacios_confinados_5"}},
    {"pregunta": "¿Cuántas personas forman el comité paritario?",
     "ids_relevantes": {"ley_16744_accidentes_trabajo_3"}},
    {"pregunta": "Si me accidento camino al trabajo, ¿me cubre el seguro?",
     "ids_relevantes": {"ley_16744_accidentes_trabajo_1"}},
    {"pregunta": "¿La empresa me puede cobrar los zapatos de seguridad?",
     "ids_relevantes": {"ds594_condiciones_sanitarias_2"}},
    {"pregunta": "¿Qué enfermedad puede dar respirar polvo de sílice?",
     "ids_relevantes": {"ds594_condiciones_sanitarias_4"}},
    {"pregunta": "¿Qué institución fiscaliza la seguridad en las minas?",
     "ids_relevantes": {"ds132_reglamento_seguridad_minera_1"}},
    {"pregunta": "¿Desde cuántos trabajadores es obligatorio tener un departamento de prevención?",
     "ids_relevantes": {"ds40_prevencion_riesgos_2"}},
    # Pregunta que el corpus no cubre: sin ids relevantes, su recall no se define
    # y queda fuera del promedio de recall.
    {"pregunta": "¿Cuántos días de vacaciones le corresponden a un trabajador minero?",
     "ids_relevantes": set()},
]


# ---------- Métricas ----------

def precision_at_k(ids_recuperados, ids_relevantes) -> float:
    """Fracción de los recuperados que es relevante (0.0 si no se recuperó nada)."""
    if not ids_recuperados:
        return 0.0
    acertados = [i for i in ids_recuperados if i in ids_relevantes]
    return len(acertados) / len(ids_recuperados)


def recall_at_k(ids_recuperados, ids_relevantes) -> float | None:
    """Fracción de los relevantes que se recuperó (None si el caso no tiene relevantes)."""
    if not ids_relevantes:
        return None
    acertados = [i for i in ids_recuperados if i in ids_relevantes]
    return len(acertados) / len(ids_relevantes)


def promediar(valores) -> float:
    """Promedio que ignora los None y no divide por cero."""
    validos = [v for v in valores if v is not None]
    return sum(validos) / len(validos) if validos else 0.0


def f1(precision: float, recall: float) -> float:
    return 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)


# ---------- Evaluación ----------

def validar_etiquetas(casos, ids_existentes) -> list[str]:
    """Detecta etiquetas mal escritas: un id que no existe nunca va a coincidir
    y bajaría las métricas sin que sea culpa del retriever. No usa la API."""
    ids_existentes = set(ids_existentes)
    return [f"'{i}' (pregunta: {c['pregunta']})"
            for c in casos for i in c["ids_relevantes"] if i not in ids_existentes]


def recuperar_rankings(casos, retriever, pausa=0.5) -> dict[str, list[str]]:
    """Recupera una sola vez, con el k más grande, para cada pregunta.
    Los primeros k de ese ranking son exactamente lo que devolvería un retriever
    con ese k, así que con una llamada por pregunta se evalúan k=3, 4 y 5."""
    rankings = {}
    for i, caso in enumerate(casos):
        if i and pausa:
            time.sleep(pausa)
        rankings[caso["pregunta"]] = [c.id for c in retriever.invoke(caso["pregunta"])]
    return rankings


def evaluar(casos, rankings, k: int):
    """Calcula precisión y recall por caso con los primeros k del ranking, y sus promedios."""
    resultados = []
    for caso in casos:
        recuperados = rankings[caso["pregunta"]][:k]
        resultados.append({
            "pregunta": caso["pregunta"],
            "recuperados": recuperados,
            "precision": precision_at_k(recuperados, caso["ids_relevantes"]),
            "recall": recall_at_k(recuperados, caso["ids_relevantes"]),
        })
    p = promediar(r["precision"] for r in resultados)
    r = promediar(x["recall"] for x in resultados)
    return resultados, p, r


def formatear_corrida(casos, rankings, fecha: str) -> str:
    """Texto de una corrida: detalle por pregunta con K_PRINCIPAL y resumen para cada k."""
    lineas = [
        f"Fecha: {fecha}",
        f"Configuracion: k={K_PRINCIPAL}, chunk_size={CHUNK_SIZE}, chunk_overlap={CHUNK_OVERLAP}, "
        f"casos={len(casos)}",
        "",
        "prec  recall  pregunta",
    ]
    resultados, _, _ = evaluar(casos, rankings, K_PRINCIPAL)
    for r in resultados:
        recall_txt = " n/a" if r["recall"] is None else f"{r['recall']:.2f}"
        lineas.append(f"{r['precision']:.2f}  {recall_txt}    {r['pregunta']}")
        if r["recall"] is not None and r["recall"] < 1:
            lineas.append(f"            recuperados: {', '.join(r['recuperados'])}")

    lineas += ["", "k   precision  recall  f1"]
    for k in VALORES_K:
        _, p, r = evaluar(casos, rankings, k)
        lineas.append(f"{k}   {p:.3f}      {r:.3f}   {f1(p, r):.3f}")
    return "\n".join(lineas)


def main() -> None:
    _, ids_existentes = partir_en_chunks(cargar_corpus())
    errores = validar_etiquetas(CASOS_EVALUACION, ids_existentes)
    if errores:
        print("Hay etiquetas con ids que no existen en el índice:")
        print("\n".join(" - " + e for e in errores))
        raise SystemExit(1)

    from src.recuperacion import crear_retriever
    rankings = recuperar_rankings(CASOS_EVALUACION, crear_retriever(k=max(VALORES_K)))

    texto = formatear_corrida(CASOS_EVALUACION, rankings, datetime.now().strftime("%Y-%m-%d %H:%M"))
    print(texto)

    ARCHIVO_RESULTADOS.parent.mkdir(exist_ok=True)
    with open(ARCHIVO_RESULTADOS, "a", encoding="utf-8") as archivo:
        archivo.write(texto + "\n\n" + "=" * 60 + "\n\n")
    print(f"\nCorrida agregada a {ARCHIVO_RESULTADOS.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
