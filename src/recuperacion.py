"""Recuperación semántica y respuesta con fuente citada (U2.5, Bloque 26).

Flujo para cada pregunta:
1. Se reconecta al índice ya guardado en vectorstore/ (no vuelve a indexar).
2. Recupera los K chunks más parecidos a la pregunta, por significado.
3. Arma un prompt con esos chunks numerados [1], [2]... y la instrucción de
   citar cada afirmación y de reconocer cuando el contexto no alcanza.
4. El modelo responde, y el programa traduce cada número citado a su archivo
   de origen (y detecta números que el modelo haya inventado).

Uso desde la raíz del repo:  python -m src.recuperacion
Requiere haber corrido antes:  python -m src.indexar_corpus
"""
import re

from dotenv import load_dotenv

load_dotenv()

# Elegido con la evaluación del Bloque 27 (docs/resultados_evaluacion.txt):
# con k=3, 4 y 5 el recall es el mismo (0.964), así que k=3 da el mejor F1
# y envía menos contexto al modelo en cada consulta.
K = 3

SIN_INFORMACION = "Los documentos disponibles no tienen información suficiente para responder esta pregunta."
ADVERTENCIA = ("Recuerda que esta orientación no reemplaza el procedimiento oficial "
               "de la faena ni las instrucciones del supervisor.")

PROMPT_RAG = f"""Eres un asistente de seguridad para una faena minera en Chile. Responde en español, \
de forma breve y en texto plano, sin markdown.

Responde la pregunta usando SOLO el contexto de abajo. Cita la fuente de cada afirmación con \
su número entre corchetes, como [1] o [2][3]. No agregues datos que no estén en el contexto, \
aunque los conozcas.

El contexto puede usar palabras distintas a las de la pregunta: relaciona los términos cuando el \
propio contexto lo permita (por ejemplo, si el contexto dice que un equipo pertenece a una categoría, \
aplica a ese equipo lo que el contexto dice de la categoría). Si el contexto responde solo una parte \
de la pregunta, responde esa parte y di qué falta.

Solo si ningún fragmento del contexto se relaciona con la pregunta, responde exactamente: \
"{SIN_INFORMACION}"

Termina siempre con esta frase: "{ADVERTENCIA}"

Contexto:
{{contexto}}

Pregunta: {{pregunta}}

Respuesta:"""


# ---------- Recuperación ----------

def crear_retriever(k: int = K, vectorstore=None):
    """Retriever sobre el índice persistido. Se reconecta con Chroma(persist_directory=...),
    nunca con from_documents, para no recalcular embeddings en cada pregunta."""
    if vectorstore is None:
        from src.indexar_corpus import cargar_vectorstore
        vectorstore = cargar_vectorstore()
    return vectorstore.as_retriever(search_kwargs={"k": k})


def formatear_contexto(chunks_recuperados):
    """Arma el contexto numerado para el prompt y el mapa número -> archivo de origen."""
    lineas, citas = [], {}
    for i, doc in enumerate(chunks_recuperados, start=1):
        lineas.append(f"[{i}] {doc.page_content}")
        citas[i] = doc.metadata.get("fuente", "desconocida")
    return "\n\n".join(lineas), citas


def construir_prompt(pregunta: str, retriever=None, k: int = K):
    """Recupera los chunks y arma el prompt. Devuelve (prompt, citas, chunks)."""
    if not pregunta or not pregunta.strip():
        raise ValueError("La pregunta no puede estar vacía.")
    retriever = retriever or crear_retriever(k)
    chunks = retriever.invoke(pregunta)
    contexto, citas = formatear_contexto(chunks)
    prompt = PROMPT_RAG.format(contexto=contexto, pregunta=pregunta.strip())
    return prompt, citas, chunks


# ---------- Citas ----------

def extraer_citas(respuesta: str, citas: dict) -> tuple[dict, list[int]]:
    """Busca los [n] de la respuesta. Devuelve (citas_validas {n: fuente}, numeros_invalidos).

    Un número inválido es uno que el modelo citó pero que no estaba en el contexto,
    por ejemplo [9] cuando solo se le pasaron 4 chunks: es una cita inventada.
    """
    numeros = sorted({int(n) for n in re.findall(r"\[(\d+)\]", respuesta)})
    validas = {n: citas[n] for n in numeros if n in citas}
    invalidas = [n for n in numeros if n not in citas]
    return validas, invalidas


# ---------- Respuesta completa ----------

def texto_de_salida(contenido) -> str:
    """Con Gemini, el contenido a veces llega como lista de bloques en vez de str."""
    if isinstance(contenido, str):
        return contenido
    if isinstance(contenido, list):
        return "".join(b.get("text", "") for b in contenido
                       if isinstance(b, dict) and b.get("type") == "text")
    return str(contenido)


def responder(pregunta: str, modelo=None, retriever=None, k: int = K) -> dict:
    """Corre el flujo RAG completo para una pregunta y devuelve un dict con
    la respuesta, las citas resueltas y los ids de los chunks recuperados."""
    if modelo is None:
        from src.cadena_tres_pasos import crear_modelo
        modelo = crear_modelo()
    prompt, citas, chunks = construir_prompt(pregunta, retriever, k)
    respuesta = texto_de_salida(modelo.invoke(prompt).content)
    validas, invalidas = extraer_citas(respuesta, citas)
    return {
        "pregunta": pregunta,
        "respuesta": respuesta,
        "ids_recuperados": [c.id for c in chunks],
        "citas": citas,
        "citas_usadas": validas,
        "citas_invalidas": invalidas,
        "sin_informacion": SIN_INFORMACION in respuesta,
    }


def mostrar(resultado: dict) -> None:
    print(f"\n=== {resultado['pregunta']}")
    print("Chunks recuperados:", ", ".join(resultado["ids_recuperados"]))
    print("\n" + resultado["respuesta"].strip())
    if resultado["citas_usadas"]:
        print("\nFuentes citadas:")
        for n, fuente in resultado["citas_usadas"].items():
            print(f"  [{n}] {fuente}")
    if resultado["citas_invalidas"]:
        print(f"ATENCIÓN: citas que no existen en el contexto: {resultado['citas_invalidas']}")
    if resultado["sin_informacion"]:
        print("(El modelo reconoció que el contexto no alcanzaba.)")


if __name__ == "__main__":
    import sys
    import time

    # Con argumentos, responde solo esas preguntas:
    #   python -m src.recuperacion "¿Cuándo puedo entrar a un estanque a revisar si hay gases?"
    preguntas = sys.argv[1:] or [
        # Dos preguntas de temas distintos: los chunks recuperados deben cambiar.
        "¿Qué tengo que hacer antes de cambiar un rodillo de la correa?",
        "¿Cuál es el límite de ruido para una jornada de 8 horas?",
        # Pregunta con otras palabras: no dice "espacio confinado" ni "atmósfera", como el documento.
        "¿Cuándo puedo entrar a un estanque a revisar si hay gases?",
        # Una pregunta que el corpus NO puede responder: debe decir que no tiene información.
        "¿Cuántos días de vacaciones le corresponden a un trabajador minero?",
    ]
    for i, pregunta in enumerate(preguntas):
        if i:
            time.sleep(5)  # pausa para no topar el límite de peticiones por minuto
        mostrar(responder(pregunta))
