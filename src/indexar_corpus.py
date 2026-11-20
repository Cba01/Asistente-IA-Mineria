"""Indexación del corpus de seguridad minera en Chroma (U2.5, Bloque 24).

Toma los documentos de la carpeta corpus/, los parte en chunks, calcula un
embedding real por chunk con Gemini y los guarda en vectorstore/ (en disco),
para que los scripts de consulta los reutilicen sin volver a indexar.

Cada chunk se guarda con:
- metadata "fuente": nombre del archivo de origen (para citarlo en la respuesta),
- metadata "chunk": número del chunk dentro de su documento,
- un id explícito y predecible, por ejemplo "pts_gen_002_bloqueo_0"
  (necesario para evaluar la recuperación en el Bloque 27).

Uso desde la raíz del repo:
    python -m src.indexar_corpus              # indexa (borra y reconstruye el índice)
    python -m src.indexar_corpus --comparar   # compara tamaños de chunk, sin llamar a la API
"""
import argparse
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

load_dotenv()

# Rutas absolutas, calculadas desde la ubicación de este archivo: así el índice
# es siempre el mismo sin importar desde qué carpeta se ejecute el script.
RAIZ = Path(__file__).resolve().parent.parent
CARPETA_CORPUS = RAIZ / "corpus"
PERSIST_DIR = RAIZ / "vectorstore"

COLECCION = "seguridad_minera"
MODELO_EMBEDDINGS = "models/gemini-embedding-001"

# Elegido con --comparar (ver docs/decision_chunking.md). Es el tamaño máximo
# del CUERPO de cada chunk; a eso se suma el encabezado de contexto.
CHUNK_SIZE = 500
CHUNK_OVERLAP = 80


# ---------- 1. Corpus ----------

def cargar_corpus(carpeta: Path = CARPETA_CORPUS) -> list[tuple[str, str]]:
    """Lee todos los .md de la carpeta. Devuelve una lista de (nombre_archivo, texto)."""
    archivos = sorted(carpeta.glob("*.md"))
    if not archivos:
        raise FileNotFoundError(f"No hay archivos .md en {carpeta}")
    return [(a.name, a.read_text(encoding="utf-8")) for a in archivos]


# ---------- 2. Chunking ----------

def separar_secciones(texto: str) -> tuple[str, list[tuple[str, str]]]:
    """Separa un documento markdown en (titulo, [(titulo_seccion, cuerpo), ...]).

    El texto antes de la primera sección "## " (título y aviso de documento
    ficticio o resumen) no se indexa como chunk propio: no responde ninguna
    pregunta y solo competiría con los chunks útiles en la búsqueda.
    """
    bloques = ("\n" + texto.strip()).split("\n## ")
    intro = bloques[0].strip()
    titulo = intro.splitlines()[0].lstrip("# ").strip() if intro else ""
    secciones = []
    for bloque in bloques[1:]:
        titulo_seccion, _, cuerpo = bloque.partition("\n")
        if cuerpo.strip():
            secciones.append((titulo_seccion.strip(), cuerpo.strip()))
    return titulo, secciones


def partir_en_chunks(documentos, chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP):
    """Parte cada documento por secciones y devuelve (chunks, ids).

    - Cada sección se parte por separado: un chunk nunca mezcla dos secciones.
    - Si una sección es más larga que chunk_size, el splitter la divide en
      varias piezas (cortando entre párrafos o líneas, con overlap).
    - Cada chunk empieza con el título del documento y de su sección, para que
      una pieza como "6. Verificar energía cero..." no pierda de qué
      procedimiento es (ni para el embedding ni para el modelo que la lea).
    - El id combina el nombre del archivo y el número de chunk: "pts_gen_002_bloqueo_3".
    """
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    chunks, ids = [], []
    for nombre, texto in documentos:
        base = Path(nombre).stem
        titulo, secciones = separar_secciones(texto)
        n = 0
        for titulo_seccion, cuerpo in secciones:
            for pieza in splitter.split_text(cuerpo):
                contenido = f"{titulo}\n## {titulo_seccion}\n\n{pieza}"
                chunks.append(Document(
                    page_content=contenido,
                    metadata={"fuente": nombre, "seccion": titulo_seccion, "chunk": n},
                ))
                ids.append(f"{base}_{n}")
                n += 1
    return chunks, ids


def verificar_chunks(chunks, ids) -> list[str]:
    """Revisión local, sin costo: chunks vacíos, textos repetidos o ids repetidos."""
    problemas = []
    vacios = [ids[i] for i, c in enumerate(chunks) if not c.page_content.strip()]
    if vacios:
        problemas.append(f"Chunks vacíos: {vacios}")
    textos = [c.page_content for c in chunks]
    if len(textos) != len(set(textos)):
        problemas.append("Hay chunks con texto duplicado")
    if len(ids) != len(set(ids)):
        problemas.append("Hay ids duplicados")
    return problemas


def comparar_tamanos(documentos, tamanos=(300, 500, 800)) -> None:
    """Muestra cuántos chunks genera cada tamaño y un ejemplo, para elegir con evidencia."""
    for tamano in tamanos:
        chunks, _ = partir_en_chunks(documentos, chunk_size=tamano, chunk_overlap=int(tamano * 0.16))
        largos = [len(c.page_content) for c in chunks]
        print(f"\n=== chunk_size={tamano} -> {len(chunks)} chunks "
              f"(largo mín {min(largos)}, prom {sum(largos) // len(largos)}, máx {max(largos)}) ===")
        divididas = len(chunks) - sum(len(separar_secciones(t)[1]) for _, t in documentos)
        print(f"Secciones que tuvieron que dividirse en más de un chunk: {divididas} piezas extra")
        ejemplo = [c for c in chunks if c.metadata["fuente"].startswith("pts_gen_002")
                   and c.metadata["seccion"] == "Pasos del bloqueo"]
        for c in ejemplo:
            print(f"--- ({len(c.page_content)} caracteres)")
            print(c.page_content)


# ---------- 3 y 4. Embeddings y persistencia ----------

def crear_embeddings():
    from langchain_google_genai import GoogleGenerativeAIEmbeddings
    return GoogleGenerativeAIEmbeddings(model=MODELO_EMBEDDINGS)


def con_reintentos(operacion, max_intentos=4, espera_inicial=5):
    """Repite la operación solo si el error es de cuota (429); los demás errores se lanzan."""
    espera = espera_inicial
    for intento in range(1, max_intentos + 1):
        try:
            return operacion()
        except Exception as error:
            mensaje = str(error)
            es_limite = "429" in mensaje or "RESOURCE_EXHAUSTED" in mensaje
            if not es_limite or intento == max_intentos:
                raise
            print(f"Límite de peticiones alcanzado. Reintento {intento} de {max_intentos - 1} en {espera} s...")
            time.sleep(espera)
            espera *= 2


def indexar(chunks, ids, embeddings):
    """Borra la colección anterior y la reconstruye con los chunks actuales.

    Se borra primero porque, si un documento cambia o se elimina, sus chunks
    viejos quedarían en el índice. Con un corpus chico, reconstruir es barato.
    """
    from langchain_chroma import Chroma

    vectorstore = Chroma(
        collection_name=COLECCION,
        embedding_function=embeddings,
        persist_directory=str(PERSIST_DIR),
    )
    vectorstore.delete_collection()

    return con_reintentos(lambda: Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        ids=ids,
        collection_name=COLECCION,
        persist_directory=str(PERSIST_DIR),
    ))


# ---------- 5. Reconexión (la usan los scripts de consulta) ----------

def cargar_vectorstore(embeddings=None):
    """Se reconecta al índice ya guardado, sin recalcular ningún embedding."""
    from langchain_chroma import Chroma

    return Chroma(
        collection_name=COLECCION,
        embedding_function=embeddings or crear_embeddings(),
        persist_directory=str(PERSIST_DIR),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Indexa el corpus de seguridad minera en Chroma.")
    parser.add_argument("--comparar", action="store_true",
                        help="Solo compara tamaños de chunk (no llama a la API).")
    args = parser.parse_args()

    documentos = cargar_corpus()
    print(f"Corpus: {len(documentos)} documentos en {CARPETA_CORPUS.name}/")

    if args.comparar:
        comparar_tamanos(documentos)
        return

    chunks, ids = partir_en_chunks(documentos)
    problemas = verificar_chunks(chunks, ids)
    if problemas:
        print("No se indexó. Problemas en los chunks:")
        for p in problemas:
            print(" -", p)
        sys.exit(1)
    print(f"Chunks: {len(chunks)} (chunk_size={CHUNK_SIZE}, chunk_overlap={CHUNK_OVERLAP})")

    try:
        indexar(chunks, ids, crear_embeddings())
    except Exception as error:
        mensaje = str(error)
        if "429" in mensaje or "RESOURCE_EXHAUSTED" in mensaje:
            print("Se agotaron los reintentos por límite de peticiones. Espera un minuto y vuelve a ejecutar.")
        elif "API key" in mensaje or "401" in mensaje or "403" in mensaje:
            print('La API rechazó la clave. Revisa GEMINI_API_KEY en tu ".env".')
        else:
            print("No se pudo indexar el corpus:", type(error).__name__)
            print("Detalle técnico:", mensaje)
        sys.exit(1)

    # Verificación real de la persistencia: una conexión nueva al índice en disco.
    total = cargar_vectorstore()._collection.count()
    print(f"Indexados {total} chunks en {PERSIST_DIR.name}/ (colección '{COLECCION}')")
    if total != len(chunks):
        print(f"Atención: se esperaban {len(chunks)} chunks.")
        sys.exit(1)


if __name__ == "__main__":
    main()
