"""Genera respuestas para los casos de evaluación, calcula sus métricas y las guarda.

- Guarda después de cada respuesta: si se corta, al volver a ejecutarlo retoma donde quedó.
- Registra la coincidencia cruda y la procesada (antes y después del pipeline, Bloque 15).
Uso desde la raíz del repo:  python -m src.evaluar_salidas
"""
import json
import time
from pathlib import Path

from src.casos_evaluacion import CASOS
from src.cliente import consultar_modelo
from src.consumir_gemini import MODELO
from src.pipeline_texto import calcular_metricas, coincidencia_simple, procesar_texto, resumir_metricas

ARCHIVO_RESULTADOS = Path("docs/resultados_metricas.json")
PAUSA_SEGUNDOS = 5  # flash-lite permite 15 por minuto; 5 s deja margen
SISTEMA_EVALUACION = (
    "Eres un asistente de seguridad para faenas mineras en Chile. "
    "Responde siempre en español, de forma directa, en una o dos frases."
)


def cargar_resultados() -> list[dict]:
    """Lee los resultados ya guardados, si existen."""
    if ARCHIVO_RESULTADOS.exists():
        return json.loads(ARCHIVO_RESULTADOS.read_text(encoding="utf-8"))
    return []


def guardar_resultados(resultados: list[dict]) -> None:
    ARCHIVO_RESULTADOS.write_text(json.dumps(resultados, indent=2, ensure_ascii=False), encoding="utf-8")


def evaluar_caso(caso: dict) -> dict:
    """Consulta al modelo y calcula las métricas de un caso."""
    respuesta = consultar_modelo(caso["pregunta"], system_instruction=SISTEMA_EVALUACION)
    metricas = calcular_metricas(caso["referencia"], respuesta)
    return {
        "pregunta": caso["pregunta"],
        "referencia": caso["referencia"],
        "respuesta": respuesta,
        "modelo": MODELO,
        "coincidencia_cruda": coincidencia_simple(caso["referencia"].split(), respuesta.split()),
        "coincidencia_procesada": coincidencia_simple(procesar_texto(caso["referencia"]), procesar_texto(respuesta)),
        **metricas,
    }


def main() -> None:
    resultados = cargar_resultados()
    ya_evaluadas = {r["pregunta"] for r in resultados}
    pendientes = [c for c in CASOS if c["pregunta"] not in ya_evaluadas]
    print(f"{len(ya_evaluadas)} casos ya evaluados, {len(pendientes)} pendientes. Modelo: {MODELO}\n")

    for i, caso in enumerate(pendientes, start=1):
        try:
            resultado = evaluar_caso(caso)
        except RuntimeError as error:
            print(f"[{i}] Se omite (se reintentará en la próxima ejecución): {error}")
            continue
        resultados.append(resultado)
        guardar_resultados(resultados)
        print(f"[{i}] F1={resultado['f1']:.2f} | cruda {resultado['coincidencia_cruda']:.0%} -> "
              f"procesada {resultado['coincidencia_procesada']:.0%} | {caso['pregunta']}")
        time.sleep(PAUSA_SEGUNDOS)

    resumen = resumir_metricas(resultados)
    print(f"\nResumen de {len(resultados)} casos: " + ", ".join(f"{k}={v:.2f}" for k, v in resumen.items()))
    print("\nLos 3 casos con F1 más bajo:")
    for r in sorted(resultados, key=lambda r: r["f1"])[:3]:
        print(f"  {r['f1']:.2f}  {r['pregunta']}")


if __name__ == "__main__":
    main()