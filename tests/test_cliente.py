"""Pruebas unitarias del cliente modular (src/cliente.py).
Usan mocks: no llaman a la API real, no gastan cuota y no esperan de verdad.
Ejecutar desde la raíz del repo:  python -m pytest -v
"""
from unittest.mock import Mock, patch

import pytest
import requests

from src import cliente

URL, HEADERS, BODY = "https://api.falsa/modelo", {"x-goog-api-key": "falsa"}, {"contents": []}


@pytest.fixture(autouse=True)
def entorno_limpio(monkeypatch):
    """Se ejecuta solo antes de cada prueba: reinicia el costo acumulado y pone una key falsa,
    para que ninguna prueba dependa de otra ni del .env real."""
    cliente.costo_total_sesion = 0.0
    monkeypatch.setenv("GEMINI_API_KEY", "clave-de-prueba")


def respuesta_falsa(codigo, contenido=None):
    """Crea una respuesta HTTP simulada con el código y el JSON indicados."""
    respuesta = Mock(status_code=codigo)
    respuesta.json.return_value = contenido if contenido is not None else {"error": {"message": "simulado"}}
    return respuesta


# ---------- enviar_peticion: clasificación de errores ----------

def test_enviar_peticion_credencial_invalida_401_lanza_value_error():
    with patch("src.cliente.requests.post", return_value=respuesta_falsa(401)):
        with pytest.raises(ValueError):
            cliente.enviar_peticion(URL, HEADERS, BODY)


def test_enviar_peticion_key_invalida_400_lanza_value_error():
    # Gemini a veces responde 400 (y no 401) cuando la API key es inválida
    with patch("src.cliente.requests.post", return_value=respuesta_falsa(400)):
        with pytest.raises(ValueError):
            cliente.enviar_peticion(URL, HEADERS, BODY)


def test_enviar_peticion_limite_de_uso_429_lanza_timeout_error():
    with patch("src.cliente.requests.post", return_value=respuesta_falsa(429)):
        with pytest.raises(TimeoutError):
            cliente.enviar_peticion(URL, HEADERS, BODY)


def test_enviar_peticion_servidor_saturado_503_lanza_timeout_error():
    with patch("src.cliente.requests.post", return_value=respuesta_falsa(503)):
        with pytest.raises(TimeoutError):
            cliente.enviar_peticion(URL, HEADERS, BODY)


def test_enviar_peticion_sin_conexion_lanza_timeout_error():
    with patch("src.cliente.requests.post", side_effect=requests.exceptions.ConnectionError):
        with pytest.raises(TimeoutError):
            cliente.enviar_peticion(URL, HEADERS, BODY)


def test_enviar_peticion_exito_devuelve_json():
    contenido = {"candidates": [{"content": {"parts": [{"text": "hola"}]}}]}
    with patch("src.cliente.requests.post", return_value=respuesta_falsa(200, contenido)):
        assert cliente.enviar_peticion(URL, HEADERS, BODY) == contenido


# ---------- con_reintento: cuándo reintenta y cuándo no ----------

def test_con_reintento_reintenta_y_luego_tiene_exito():
    funcion = Mock(side_effect=[TimeoutError("simulado"), "ok"])  # falla 1 vez, después funciona
    with patch("src.cliente.time.sleep") as mock_sleep:
        assert cliente.con_reintento(funcion) == "ok"
    assert funcion.call_count == 2
    mock_sleep.assert_called_once()


def test_con_reintento_agota_intentos_y_propaga_timeout_error():
    funcion = Mock(side_effect=TimeoutError("simulado"))  # falla siempre
    with patch("src.cliente.time.sleep") as mock_sleep:
        with pytest.raises(TimeoutError):
            cliente.con_reintento(funcion, intentos=3)
    assert funcion.call_count == 3
    assert mock_sleep.call_count == 2  # espera entre intentos, no después del último


def test_con_reintento_no_reintenta_value_error():
    funcion = Mock(side_effect=ValueError("key inválida"))
    with patch("src.cliente.time.sleep") as mock_sleep:
        with pytest.raises(ValueError):
            cliente.con_reintento(funcion)
    assert funcion.call_count == 1
    mock_sleep.assert_not_called()


# ---------- registrar_costo: cálculo y acumulado ----------

def test_registrar_costo_calcula_y_acumula():
    # 1000 de entrada x $0.75/M + (500 salida + 500 pensamiento) x $3.75/M = $0.0045
    datos = {"usageMetadata": {"promptTokenCount": 1000, "candidatesTokenCount": 500,
                               "thoughtsTokenCount": 500, "totalTokenCount": 2000}}
    costo = cliente.registrar_costo(datos, modelo="gemini-3.6-flash")
    assert costo == pytest.approx(0.0045)
    cliente.registrar_costo(datos, modelo="gemini-3.6-flash")
    assert cliente.costo_total_sesion == pytest.approx(0.009)


def test_registrar_costo_modelo_sin_precio_devuelve_cero():
    datos = {"usageMetadata": {"promptTokenCount": 1000, "totalTokenCount": 1000}}
    assert cliente.registrar_costo(datos, modelo="modelo-desconocido") == 0.0
    assert cliente.costo_total_sesion == 0.0


# ---------- consultar_modelo: la interfaz pública ----------

def test_consultar_modelo_convierte_timeout_en_runtime_error():
    with patch("src.cliente.con_reintento", side_effect=TimeoutError("simulado")):
        with pytest.raises(RuntimeError):
            cliente.consultar_modelo("pregunta de prueba")


def test_consultar_modelo_propaga_value_error_sin_reintentar():
    with patch("src.cliente.enviar_peticion", side_effect=ValueError("key inválida")) as mock_enviar, \
         patch("src.cliente.time.sleep"):
        with pytest.raises(ValueError):
            cliente.consultar_modelo("pregunta de prueba")
    assert mock_enviar.call_count == 1


def test_consultar_modelo_exito_devuelve_texto_y_registra_costo():
    contenido = {
        "candidates": [{"content": {"parts": [{"text": "Santiago"}]}}],
        "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5, "totalTokenCount": 15},
    }
    with patch("src.cliente.enviar_peticion", return_value=contenido):
        texto = cliente.consultar_modelo("¿Capital de Chile?", modelo="gemini-3.6-flash")
    assert texto == "Santiago"
    assert cliente.costo_total_sesion > 0