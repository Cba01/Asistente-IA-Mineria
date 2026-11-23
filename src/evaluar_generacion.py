"""Evaluación de la GENERACIÓN para comparar versiones del prompt (preparación del Gate 2).

El Bloque 27 midió la recuperación (recall 0,964). Esto mide lo que pasa después:
con el mismo contexto recuperado, ¿la respuesta usa bien lo que recibió?

Por cada versión del prompt y cada una de las 15 preguntas del Bloque 27 cuenta:
- falso_no_se:        dijo "no tengo información" teniendo el chunk relevante en el contexto,
- sin_citas:          respondió algo pero sin ningún [n],
- citas_invalidas:    citó un número que no estaba en el contexto,
- faltante_inventado: comentó que "falta" algo (palabra que no aparece en el contexto),
- rechazo_correcto:   en la pregunta que el corpus no cubre, dijo que no tiene información.

La recuperación se hace UNA vez por pregunta y se reutiliza para todas las versiones:
así la única diferencia entre versiones es el prompt.

Resultados en docs/evaluacion_generacion.json (por huella), que el grafo de aprobación muestra.

Uso desde la raíz del repo:
    python -m src.evaluar_generacion              # las 3 últimas versiones registradas
    python -m src.evaluar_generacion --ultimas 2
Llamadas a la API: 15 de embeddings + 15 de generación por versión.
"""
import argparse
import json
import re
import time
from datetime import date
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from src.evaluacion_recuperacion import CASOS_EVALUACION
from src.indexar_corpus import RAIZ
from src.recuperacion import SIN_INFORMACION, extraer_citas, formatear_contexto, texto_de_salida
from src.registro_prompts import ARCHIVO_REGISTRO, RegistroDePrompts

ARCHIVO_EVALUACION = RAIZ / "docs" / "evaluacion_generacion.json"
MARCA_PLANTILLA = "\n\n<contexto>\n{contexto}"


def mensajes_para(texto_version: str, pregunta: str, chunks) -> list:
    """Arma los mensajes tal como los arma esa versión del prompt.
    Desde la v3 hay un mensaje de sistema y una plantilla con <contexto>; antes era un solo texto."""
    contexto, _ = formatear_contexto(chunks)
    if MARCA_PLANTILLA in texto_version:
        sistema, plantilla = texto_version.split("\n\n<contexto>", 1)
        humano = ("<contexto>" + plantilla).format(contexto=contexto, pregunta=pregunta)
        return [SystemMessage(content=sistema), HumanMessage(content=humano)]
    return [HumanMessage(content=texto_version.format(contexto=contexto, pregunta=pregunta))]


def clasificar(caso: dict, chunks, respuesta: str) -> dict:
    """Clasifica una respuesta. No juzga si es correcta: cuenta fallas objetivas."""
    _, citas = formatear_contexto(chunks)
    validas, invalidas = extraer_citas(respuesta, citas)
    sin_info = SIN_INFORMACION in respuesta
    relevante_en_contexto = bool(caso["ids_relevantes"] & {c.id for c in chunks})
    texto_contexto = " ".join(c.page_content.lower() for c in chunks)
    faltante = bool(re.search(r"\bfalta\b", respuesta.lower())) and not re.search(r"\bfalta\b", texto_contexto)
    return {
        "pregunta": caso["pregunta"],
        "tiene_respuesta": bool(caso["ids_relevantes"]),
        "falso_no_se": relevante_en_contexto and sin_info,
        "sin_citas": not sin_info and not validas,
        "citas_invalidas": len(invalidas),
        "faltante_inventado": faltante,
        "rechazo_correcto": (not caso["ids_relevantes"]) and sin_info,
    }


def resumir(clasificaciones: list[dict]) -> dict:
    con_respuesta = [c for c in clasificaciones if c["tiene_respuesta"]]
    sin_respuesta = [c for c in clasificaciones if not c["tiene_respuesta"]]
    return {
        "casos": len(clasificaciones),
        "falso_no_se": sum(c["falso_no_se"] for c in con_respuesta),
        "sin_citas": sum(c["sin_citas"] for c in clasificaciones),
        "citas_invalidas": sum(c["citas_invalidas"] for c in clasificaciones),
        "faltante_inventado": sum(c["faltante_inventado"] for c in clasificaciones),
        "rechazo_correcto": f"{sum(c['rechazo_correcto'] for c in sin_respuesta)}/{len(sin_respuesta)}",
    }


def evaluar_version(texto_version, contextos: dict, modelo, casos=CASOS_EVALUACION, pausa=4.5):
    clasificaciones = []
    for i, caso in enumerate(casos):
        if i and pausa:
            time.sleep(pausa)  # plan gratuito: 15 peticiones por minuto
        chunks = contextos[caso["pregunta"]]
        salida = modelo.invoke(mensajes_para(texto_version, caso["pregunta"], chunks))
        clasificaciones.append({**clasificar(caso, chunks, texto_de_salida(salida.content)),
                                "respuesta": texto_de_salida(salida.content)})
    return resumir(clasificaciones), clasificaciones


def guardar(resultados: dict, archivo: Path = ARCHIVO_EVALUACION) -> None:
    previos = json.loads(Path(archivo).read_text(encoding="utf-8")) if Path(archivo).exists() else {}
    previos.update(resultados)
    Path(archivo).write_text(json.dumps(previos, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ultimas", type=int, default=3, help="Cuántas versiones recientes evaluar.")
    args = parser.parse_args()

    from src.cadena_tres_pasos import crear_modelo
    from src.recuperacion import K, crear_retriever

    versiones = RegistroDePrompts(ARCHIVO_REGISTRO).historial("prompt_rag")[-args.ultimas:]
    retriever = crear_retriever(K)
    print(f"Recuperando contexto para {len(CASOS_EVALUACION)} preguntas (una sola vez)...")
    contextos = {c["pregunta"]: retriever.invoke(c["pregunta"]) for c in CASOS_EVALUACION}

    modelo = crear_modelo()
    resultados = {}
    for v in versiones:
        print(f"\nEvaluando v{v['version']} ({v['huella']})...")
        resumen, detalle = evaluar_version(v["texto"], contextos, modelo)
        resultados[v["huella"]] = {"version": v["version"], "fecha": str(date.today()),
                                   "modelo": getattr(modelo, "model", None), "resumen": resumen,
                                   "detalle": detalle}
        print("  ", resumen)
        time.sleep(4.5)

    guardar(resultados)
    print(f"\n{'versión':<8} {'falso no sé':>11} {'sin citas':>9} {'citas inv.':>10} "
          f"{'falta inv.':>10} {'rechazo ok':>10}")
    for huella, r in resultados.items():
        s = r["resumen"]
        print(f"v{r['version']:<7} {s['falso_no_se']:>11} {s['sin_citas']:>9} {s['citas_invalidas']:>10} "
              f"{s['faltante_inventado']:>10} {s['rechazo_correcto']:>10}")
    print(f"\nDetalle por pregunta en {ARCHIVO_EVALUACION.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
