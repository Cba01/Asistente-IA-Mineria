"""Pruebas de la chain de tres pasos. El modelo es falso: no se llama a la API."""
from unittest.mock import MagicMock

from langchain_core.messages import AIMessage

from src.cadena_tres_pasos import construir_cadena

ANALISIS_FALSO = "Cambio de rodillo\npeligro de atrapamiento\ncaída de altura\nenergía residual"
RECOMENDACIONES_FALSAS = "Bloquear energías\nUsar arnés\nTrabar la correa"
CHECKLIST_FALSO = "1. Bloquear energías\n2. Usar arnés\n3. Trabar la correa"


def crear_modelo_falso():
    """Modelo falso que responde distinto en cada una de las 3 llamadas, en orden."""
    return MagicMock(side_effect=[
        AIMessage(content=ANALISIS_FALSO),
        AIMessage(content=RECOMENDACIONES_FALSAS),
        AIMessage(content=CHECKLIST_FALSO),
    ])


def test_cadena_ejecuta_los_tres_pasos_y_devuelve_el_ultimo():
    modelo_falso = crear_modelo_falso()
    resultado = construir_cadena(modelo_falso).invoke({"consulta": "cambiar un rodillo"})
    assert modelo_falso.call_count == 3
    assert resultado == CHECKLIST_FALSO


def test_cada_paso_recibe_la_salida_del_anterior():
    # Confirma que es una chain de verdad, no tres llamadas independientes
    modelo_falso = crear_modelo_falso()
    construir_cadena(modelo_falso).invoke({"consulta": "cambiar un rodillo"})
    prompt_paso_2 = modelo_falso.call_args_list[1].args[0].to_string()
    prompt_paso_3 = modelo_falso.call_args_list[2].args[0].to_string()
    assert ANALISIS_FALSO in prompt_paso_2
    assert RECOMENDACIONES_FALSAS in prompt_paso_3


def test_primer_paso_recibe_la_consulta_del_usuario():
    modelo_falso = crear_modelo_falso()
    construir_cadena(modelo_falso).invoke({"consulta": "cambiar un rodillo"})
    prompt_paso_1 = modelo_falso.call_args_list[0].args[0].to_string()
    assert "cambiar un rodillo" in prompt_paso_1