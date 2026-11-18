"""Pruebas del enrutamiento: se fuerza cada ruta con una clasificación falsa, sin llamar a la API."""
from unittest.mock import MagicMock

from langchain_core.messages import AIMessage

from src.enrutamiento import construir_cadena_con_enrutamiento, construir_paso_clasificacion


def clasificacion_que_devuelve(categoria):
    return MagicMock(return_value=categoria)


def test_clasificacion_normaliza_mayusculas_espacios_y_punto():
    modelo_falso = MagicMock(return_value=AIMessage(content="  Emergencia.\n"))
    resultado = construir_paso_clasificacion(modelo_falso).invoke({"consulta": "se cayó alguien"})
    assert resultado == "emergencia"


def test_enrutamiento_va_a_emergencia():
    cadena_emergencia = MagicMock(return_value="instrucciones de emergencia")
    cadena = construir_cadena_con_enrutamiento(clasificacion_que_devuelve("emergencia"),
                                               cadena_emergencia=cadena_emergencia)
    assert cadena.invoke({"consulta": "hay un herido"}) == "instrucciones de emergencia"
    assert cadena_emergencia.called


def test_enrutamiento_va_a_normativa():
    cadena_normativa = MagicMock(return_value="respuesta normativa")
    cadena = construir_cadena_con_enrutamiento(clasificacion_que_devuelve("normativa"),
                                               cadena_normativa=cadena_normativa)
    assert cadena.invoke({"consulta": "¿qué dice el DS 594?"}) == "respuesta normativa"


def test_enrutamiento_va_a_procedimiento():
    cadena_procedimiento = MagicMock(return_value="checklist")
    cadena = construir_cadena_con_enrutamiento(clasificacion_que_devuelve("procedimiento"),
                                               cadena_procedimiento=cadena_procedimiento)
    assert cadena.invoke({"consulta": "cambiar un rodillo"}) == "checklist"


def test_enrutamiento_usa_procedimiento_ante_categoria_desconocida():
    cadena_procedimiento = MagicMock(return_value="checklist")
    cadena_emergencia = MagicMock(return_value="emergencia")
    cadena = construir_cadena_con_enrutamiento(clasificacion_que_devuelve("no estoy seguro"),
                                               cadena_emergencia=cadena_emergencia,
                                               cadena_procedimiento=cadena_procedimiento)
    assert cadena.invoke({"consulta": "algo ambiguo"}) == "checklist"
    assert not cadena_emergencia.called


def test_la_ruta_recibe_la_consulta_original_y_la_categoria():
    cadena_normativa = MagicMock(return_value="ok")
    cadena = construir_cadena_con_enrutamiento(clasificacion_que_devuelve("normativa"),
                                               cadena_normativa=cadena_normativa)
    cadena.invoke({"consulta": "¿qué dice el DS 132?"})
    entrada = cadena_normativa.call_args.args[0]
    assert entrada["consulta"] == "¿qué dice el DS 132?"
    assert entrada["categoria"] == "normativa"