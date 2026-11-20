"""Método de decisión de la estrategia de personalización (U2.6, Bloque 30 · core).

Responde las 5 preguntas del curso con evidencia del proyecto, calcula el puntaje
de RAG, fine-tuning completo y PEFT, reporta empates (no los esconde) y hace un
análisis de sensibilidad: qué pasa si cada respuesta hubiera sido la contraria.

Uso desde la raíz del repo:
    python -m src.decision              # puntaje, evidencia y sensibilidad
    python -m src.decision --esqueleto  # además escribe el esqueleto del documento
"""
import argparse

from src.dataset_tuning import EJEMPLOS_RAW
from src.indexar_corpus import RAIZ, cargar_corpus
from src.medir_formato import evaluar_archivo

ARCHIVO_DECISION = RAIZ / "docs" / "decision_personalizacion.md"


def recomendar_estrategia(respuestas: dict) -> tuple[dict, list[str]]:
    """Versión corregida del curso: devuelve TODAS las técnicas empatadas en el máximo."""
    puntos = {"RAG": 0, "Fine-tuning completo": 0, "PEFT": 0}
    if respuestas["informacion_cambia_seguido"]:
        puntos["RAG"] += 3
    if respuestas["problema_de_formato_o_tono"]:
        puntos["PEFT"] += 2
        puntos["Fine-tuning completo"] += 1
    if respuestas["dataset_grande_y_de_calidad"]:
        puntos["Fine-tuning completo"] += 2
        puntos["PEFT"] += 1
    if respuestas["presupuesto_limitado_o_iterar_rapido"]:
        puntos["RAG"] += 2
        puntos["PEFT"] += 1
    if respuestas["necesita_multiples_variantes"]:
        puntos["PEFT"] += 2
    maximo = max(puntos.values())
    return puntos, [t for t, p in puntos.items() if p == maximo]


def reunir_evidencia() -> tuple[dict, dict]:
    """Devuelve (respuestas, evidencia): cada True/False sale de un dato del proyecto."""
    formato = evaluar_archivo()
    n_docs = len(cargar_corpus())
    n_ejemplos = len(EJEMPLOS_RAW)

    evidencia = {
        "informacion_cambia_seguido": (
            f"Los {n_docs} documentos del corpus se crearon o modificaron en los últimos 3 meses "
            "(los 3 PTS se corrigieron el 2026-11-19 para alinearlos con el agente). En una faena real, "
            "los PTS se agregan y revisan por cambios de equipos, incidentes y auditorías."
        ),
        "problema_de_formato_o_tono": (
            f"{formato['con_fallas']} de {formato['total']} respuestas reales de la U2.2 "
            f"({formato['proporcion']:.0%}) incumplen al menos un criterio de formato "
            f"(umbral 15 %). Fallas: {formato['por_criterio']}."
        ),
        "dataset_grande_y_de_calidad": (
            f"El dataset etiquetado tiene {n_ejemplos} ejemplos; el umbral es 200."
        ),
        "presupuesto_limitado_o_iterar_rapido": (
            "El proyecto usa el plan gratuito de Gemini: no hay presupuesto para pagar ningún "
            "entrenamiento, y los cambios de prompt o de corpus se prueban en minutos."
        ),
        "necesita_multiples_variantes": (
            "Una sola faena y un solo comportamiento esperado: no se necesitan versiones distintas."
        ),
    }
    respuestas = {
        "informacion_cambia_seguido": True,
        "problema_de_formato_o_tono": formato["supera_umbral"],
        "dataset_grande_y_de_calidad": n_ejemplos >= 200,
        "presupuesto_limitado_o_iterar_rapido": True,
        "necesita_multiples_variantes": False,
    }
    return respuestas, evidencia


def analisis_sensibilidad(respuestas: dict) -> list[tuple[str, bool, list[str], bool]]:
    """Cambia una respuesta a la vez y dice si cambia la recomendación."""
    _, base = recomendar_estrategia(respuestas)
    filas = []
    for clave in respuestas:
        variante = {**respuestas, clave: not respuestas[clave]}
        _, ganadoras = recomendar_estrategia(variante)
        filas.append((clave, variante[clave], ganadoras, set(ganadoras) != set(base)))
    return filas


def generar_esqueleto(problema: str, puntos: dict, ganadoras: list[str]) -> str:
    lineas = ["# Decisión de personalización", "", "## 1. El problema", problema, "",
              "## 2. Resultado del método de decisión"]
    lineas += [f"- {t}: {p} puntos" for t, p in sorted(puntos.items(), key=lambda x: -x[1])]
    if len(ganadoras) > 1:
        lineas += ["", f"**Empate entre: {', '.join(ganadoras)}**"]
    lineas += ["", "## 3. Técnica elegida y por qué", "[COMPLETAR]", "",
               "## 4. Qué se necesitaría para ejecutarla", "[COMPLETAR con números]"]
    return "\n".join(lineas)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--esqueleto", action="store_true",
                        help="Escribe el esqueleto en docs/decision_personalizacion.md si no existe.")
    args = parser.parse_args()

    respuestas, evidencia = reunir_evidencia()
    print("Respuestas y evidencia:")
    for clave, valor in respuestas.items():
        print(f"- {clave} = {valor}\n    {evidencia[clave]}")

    puntos, ganadoras = recomendar_estrategia(respuestas)
    print("\nPuntaje:", puntos)
    print("Candidatas:", ganadoras, "(EMPATE)" if len(ganadoras) > 1 else "")

    print("\nSensibilidad (cambiando una respuesta a la vez):")
    for clave, nuevo, ganadoras_v, cambia in analisis_sensibilidad(respuestas):
        print(f"- {clave} -> {nuevo}: {ganadoras_v} [{'CAMBIA' if cambia else 'igual'}]")

    if args.esqueleto:
        if ARCHIVO_DECISION.exists():
            print(f"\n{ARCHIVO_DECISION.name} ya existe: no se sobrescribe.")
        else:
            ARCHIVO_DECISION.write_text(generar_esqueleto(
                "[COMPLETAR: el problema, sin nombrar todavía ninguna técnica]", puntos, ganadoras),
                encoding="utf-8")
            print(f"\nEsqueleto escrito en docs/{ARCHIVO_DECISION.name}")


if __name__ == "__main__":
    main()
