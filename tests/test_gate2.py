"""Los 4 criterios no compensables del Gate 2, verificados sobre el servicio real.

El retriever y el modelo se reemplazan por versiones falsas (sin API), pero el resto
del camino es el del servicio: version aprobada, filtro, mensajes, citas, logs y supervisión.

Uso:  python -m pytest tests/test_gate2.py -v
"""
from langchain_core.documents import Document
from langchain_core.language_models import FakeListChatModel
from langgraph.types import Command

import pytest

from src import logging_rag
from src import servicio_rag
from src.grafo_supervision import construir_grafo, nuevo_config
from src.recuperacion import ADVERTENCIA
from src.registro_prompts import RegistroDePrompts

# Datos sensibles de prueba que NUNCA deben aparecer en los logs.
CORREO = "ana.perez@example.com"
TRABAJADOR = "T-2045"
PREGUNTA = (f"¿El trabajador {TRABAJADOR} puede intervenir la correa sin bloquearla? "
            f"Mi correo es {CORREO}")

CHUNKS = [
    Document(id="pts_gen_002_bloqueo_4", page_content="5. Verificar energía cero antes de intervenir.",
             metadata={"fuente": "pts_gen_002_bloqueo.md"}),
    Document(id="pts_mec_014_correas_5",
             page_content="Está prohibido intervenir una correa en movimiento.",
             metadata={"fuente": "pts_mec_014_correas.md"}),
]


class RetrieverFalso:
    def invoke(self, pregunta):
        return CHUNKS


@pytest.fixture
def servicio(tmp_path, monkeypatch):
    """Logs a un archivo temporal real y la versión de prompt actual marcada como aprobada."""
    archivo_log = tmp_path / "rag.jsonl"
    logging_rag.configurar_logger(archivo=archivo_log, consola=False)
    monkeypatch.setattr(servicio_rag, "leer_activas",
                        lambda: {"prompt_rag": logging_rag.PROMPT_HUELLA})

    def ejecutar(respuesta_modelo=f"No, primero verifica energía cero [1]. {ADVERTENCIA}"):
        modelo = FakeListChatModel(responses=[respuesta_modelo])
        return servicio_rag.responder(PREGUNTA, retriever=RetrieverFalso(), modelo=modelo)

    return ejecutar, archivo_log


def test_1_pipeline_sin_excepciones(servicio):
    ejecutar, _ = servicio
    resultado = ejecutar()
    assert resultado["respuesta"].strip()
    assert resultado["trace_id"].startswith("trace-")


def test_2_respuesta_cita_fuente(servicio):
    ejecutar, _ = servicio
    resultado = ejecutar()
    assert resultado["fuentes"] == ["pts_gen_002_bloqueo.md"]
    assert all(f in resultado["respuesta"] for f in resultado["fuentes"])


def test_2b_si_el_modelo_no_cita_igual_se_muestran_los_documentos(servicio):
    ejecutar, _ = servicio
    resultado = ejecutar(f"No, verifica energía cero. {ADVERTENCIA}")
    assert "Documentos consultados" in resultado["respuesta"]
    assert all(c.metadata["fuente"] in resultado["respuesta"] for c in CHUNKS)


def test_3_logs_sin_contenido_crudo(servicio):
    ejecutar, archivo_log = servicio
    ejecutar()
    texto_logs = archivo_log.read_text(encoding="utf-8")
    assert texto_logs.strip(), "no se escribió ningún log"
    for sensible in (CORREO, TRABAJADOR, PREGUNTA, "verifica energía cero"):
        assert sensible not in texto_logs, f"'{sensible}' aparece en los logs"


def test_4_supervision_pausa_y_reanuda(tmp_path):
    registro = RegistroDePrompts(tmp_path / "registro.json")
    a = registro.registrar("prompt_rag", "versión A", "yo", "a", "m")
    b = registro.registrar("prompt_rag", "versión B", "yo", "b", "m")
    app = construir_grafo(registro, tmp_path / "activa.json")
    config = nuevo_config()
    pausado = app.invoke({"nombre": "prompt_rag", "huella_actual": a["huella"],
                          "huella_nueva": b["huella"], "aprobado": False}, config=config)
    assert "__interrupt__" in pausado
    final = app.invoke(Command(resume=True), config=config)
    assert "__interrupt__" not in final and final["aprobado"] is True


def test_servicio_no_responde_con_un_prompt_no_aprobado(monkeypatch):
    monkeypatch.setattr(servicio_rag, "leer_activas", lambda: {"prompt_rag": "otra_version"})
    with pytest.raises(servicio_rag.VersionNoAprobada):
        servicio_rag.responder(PREGUNTA, retriever=RetrieverFalso(),
                               modelo=FakeListChatModel(responses=["x"]))


def test_la_version_aprobada_en_el_repo_es_la_del_codigo():
    """Si esto falla, se cambió el prompt sin registrarlo y aprobarlo."""
    servicio_rag.verificar_version_prompt()


def test_actualizacion_incremental_de_un_documento(tmp_path, monkeypatch):
    from langchain_core.embeddings import DeterministicFakeEmbedding
    from src import indexar_corpus as ic

    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "a.md").write_text("# A\n\n## Uno\n\nTexto uno.\n\n## Dos\n\nTexto dos.", encoding="utf-8")
    (corpus / "b.md").write_text("# B\n\n## Uno\n\nOtro texto.", encoding="utf-8")
    monkeypatch.setattr(ic, "CARPETA_CORPUS", corpus)
    monkeypatch.setattr(ic, "PERSIST_DIR", tmp_path / "vs")
    monkeypatch.setattr(ic, "COLECCION", "prueba_incremental")
    emb = DeterministicFakeEmbedding(size=8)
    chunks, ids = ic.partir_en_chunks(ic.cargar_corpus(corpus))
    ic.indexar(chunks, ids, emb)
    assert ic.cargar_vectorstore(emb)._collection.count() == 3

    (corpus / "a.md").write_text("# A\n\n## Uno\n\nTexto uno corregido.", encoding="utf-8")
    assert ic.actualizar_documento("a.md", emb) == (2, 1)
    vs = ic.cargar_vectorstore(emb)
    assert sorted(vs.get()["ids"]) == ["a_0", "b_0"]
    assert "corregido" in vs.get(ids=["a_0"])["documents"][0]

    (corpus / "b.md").unlink()
    assert ic.actualizar_documento("b.md", emb) == (1, 0)
    assert ic.cargar_vectorstore(emb).get()["ids"] == ["a_0"]
