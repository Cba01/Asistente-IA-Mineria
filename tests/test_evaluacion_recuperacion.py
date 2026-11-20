"""Pruebas de las métricas de recuperación. No llaman a la API."""
from langchain_core.documents import Document

from src.evaluacion_recuperacion import (CASOS_EVALUACION, evaluar, f1, precision_at_k,
                                         promediar, recall_at_k, recuperar_rankings,
                                         validar_etiquetas)
from src.indexar_corpus import cargar_corpus, partir_en_chunks


def test_precision_y_recall_del_ejemplo_del_curso():
    assert precision_at_k(["doc2", "doc0", "doc4"], {"doc0"}) == 1 / 3
    assert recall_at_k(["doc2", "doc0", "doc4"], {"doc0"}) == 1.0


def test_recall_parcial_con_dos_relevantes():
    assert recall_at_k(["a", "x", "y"], {"a", "b"}) == 0.5


def test_casos_borde_sin_division_por_cero():
    assert precision_at_k([], {"doc0"}) == 0.0
    assert recall_at_k(["doc0"], set()) is None
    assert promediar([None, None]) == 0.0
    assert promediar([1.0, None, 0.0]) == 0.5
    assert f1(0.0, 0.0) == 0.0


def test_las_etiquetas_existen_en_el_corpus():
    _, ids = partir_en_chunks(cargar_corpus())
    assert validar_etiquetas(CASOS_EVALUACION, ids) == []


def test_validar_detecta_id_mal_escrito():
    casos = [{"pregunta": "p", "ids_relevantes": {"pts_gen_002_bloque_2"}}]
    assert len(validar_etiquetas(casos, ["pts_gen_002_bloqueo_2"])) == 1


def test_conjunto_tiene_entre_8_y_15_casos():
    assert 8 <= len(CASOS_EVALUACION) <= 15


def test_subir_k_no_baja_el_recall():
    casos = [{"pregunta": "p", "ids_relevantes": {"c"}}]
    rankings = {"p": ["a", "b", "c", "d", "e"]}
    _, p3, r3 = evaluar(casos, rankings, 3)
    _, p5, r5 = evaluar(casos, rankings, 5)
    assert r5 >= r3 and p5 <= p3


def test_recuperar_rankings_usa_los_ids_de_los_documentos():
    class RetrieverFalso:
        def invoke(self, pregunta):
            return [Document(id="x_0", page_content="a"), Document(id="y_1", page_content="b")]

    casos = [{"pregunta": "p1", "ids_relevantes": set()}]
    assert recuperar_rankings(casos, RetrieverFalso(), pausa=0) == {"p1": ["x_0", "y_1"]}
