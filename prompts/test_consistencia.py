import json
import sys
import time
from pathlib import Path

# Permite importar el módulo de src/ ejecutando desde la raíz del repo
RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from consumir_gemini import armar_peticion, enviar_peticion, extraer_texto, parsear_respuesta_json  # noqa: E402
from banco import BANCO_DE_PROMPTS  # noqa: E402

INTENTOS = 3
PAUSA_SEGUNDOS = 13  # el plan gratis de 3.6-flash permite 5 peticiones por minuto
ARCHIVO_REGISTRO = Path(__file__).resolve().parent / "registro_resultados.json"


def probar_prompt(prompt):
    """Ejecuta un prompt varias veces y cuenta cuántas respuestas son JSON válido con las claves esperadas."""
    exitos = 0
    fallos = []
    for intento in range(1, INTENTOS + 1):
        try:
            url, headers, body = armar_peticion(
                prompt["ejemplo_usuario"],
                system_instruction=prompt["system_instruction"],
                response_schema=prompt.get("response_schema"),
            )
            texto = extraer_texto(enviar_peticion(url, headers, body))
            datos = parsear_respuesta_json(texto, prompt["claves_esperadas"])
            exitos += 1
            print(f"  intento {intento}: OK -> {datos}")
        except (ValueError, RuntimeError) as error:
            fallos.append(f"intento {intento}: {error}")
            print(f"  intento {intento}: FALLÓ -> {error}")
        time.sleep(PAUSA_SEGUNDOS)
    return {"exitos": exitos, "intentos": INTENTOS, "fallos": fallos}


def main():
    registro = {}
    for prompt in BANCO_DE_PROMPTS:
        print(f"\n=== {prompt['nombre']} ===")
        resultado = probar_prompt(prompt)
        registro[prompt["nombre"]] = resultado
        print(f"{prompt['nombre']}: {resultado['exitos']}/{resultado['intentos']} respuestas válidas")

    with open(ARCHIVO_REGISTRO, "w", encoding="utf-8") as archivo:
        json.dump(registro, archivo, indent=2, ensure_ascii=False)
    print(f"\nRegistro guardado en {ARCHIVO_REGISTRO}")


if __name__ == "__main__":
    main()