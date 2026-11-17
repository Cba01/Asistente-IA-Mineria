"""Chain de tres pasos (U2.3, Bloque 18): de la descripción de una tarea a un checklist de seguridad.

1. Analizar: identifica la tarea y sus peligros principales.
2. Recomendar: propone una medida de control para cada peligro.
3. Formatear: arma un checklist breve en texto plano, con advertencia final.

Uso desde la raíz del repo:  python -m src.cadena_tres_pasos
"""
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from src.consumir_gemini import MODELO

PLANTILLA_ANALISIS = PromptTemplate.from_template(
    "Eres un experto en prevención de riesgos en faenas mineras de Chile. "
    "Lee la consulta de un trabajador e identifica la tarea que va a realizar y sus 3 peligros principales. "
    "Responde en español: la tarea en la primera línea y luego un peligro por línea, sin explicaciones.\n\n"
    "Consulta: {consulta}"
)

PLANTILLA_RECOMENDACIONES = PromptTemplate.from_template(
    "Para la siguiente tarea y sus peligros, indica una medida de control concreta por cada peligro, "
    "usando terminología chilena (AST, PTS, permiso de trabajo, bloqueo de energías). "
    "Responde en español.\n\n{analisis}"
)

PLANTILLA_FORMATO = PromptTemplate.from_template(
    "Convierte estas medidas en un checklist de máximo 5 puntos numerados, en texto plano "
    "(sin markdown, sin ** ni #), para que un trabajador lo revise antes de empezar. "
    "Termina con esta frase: 'Esta orientación no reemplaza el PTS de la faena ni las instrucciones "
    "del supervisor.'\n\n{recomendaciones}"
)


def construir_cadena(modelo):
    """Arma la chain de tres pasos con el modelo que recibe (el real o uno falso, para las pruebas).
    No la ejecuta: solo la deja lista para usar con .invoke()."""
    return (
        PLANTILLA_ANALISIS | modelo | StrOutputParser()
        | (lambda analisis: {"analisis": analisis})
        | PLANTILLA_RECOMENDACIONES | modelo | StrOutputParser()
        | (lambda recomendaciones: {"recomendaciones": recomendaciones})
        | PLANTILLA_FORMATO | modelo | StrOutputParser()
    )


def crear_modelo():
    """Crea el modelo de Gemini para LangChain, con el mismo GEMINI_MODEL del .env.
    No se pasa temperature: gemini-3.5-flash-lite usa valores de muestreo fijos y lo ignora."""
    return ChatGoogleGenerativeAI(model=MODELO, timeout=60, max_retries=3)


if __name__ == "__main__":
    cadena = construir_cadena(crear_modelo())
    consulta = ("Mañana tengo que cambiar un rodillo de retorno de la correa del chancador primario, "
                "que está en una pasarela a unos 3 metros de altura.")
    print(cadena.invoke({"consulta": consulta}))