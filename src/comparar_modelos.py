import time
from datetime import date
from consumir_gemini import armar_peticion, enviar_peticion, extraer_texto, calcular_costo

MODELOS = {
    "gemini-3.6-flash":      {"entrada": 0.75, "salida": 3.75},
    "gemini-3.5-flash-lite": {"entrada": 0.30, "salida": 2.50},
}

PREGUNTA_LATENCIA = "Confirma en una frase corta que esta conexión funciona"

PREGUNTAS_CASO = [
    "¿Qué pasos debo seguir antes de intervenir una correa transportadora?",
    "¿Qué es el bloqueo y etiquetado de energías y cuándo se aplica?",
    "¿Qué elementos de protección personal necesito para trabajar en altura?",
]

ARCHIVO_RESPUESTAS = "docs/respuestas_comparacion.md"


def medir_latencia(modelo, repeticiones=4):
    """Mide la latencia del modelo varias veces, sin reintentos, para que la espera no ensucie la medición."""
    latencias = []
    datos = None
    for i in range(repeticiones):
        url, headers, body = armar_peticion(PREGUNTA_LATENCIA, modelo)
        inicio = time.perf_counter()
        try:
            datos = enviar_peticion(url, headers, body, intentos=1)
        except RuntimeError as error:
            print(f"  Medición {i + 1} descartada: {error}")
            time.sleep(3)
            continue
        latencias.append(time.perf_counter() - inicio)
        time.sleep(1)
    return latencias, datos


def evaluar_calidad(modelo):
    """Hace las preguntas del caso y guarda las respuestas completas en el archivo."""
    for pregunta in PREGUNTAS_CASO:
        url, headers, body = armar_peticion(pregunta, modelo)
        try:
            texto = extraer_texto(enviar_peticion(url, headers, body))
        except RuntimeError as error:
            texto = f"ERROR: {error}"
        print(f"\nP: {pregunta}\nR: {texto[:200]}...")
        with open(ARCHIVO_RESPUESTAS, "a", encoding="utf-8") as archivo:
            archivo.write(f"### {modelo}\n\n**P:** {pregunta}\n\n{texto}\n\n---\n\n")
        time.sleep(1)


def main():
    with open(ARCHIVO_RESPUESTAS, "w", encoding="utf-8") as archivo:
        archivo.write(f"# Respuestas de la comparación de modelos ({date.today()})\n\n")

    for modelo, precios in MODELOS.items():
        print(f"\n===== {modelo} =====")

        latencias, datos = medir_latencia(modelo)
        if latencias:
            promedio = sum(latencias) / len(latencias)
            print(f"Latencia promedio: {promedio:.2f} s  {[round(l, 2) for l in latencias]}")
        if datos:
            costo = calcular_costo(datos, precios["entrada"], precios["salida"])
            print(f"Costo última petición: ${costo:.6f}")
            print(f"Tokens: {datos.get('usageMetadata')}")

        evaluar_calidad(modelo)

    print(f"\nRespuestas completas guardadas en {ARCHIVO_RESPUESTAS}")


if __name__ == "__main__":
    main()