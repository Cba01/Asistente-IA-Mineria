"""Enrutamiento condicional (U2.3, Bloque 19): clasifica la consulta y la envía por la ruta que corresponde.

- emergencia:    instrucciones inmediatas, breves y seguras.
- normativa:     respuesta breve sobre normativa, admitiendo cuando no está seguro de una cifra.
- procedimiento: la chain de tres pasos del Bloque 18 (ruta por defecto).

Uso desde la raíz del repo:  python -m src.enrutamiento
"""
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableBranch, RunnablePassthrough

from src.cadena_tres_pasos import construir_cadena, crear_modelo

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


def normalizar_categoria(texto: str) -> str:
    """Deja la categoría en minúsculas, sin espacios ni punto final ('Emergencia.\\n' -> 'emergencia')."""
    return texto.strip().strip(".").lower()


def construir_paso_clasificacion(modelo):
    return PLANTILLA_CLASIFICACION | modelo | StrOutputParser() | normalizar_categoria


def construir_cadena_emergencia(modelo):
    return PLANTILLA_EMERGENCIA | modelo | StrOutputParser()


def construir_cadena_normativa(modelo):
    return PLANTILLA_NORMATIVA | modelo | StrOutputParser()


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
    """Arma el flujo completo con un mismo modelo para todos los pasos."""
    return construir_cadena_con_enrutamiento(
        paso_clasificacion=construir_paso_clasificacion(modelo),
        cadena_emergencia=construir_cadena_emergencia(modelo),
        cadena_normativa=construir_cadena_normativa(modelo),
        cadena_procedimiento=construir_cadena(modelo),
    )


if __name__ == "__main__":
    flujo = construir_flujo(crear_modelo())
    consultas = [
        "Se acaba de accidentar un compañero en la correa, tiene la mano atrapada.",
        "¿Qué dice el DS 594 sobre el límite de ruido?",
        "Mañana tengo que cambiar un rodillo de retorno en una pasarela a 3 metros.",
    ]
    for consulta in consultas:
        print(f"\n=== {consulta}\n")
        print(flujo.invoke({"consulta": consulta}))