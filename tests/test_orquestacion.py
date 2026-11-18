"""Pruebas del manejo de errores del flujo orquestado (Bloque 20).
Se simulan fallos del modelo: ninguna prueba llama a la API."""
from unittest.mock import MagicMock

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from src.enrutamiento import (
    RESPALDO_EMERGENCIA,
    RESPALDO_PROCEDIMIENTO,
    RESPUESTA_GENERAL_RESPALDO,
    construir_cadena_con_enrutamiento,
    construir_flujo,
    construir_ruta_segura,
    procesar_consulta_segura,
)


def fallar_a_proposito(_):
    raise ConnectionError("error de red simulado")


# ---------- Fallbacks por ruta ----------

def test_ruta_emergencia_usa_respaldo_ante_fallo_del_modelo():
    ruta = construir_ruta_segura(RunnableLambda(fallar_a_proposito), RESPALDO_EMERGENCIA)
    resultado = ruta.invoke({"consulta": "hay un herido"})
    assert resultado == RESPALDO_EMERGENCIA
    assert "aviso" in resultado.lower()


def test_ruta_procedimiento_usa_respaldo_ante_fallo_del_modelo():
    ruta = construir_ruta_segura(RunnableLambda(fallar_a_proposito), RESPALDO_PROCEDIMIENTO)
    assert ruta.invoke({"consulta": "cambiar un rodillo"}) == RESPALDO_PROCEDIMIENTO


def test_ruta_segura_no_usa_respaldo_si_la_ruta_funciona():
    ruta = construir_ruta_segura(RunnableLambda(lambda _: "respuesta normal"), RESPALDO_PROCEDIMIENTO)
    assert ruta.invoke({"consulta": "cambiar un rodillo"}) == "respuesta normal"


def test_flujo_completo_usa_respaldo_si_falla_la_ruta_de_emergencia():
    # La clasificación funciona ("emergencia"), pero la llamada siguiente al modelo falla
    modelo_falso = MagicMock(side_effect=[AIMessage(content="emergencia"), ConnectionError("simulado")])
    resultado = construir_flujo(modelo_falso).invoke({"consulta": "se cayó un compañero"})
    assert resultado == RESPALDO_EMERGENCIA


# ---------- try/except general ----------

def test_procesar_consulta_segura_no_propaga_fallo_de_la_clasificacion():
    clasificacion_falsa = MagicMock(side_effect=ConnectionError("simulado"))
    cadena = construir_cadena_con_enrutamiento(paso_clasificacion=clasificacion_falsa)
    resultado = procesar_consulta_segura(cadena, "mensaje de prueba")
    assert resultado == RESPUESTA_GENERAL_RESPALDO


def test_respuesta_general_incluye_instrucciones_de_emergencia():
    # Si no se sabe qué tipo de consulta era, igual hay que cubrir el caso de una emergencia
    assert "emergencia" in RESPUESTA_GENERAL_RESPALDO.lower()
    assert "aviso" in RESPUESTA_GENERAL_RESPALDO.lower()


def test_procesar_consulta_segura_registra_el_error(caplog):
    clasificacion_falsa = MagicMock(side_effect=ConnectionError("simulado"))
    cadena = construir_cadena_con_enrutamiento(paso_clasificacion=clasificacion_falsa)
    procesar_consulta_segura(cadena, "mensaje de prueba")
    assert "Error procesando la consulta" in caplog.text


def test_flujo_con_modelo_que_siempre_falla_igual_responde():
    modelo_caido = MagicMock(side_effect=ConnectionError("modelo caído"))
    resultado = procesar_consulta_segura(construir_flujo(modelo_caido), "se cayó un compañero")
    assert resultado == RESPUESTA_GENERAL_RESPALDO