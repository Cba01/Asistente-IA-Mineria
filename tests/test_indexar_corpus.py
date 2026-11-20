"""Pruebas del chunking del corpus. No llaman a la API ni crean el índice."""
from src.indexar_corpus import cargar_corpus, partir_en_chunks, separar_secciones, verificar_chunks

DOC_PRUEBA = """# PTS-PRUEBA · Documento de prueba

Aviso que no se indexa.

## Primera sección

Texto de la primera sección.

## Segunda sección

Texto de la segunda sección.
"""


def test_corpus_tiene_al_menos_5_documentos():
    assert len(cargar_corpus()) >= 5


def test_cada_chunk_tiene_fuente_y_numero():
    chunks, _ = partir_en_chunks(cargar_corpus())
    for c in chunks:
        assert c.metadata["fuente"].endswith(".md")
        assert c.metadata["seccion"]
        assert isinstance(c.metadata["chunk"], int)


def test_separar_secciones_descarta_la_intro():
    titulo, secciones = separar_secciones(DOC_PRUEBA)
    assert titulo == "PTS-PRUEBA · Documento de prueba"
    assert [s[0] for s in secciones] == ["Primera sección", "Segunda sección"]


def test_ids_predecibles_y_encabezado_en_cada_chunk():
    chunks, ids = partir_en_chunks([("pts_prueba.md", DOC_PRUEBA)])
    assert ids == ["pts_prueba_0", "pts_prueba_1"]
    assert chunks[1].page_content.startswith("PTS-PRUEBA · Documento de prueba\n## Segunda sección")
    assert "Aviso que no se indexa" not in chunks[0].page_content


def test_seccion_larga_se_divide_sin_perder_el_encabezado():
    pasos = "\n".join(f"{i}. Paso número {i} del procedimiento de prueba." for i in range(1, 30))
    doc = f"# PTS-LARGO\n\n## Pasos\n\n{pasos}"
    chunks, ids = partir_en_chunks([("largo.md", doc)], chunk_size=200, chunk_overlap=30)
    assert len(chunks) > 1
    assert all(c.page_content.startswith("PTS-LARGO\n## Pasos") for c in chunks)
    assert len(set(ids)) == len(ids)


def test_corpus_real_sin_problemas():
    chunks, ids = partir_en_chunks(cargar_corpus())
    assert verificar_chunks(chunks, ids) == []


def test_verificar_detecta_vacios_y_duplicados():
    from langchain_core.documents import Document
    chunks = [Document(page_content="hola"), Document(page_content="hola"), Document(page_content="  ")]
    problemas = verificar_chunks(chunks, ["a", "a", "b"])
    assert len(problemas) == 3
