"""Enrutamiento condicional con manejo de errores (U2.3, Bloques 19 y 20).

Clasifica la consulta y la envía por la ruta que corresponde:
- emergencia:    instrucciones inmediatas, breves y seguras.
- normativa:     respuesta breve sobre normativa, admitiendo cuando no está seguro de una cifra.
- procedimiento: la chain de tres pasos del Bloque 18 (ruta por defecto).

Manejo de errores en dos capas:
- Cada ruta tiene un fallback con un texto de respaldo, que no depende del modelo.
- procesar_consulta_segura() captura cualquier otro fallo (por ejemplo, en la clasificación),
  lo registra con logging y responde un mensaje seguro que incluye las instrucciones de emergencia.

Uso desde la raíz del repo:  python -m src.enrutamiento
"""
import logging

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableBranch, RunnableLambda, RunnablePassthrough

from src.cadena_tres_pasos import construir_cadena, crear_modelo

logger = logging.getLogger(__name__)

PLANTILLA_CLASIFICACION = PromptTemplate.from_template(
    "Clasifica la siguiente consulta de un trabajador de una faena minera en una sola palabra:\n"
    "- emergencia: describe un accidente, una persona lesionada o un peligro que está ocurriendo ahora.\n"
    "- normativa: pregunta qué dice una ley, decreto o norma.\n"
    "- procedimiento: pregunta cómo realizar una tarea de forma segura.\n"
    "Responde solo con esa palabra.\n\nConsulta: {consulta}"
)

PLANTILLA_EMERGENCIA = PromptTemplate.from_template(
    "Un trabajador de una faena minera en Chile reporta una posible emergencia. "
    "Responde en español, en texto plano, con un máximo de 5 instrucciones inmediatas, numeradas y muy breves: "
    "primero proteger la propia seguridad, luego dar aviso inmediato al supervisor o a la línea de emergencia "
    "de la faena, no mover a un lesionado salvo peligro inminente, y esperar al equipo de rescate. "
    "No des diagnósticos médicos.\n\nReporte: {consulta}"
)

PLANTILLA_NORMATIVA = PromptTemplate.from_template(
    "Responde en español, en texto plano y en un máximo de tres frases, esta consulta sobre normativa "
    "de seguridad minera en Chile. Si no estás seguro de un artículo o de una cifra exacta, dilo "
    "explícitamente y recomienda verificarlo en el texto oficial (por ejemplo DS 132, DS 594 o Ley 16.744)."
    "\n\nConsulta: {consulta}"
)

# ---------- Respuestas de respaldo (no dependen del modelo) ----------

INSTRUCCIONES_EMERGENCIA = (
    "1. Ponte a salvo antes de ayudar.\n"
    "2. Da aviso de inmediato a tu supervisor o a la línea de emergencia de la faena.\n"
    "3. Si es seguro hacerlo, detén el equipo involucrado.\n"
    "4. No muevas a un lesionado, salvo peligro inminente.\n"
    "5. Quédate en el lugar hasta que llegue el equipo de rescate."
)

RESPALDO_EMERGENCIA = (
    "El asistente no está disponible en este momento. Ante una emergencia:\n" + INSTRUCCIONES_EMERGENCIA
)

RESPALDO_NORMATIVA = (
    "No pudimos consultar la normativa en este momento. Revisa el texto oficial (DS 132, DS 594 o "
    "Ley 16.744) o consulta al departamento de prevención de riesgos de tu faena."
)

RESPALDO_PROCEDIMIENTO = (
    "No pudimos generar la orientación en este momento. Antes de realizar la tarea, revisa el PTS "
    "correspondiente, confecciona el AST y consulta a tu supervisor."
)

RESPUESTA_GENERAL_RESPALDO = (
    "No pudimos procesar tu consulta en este momento.\n"
    "Si se trata de una emergencia:\n" + INSTRUCCIONES_EMERGENCIA + "\n"
    "Para otras consultas, revisa el PTS de la tarea o consulta a tu supervisor."
)


# ---------- Construcción de los pasos ----------

def normalizar_categoria(texto: str) -> str:
    """Deja la categoría en minúsculas, sin espacios ni punto final ('Emergencia.\\n' -> 'emergencia')."""
    return texto.strip().strip(".").lower()


def construir_paso_clasificacion(modelo):
    return PLANTILLA_CLASIFICACION | modelo | StrOutputParser() | normalizar_categoria


def construir_cadena_emergencia(modelo):
    return PLANTILLA_EMERGENCIA | modelo | StrOutputParser()


def construir_cadena_normativa(modelo):
    return PLANTILLA_NORMATIVA | modelo | StrOutputParser()


def construir_ruta_segura(cadena, texto_respaldo: str):
    """Envuelve una ruta con un fallback: si la ruta lanza una excepción, devuelve el texto de respaldo."""
    return cadena.with_fallbacks([RunnableLambda(lambda _: texto_respaldo)])


def construir_cadena_con_enrutamiento(paso_clasificacion, cadena_emergencia=None,
                                      cadena_normativa=None, cadena_procedimiento=None):
    """Agrega la categoría a la entrada y elige la ruta. Las rutas que no se entregan
    quedan como RunnablePassthrough, para poder probar una ruta a la vez."""
    cadena_emergencia = cadena_emergencia or RunnablePassthrough()
    cadena_normativa = cadena_normativa or RunnablePassthrough()
    cadena_procedimiento = cadena_procedimiento or RunnablePassthrough()
    bifurcacion = RunnableBranch(
        (lambda x: x["categoria"] == "emergencia", cadena_emergencia),
        (lambda x: x["categoria"] == "normativa", cadena_normativa),
        cadena_procedimiento,  # ruta por defecto
    )
    return RunnablePassthrough.assign(categoria=paso_clasificacion) | bifurcacion


def construir_flujo(modelo):
    """Arma el flujo completo: clasificación más las tres rutas, cada una con su fallback."""
    return construir_cadena_con_enrutamiento(
        paso_clasificacion=construir_paso_clasificacion(modelo),
        cadena_emergencia=construir_ruta_segura(construir_cadena_emergencia(modelo), RESPALDO_EMERGENCIA),
        cadena_normativa=construir_ruta_segura(construir_cadena_normativa(modelo), RESPALDO_NORMATIVA),
        cadena_procedimiento=construir_ruta_segura(construir_cadena(modelo), RESPALDO_PROCEDIMIENTO),
    )


def procesar_consulta_segura(cadena, consulta: str) -> str:
    """Punto de entrada del flujo: nunca lanza una excepción.
    Si algo falla fuera de las rutas (por ejemplo, la clasificación), lo registra y responde
    un mensaje seguro que incluye las instrucciones de emergencia."""
    try:
        return cadena.invoke({"consulta": consulta})
    except Exception:
        logger.exception("Error procesando la consulta: %s", consulta)
        return RESPUESTA_GENERAL_RESPALDO


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    flujo = construir_flujo(crear_modelo())
    consultas = [
        "Se acaba de accidentar un compañero en la correa, tiene la mano atrapada.",
        "¿Qué dice el DS 594 sobre el límite de ruido?",
        "Mañana tengo que cambiar un rodillo de retorno en una pasarela a 3 metros.",
    ]
    for consulta in consultas:
        print(f"\n=== {consulta}\n")
        print(procesar_consulta_segura(flujo, consulta))