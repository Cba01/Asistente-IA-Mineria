import os
import requests
from dotenv import load_dotenv

load_dotenv()

MODELO = "gemini-3.6-flash"
URL_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


def armar_peticion(pregunta):
    """Valida la pregunta y arma la URL, los headers y el body."""
    if not pregunta or not pregunta.strip():
        raise ValueError("La pregunta no puede estar vacía.")
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("No se encontró GEMINI_API_KEY. Revisa tu archivo .env.")
    url = f"{URL_BASE}/{MODELO}:generateContent"
    headers = {"x-goog-api-key": api_key}
    body = {"contents": [{"parts": [{"text": pregunta}]}]}
    return url, headers, body


def enviar_peticion(url, headers, body):
    """Envía la petición y devuelve la respuesta como diccionario."""
    try:
        respuesta = requests.post(url, headers=headers, json=body, timeout=30)
    except requests.exceptions.ConnectionError:
        raise RuntimeError("No se pudo conectar con el servicio. Revisa tu conexión a internet.")
    except requests.exceptions.Timeout:
        raise RuntimeError("El servicio tardó demasiado en responder.")

    if respuesta.status_code in (401, 403):
        raise RuntimeError("La API key es inválida o no tiene permisos.")
    if respuesta.status_code == 429:
        raise RuntimeError("Se alcanzó el límite de uso de la API. Espera un momento e intenta de nuevo.")
    if not respuesta.ok:
        raise RuntimeError(f"El servicio respondió con error {respuesta.status_code}.")

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


def obtener_dato_de_prueba(pregunta):
    """Función principal: orquesta las otras tres."""
    url, headers, body = armar_peticion(pregunta)
    datos = enviar_peticion(url, headers, body)
    return extraer_texto(datos)


if __name__ == "__main__":
    try:
        print(obtener_dato_de_prueba("Confirma en una frase corta que esta conexión funciona"))
    except (ValueError, RuntimeError) as error:
        print("No se pudo completar la operación:", error)