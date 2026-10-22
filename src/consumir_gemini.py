import json
import os
import re
import time

import requests
from dotenv import load_dotenv

load_dotenv()

ERRORES_TEMPORALES = (429, 500, 503)
MODELO = os.getenv("GEMINI_MODEL") or "gemini-3.6-flash"
URL_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


def armar_peticion(pregunta, system_instruction=None, response_schema=None, modelo=MODELO):
    """Valida la pregunta y arma la URL, los headers y el body.
    system_instruction: instrucciones de comportamiento, separadas de la pregunta del usuario.
    response_schema: si se entrega, obliga al modelo a responder JSON con esa estructura."""
    if not pregunta or not pregunta.strip():
        raise ValueError("La pregunta no puede estar vacía.")
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("No se encontró GEMINI_API_KEY. Revisa tu archivo .env.")
    url = f"{URL_BASE}/{modelo}:generateContent"
    headers = {"x-goog-api-key": api_key}
    body = {"contents": [{"parts": [{"text": pregunta}]}]}
    if system_instruction:
        body["systemInstruction"] = {"parts": [{"text": system_instruction}]}
    if response_schema:
        body["generationConfig"] = {
            "responseMimeType": "application/json",
            "responseSchema": response_schema,
        }
    return url, headers, body


def enviar_peticion(url, headers, body, intentos=3):
    """Envía la petición y devuelve la respuesta como diccionario.
    Si el servicio está saturado, reintenta esperando cada vez más."""
    for intento in range(1, intentos + 1):
        try:
            respuesta = requests.post(url, headers=headers, json=body, timeout=60)
        except requests.exceptions.ConnectionError:
            raise RuntimeError("No se pudo conectar con el servicio. Revisa tu conexión a internet.")
        except requests.exceptions.Timeout:
            raise RuntimeError("El servicio tardó demasiado en responder.")

        if respuesta.status_code in ERRORES_TEMPORALES and intento < intentos:
            espera = 2 ** intento  # 2s, 4s, 8s...
            print(f"  (servicio ocupado, error {respuesta.status_code}; reintento {intento} en {espera}s)")
            time.sleep(espera)
            continue
        break

    if respuesta.status_code in (401, 403):
        raise RuntimeError("La API key es inválida o no tiene permisos.")
    if not respuesta.ok:
        try:
            detalle = respuesta.json().get("error", {}).get("message", "")
        except requests.exceptions.JSONDecodeError:
            detalle = ""
        raise RuntimeError(f"El servicio respondió con error {respuesta.status_code}. {detalle}")

    try:
        return respuesta.json()
    except requests.exceptions.JSONDecodeError:
        raise RuntimeError("La respuesta del servicio no llegó en formato JSON.")


def extraer_texto(datos):
    """Saca el texto generado de la respuesta de Gemini."""
    try:
        return datos["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        raise RuntimeError("La respuesta no trae el texto generado en el lugar esperado.")


def parsear_respuesta_json(texto, claves_esperadas):
    """Convierte el texto del modelo en diccionario y valida que traiga las claves esperadas."""
    texto_limpio = texto.strip()
    texto_limpio = re.sub(r"^```(?:json)?\s*", "", texto_limpio)  # quita ```json del inicio
    texto_limpio = re.sub(r"\s*```$", "", texto_limpio)  # quita ``` del final
    try:
        datos = json.loads(texto_limpio)
    except json.JSONDecodeError:
        raise ValueError("La respuesta del modelo no es JSON válido.")
    if not isinstance(datos, dict):
        raise ValueError("La respuesta no es un objeto JSON.")
    faltantes = [clave for clave in claves_esperadas if clave not in datos]
    if faltantes:
        raise ValueError(f"La respuesta no tiene las claves esperadas: {faltantes}")
    return datos


def obtener_dato_de_prueba(pregunta):
    """Función principal: orquesta armar_peticion, enviar_peticion y extraer_texto."""
    url, headers, body = armar_peticion(pregunta)
    datos = enviar_peticion(url, headers, body)
    return extraer_texto(datos)


def calcular_costo(datos, precio_entrada, precio_salida):
    """Calcula el costo en USD de una petición. Los precios son por 1 millón de tokens."""
    uso = datos.get("usageMetadata", {})
    tokens_entrada = uso.get("promptTokenCount", 0)
    tokens_salida = uso.get("candidatesTokenCount", 0) + uso.get("thoughtsTokenCount", 0)
    return (tokens_entrada * precio_entrada + tokens_salida * precio_salida) / 1_000_000


if __name__ == "__main__":
    try:
        print(obtener_dato_de_prueba("Confirma en una frase corta que esta conexión funciona"))
    except (ValueError, RuntimeError) as error:
        print("No se pudo completar la operación:", error)