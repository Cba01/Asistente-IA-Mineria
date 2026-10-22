"""Asistente IA de seguridad minera: miniaplicación del Módulo 1.

Uso:
    python main.py "¿Qué debo hacer antes de intervenir una correa transportadora?"
    python main.py        (sin argumento, pide la pregunta por teclado)
"""
import sys

from prompts.banco import BANCO_DE_PROMPTS
from src.consumir_gemini import (
    MODELO,
    armar_peticion,
    enviar_peticion,
    extraer_texto,
    parsear_respuesta_json,
)

PROMPT_CLASIFICACION = next(
    p for p in BANCO_DE_PROMPTS if p["nombre"] == "clasificar_riesgo")

SISTEMA_RESPUESTA = (
    "Eres un asistente de seguridad para faenas mineras en Chile. Responde siempre en español, "
    "usando terminología chilena (AST, PTS, permiso de trabajo). "
    "Da una respuesta práctica y breve, de máximo 8 puntos, sin fórmulas ni LaTeX. "
    "Termina recordando que esta orientación no reemplaza el procedimiento oficial de la faena "
    "ni las instrucciones del supervisor."
    "Da una respuesta práctica y breve, de máximo 8 puntos numerados, en texto plano "
    "(sin markdown, sin ** ni #, sin fórmulas ni LaTeX). "
)


def obtener_pregunta():
    """Toma la pregunta desde la línea de comandos o, si no viene, la pide por teclado."""
    if len(sys.argv) > 1:
        return " ".join(sys.argv[1:])
    return input("Escribe tu consulta de seguridad: ")


def clasificar_riesgo(pregunta):
    """Clasifica la consulta con el prompt del banco y devuelve un diccionario validado."""
    url, headers, body = armar_peticion(
        pregunta,
        system_instruction=PROMPT_CLASIFICACION["system_instruction"],
        response_schema=PROMPT_CLASIFICACION["response_schema"],
    )
    texto = extraer_texto(enviar_peticion(url, headers, body))
    return parsear_respuesta_json(texto, PROMPT_CLASIFICACION["claves_esperadas"])


def responder_pregunta(pregunta, clasificacion):
    """Responde la consulta usando la clasificación como contexto. Devuelve el texto y los tokens usados."""
    contexto = (
        f" Clasificación previa de la consulta: riesgo de {clasificacion['tipo_riesgo']}, "
        f"criticidad {clasificacion['criticidad']}, "
        f"{'requiere' if clasificacion['requiere_bloqueo'] else 'no requiere'} bloqueo de energías."
    )
    url, headers, body = armar_peticion(
        pregunta, system_instruction=SISTEMA_RESPUESTA + contexto)
    datos = enviar_peticion(url, headers, body)
    tokens = datos.get("usageMetadata", {}).get("totalTokenCount", 0)
    return extraer_texto(datos), tokens


def mostrar_resultado(clasificacion, respuesta, tokens):
    """Imprime la clasificación y la respuesta en consola."""
    print("\n--- Clasificación ---")
    print(f"Tipo de riesgo:   {clasificacion['tipo_riesgo']}")
    print(f"Criticidad:       {clasificacion['criticidad']}")
    print(
        f"Requiere bloqueo: {'sí' if clasificacion['requiere_bloqueo'] else 'no'}")
    print("\n--- Respuesta ---")
    print(respuesta)
    print(f"\n(modelo: {MODELO} · tokens usados en la respuesta: {tokens})")


def main():
    try:
        pregunta = obtener_pregunta()
        print(f"Consultando a {MODELO}...")
        clasificacion = clasificar_riesgo(pregunta)
        respuesta, tokens = responder_pregunta(pregunta, clasificacion)
        mostrar_resultado(clasificacion, respuesta, tokens)
        return 0
    except (ValueError, RuntimeError) as error:
        print(f"\nNo se pudo completar la consulta: {error}")
        return 1
    except KeyboardInterrupt:
        print("\nConsulta cancelada.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
