"""Pruebas de la instrumentación de latencia y costo. No llaman a la API."""
import json

from langchain_core.documents import Document
from langchain_core.messages import AIMessage

from src.registro_rag import (calcular_costo, guardar_registro, leer_registros, medir,
                              registrar_consulta, resumir)


class EmbeddingsFalsos:
    def embed_query(self, texto):
        return [0.1, 0.2, 0.3]


class VectorstoreFalso:
    def similarity_search_by_vector(self, vector, k):
        return [Document(id=f"doc_{i}", page_content=f"Texto {i}", metadata={"fuente": "a.md"})
                for i in range(k)]


class ModeloFalso:
    model = "gemini-3.5-flash-lite"

    def __init__(self, con_uso=True):
        self.con_uso = con_uso
        self.prompt = None

    def invoke(self, prompt):
        self.prompt = prompt
        uso = {"input_tokens": 200, "output_tokens": 40, "total_tokens": 240} if self.con_uso else None
        return AIMessage(content="Respuesta [1].", usage_metadata=uso)


def test_medir_guarda_la_etapa_aunque_haya_error():
    tiempos = {}
    try:
        with medir(tiempos, "etapa"):
            raise RuntimeError
    except RuntimeError:
        pass
    assert tiempos["etapa"] >= 0


def test_calcular_costo_con_tarifa_conocida_y_desconocida():
    tokens = {"input_tokens": 1_000_000, "output_tokens": 1_000_000}
    assert calcular_costo(tokens, "gemini-3.5-flash-lite") == 0.30 + 2.50
    assert calcular_costo(tokens, "modelo-desconocido") is None
    assert calcular_costo(None, "gemini-3.5-flash-lite") is None


def test_registro_tiene_las_claves_y_etapas_esperadas():
    r = registrar_consulta("¿pregunta?", 3, EmbeddingsFalsos(), VectorstoreFalso(), ModeloFalso())
    for clave in ("timestamp", "pregunta", "k", "tiempos_ms", "tiempo_total_ms", "tokens", "costo_usd"):
        assert clave in r
    assert set(r["tiempos_ms"]) == {"embed_pregunta", "busqueda_vectorial", "generacion"}
    assert r["ids_recuperados"] == ["doc_0", "doc_1", "doc_2"]
    assert r["tokens"]["input_tokens"] == 200
    assert r["costo_usd"] > 0


def test_mas_k_significa_prompt_mas_largo():
    r3 = registrar_consulta("p", 3, EmbeddingsFalsos(), VectorstoreFalso(), ModeloFalso())
    r6 = registrar_consulta("p", 6, EmbeddingsFalsos(), VectorstoreFalso(), ModeloFalso())
    assert r6["caracteres_prompt"] > r3["caracteres_prompt"]


def test_sin_usage_metadata_guarda_none():
    r = registrar_consulta("p", 3, EmbeddingsFalsos(), VectorstoreFalso(), ModeloFalso(con_uso=False))
    assert r["tokens"] is None
    assert r["costo_usd"] is None


def test_guardar_y_leer_jsonl(tmp_path):
    archivo = tmp_path / "registros.jsonl"
    r = registrar_consulta("p", 3, EmbeddingsFalsos(), VectorstoreFalso(), ModeloFalso())
    guardar_registro(r, archivo)
    guardar_registro(r, archivo)
    lineas = archivo.read_text(encoding="utf-8").splitlines()
    assert len(lineas) == 2 and json.loads(lineas[0])["pregunta"] == "p"
    assert len(leer_registros(archivo)) == 2
    assert "p" in resumir(leer_registros(archivo))
