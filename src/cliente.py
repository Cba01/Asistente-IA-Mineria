"""Cliente modular para consumir la API de Gemini.

Expone una sola función pública, consultar_modelo(), que por dentro arma la petición,
la envía con reintentos, registra su costo y devuelve el texto. Clasifica los errores en dos tipos:
- ValueError: errores de configuración que no se arreglan reintentando (key inválida, modelo inexistente).
- TimeoutError: errores temporales que sí vale la pena reintentar (límite de uso, servidor caído, red).

Uso desde la raíz del repo:  python -m src.cliente
"""
import random
import time
from typing import Any, Callable

import requests

from src.consumir_gemini import MODELO, armar_peticion, calcular_costo, extraer_texto

# Precios por 1M de tokens (USD), plan pagado. Fuente: ai.google.dev/gemini-api/docs/pricing
PRECIOS_POR_MILLON = {
    "gemini-3.6-flash": {"entrada": 0.75, "salida": 3.75},
    "gemini-3.5-flash-lite": {"entrada": 0.30, "salida": 2.50},
}

costo_total_sesion = 0.0


def _detalle_error(respuesta: requests.Response) -> str:
    """Devuelve el mensaje de error que entrega Google, si viene en la respuesta."""
    try:
        return respuesta.json().get("error", {}).get("message", "")
    except ValueError:  # la respuesta no era JSON
        return ""


def enviar_peticion(url: str, headers: dict, body: dict) -> dict:
    """Envía la petición una sola vez y clasifica el resultado.
    No reintenta: esa decisión es de con_reintento."""
    try:
        respuesta = requests.post(url, headers=headers, json=body, timeout=60)
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
        raise TimeoutError("No se pudo contactar al proveedor. Puede ser momentáneo.")

    codigo = respuesta.status_code
    if codigo == 429 or codigo >= 500:
        raise TimeoutError(f"El proveedor no pudo procesar la petición (error {codigo}). Hay que esperar y reintentar.")
    if 400 <= codigo < 500:
        raise ValueError(f"Petición rechazada (error {codigo}): {_detalle_error(respuesta)} Revisa tu GEMINI_API_KEY y GEMINI_MODEL.")

    try:
        return respuesta.json()
    except ValueError:
        raise RuntimeError("La respuesta del servicio no llegó en formato JSON.")


def con_reintento(funcion: Callable[[], Any], intentos: int = 3,
                  espera_base: float = 2, espera_maxima: float = 30) -> Any:
    """Ejecuta la función y, si lanza TimeoutError, la reintenta con backoff exponencial,
    con tope (espera_maxima) y jitter. Cualquier otro error se propaga de inmediato."""
    for intento in range(1, intentos + 1):
        try:
            return funcion()
        except TimeoutError as error:
            if intento == intentos:
                raise
            espera = min(espera_base * (2 ** (intento - 1)), espera_maxima)
            espera_con_jitter = espera + random.uniform(0, espera * 0.1)
            print(f"  Intento {intento} de {intentos} falló: {error} "
                  f"Reintentando en {espera_con_jitter:.1f}s...")
            time.sleep(espera_con_jitter)


def registrar_costo(datos: dict, modelo: str = MODELO) -> float:
    """Calcula el costo de una respuesta exitosa y lo suma al acumulado de la sesión."""
    global costo_total_sesion
    precios = PRECIOS_POR_MILLON.get(modelo)
    if precios is None:
        print(f"  (sin precio registrado para {modelo}; costo no calculado)")
        return 0.0
    costo = calcular_costo(datos, precios["entrada"], precios["salida"])
    costo_total_sesion += costo
    tokens = datos.get("usageMetadata", {}).get("totalTokenCount", 0)
    print(f"  Operación: {tokens} tokens, costo ${costo:.6f} (acumulado sesión: ${costo_total_sesion:.6f})")
    return costo


def consultar_modelo(pregunta: str, system_instruction: str = None,
                     response_schema: dict = None, modelo: str = MODELO) -> str:
    """Única función pública del cliente: recibe una pregunta y devuelve el texto de la respuesta."""
    url, headers, body = armar_peticion(pregunta, system_instruction, response_schema, modelo)
    try:
        datos = con_reintento(lambda: enviar_peticion(url, headers, body))
    except TimeoutError:
        raise RuntimeError("El servicio no respondió tras varios intentos. Intenta más tarde.")
    registrar_costo(datos, modelo)  # solo se registra si la respuesta llegó bien
    return extraer_texto(datos)


if __name__ == "__main__":
    try:
        print(consultar_modelo("¿Cuál es la capital de Chile? Responde en una frase."))
    except ValueError as error:
        print(f"Error de configuración: {error}")
    except RuntimeError as error:
        print(f"Error del servicio: {error}")