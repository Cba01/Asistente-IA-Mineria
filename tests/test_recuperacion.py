"""Pruebas del flujo de recuperación con citas. No llaman a la API:
el retriever y el modelo se reemplazan por versiones falsas."""
from langchain_core.documents import Document
from langchain_core.language_models import FakeListChatModel

import pytest

from src.recuperacion import (ADVERTENCIA, SIN_INFORMACION, construir_prompt,
                              extraer_citas, formatear_contexto, responder)

CHUNKS = [
    Document(id="pts_gen_002_bloqueo_2", page_content="Cada trabajador usa su propio candado.",
             metadata={"fuente": "pts_gen_002_bloqueo.md"}),
    Document(id="ds594_condiciones_sanitarias_3", page_content="El límite de ruido es 85 dB(A) en 8 horas.",
             metadata={"fuente": "ds594_condiciones_sanitarias.md"}),
]


class RetrieverFalso:
    """Devuelve siempre los mismos chunks y recuerda qué pregunta recibió."""
    def __init__(self, chunks):
        self.chunks = chunks
        self.pregunta = None

    def invoke(self, pregunta):
        self.pregunta = pregunta
        return self.chunks


def test_formatear_contexto_numera_desde_1_y_mapea_fuentes():
    contexto, citas = formatear_contexto(CHUNKS)
    assert contexto.startswith("[1] Cada trabajador")
    assert "\n\n[2] El límite de ruido" in contexto
    assert citas == {1: "pts_gen_002_bloqueo.md", 2: "ds594_condiciones_sanitarias.md"}


def test_chunk_sin_metadata_queda_como_desconocida():
    _, citas = formatear_contexto([Document(page_content="texto")])
    assert citas == {1: "desconocida"}


def test_prompt_incluye_pregunta_exacta_contexto_e_instrucciones():
    retriever = RetrieverFalso(CHUNKS)
    prompt, citas, _ = construir_prompt("¿Cuál es el límite de ruido?", retriever)
    assert retriever.pregunta == "¿Cuál es el límite de ruido?"
    assert "Pregunta: ¿Cuál es el límite de ruido?" in prompt
    assert "[2] El límite de ruido" in prompt
    assert SIN_INFORMACION in prompt
    assert ADVERTENCIA in prompt
    assert len(citas) == 2


def test_pregunta_vacia_lanza_error():
    with pytest.raises(ValueError):
        construir_prompt("   ", RetrieverFalso(CHUNKS))


def test_extraer_citas_separa_validas_e_inventadas():
    validas, invalidas = extraer_citas("Usa tu candado [1]. El ruido máximo es 85 dB(A) [2][9].",
                                       {1: "a.md", 2: "b.md"})
    assert validas == {1: "a.md", 2: "b.md"}
    assert invalidas == [9]


def test_responder_resuelve_citas_e_ids():
    modelo = FakeListChatModel(responses=[f"El límite es 85 dB(A) [2]. {ADVERTENCIA}"])
    resultado = responder("¿Límite de ruido?", modelo=modelo, retriever=RetrieverFalso(CHUNKS))
    assert resultado["citas_usadas"] == {2: "ds594_condiciones_sanitarias.md"}
    assert resultado["citas_invalidas"] == []
    assert resultado["ids_recuperados"] == ["pts_gen_002_bloqueo_2", "ds594_condiciones_sanitarias_3"]
    assert resultado["sin_informacion"] is False


def test_responder_detecta_que_el_modelo_no_tenia_informacion():
    modelo = FakeListChatModel(responses=[f"{SIN_INFORMACION} {ADVERTENCIA}"])
    resultado = responder("¿Vacaciones?", modelo=modelo, retriever=RetrieverFalso(CHUNKS))
    assert resultado["sin_informacion"] is True
    assert resultado["citas_usadas"] == {}
