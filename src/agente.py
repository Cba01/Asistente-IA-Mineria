"""Agente de seguridad minera con herramientas (U2.4).

El agente decide por sí mismo qué herramienta usar según la pregunta, o si no necesita ninguna.
Los datos de equipos y trabajadores son FICTICIOS, solo para el ejercicio.

Uso desde la raíz del repo:  python -m src.agente
"""
from datetime import date

from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool

from src.cadena_tres_pasos import crear_modelo

# ---------- Datos ficticios de la faena ----------

EQUIPOS = {
    "CT-01": {"nombre": "Correa transportadora CT-01 (chancado primario)", "estado": "operativa",
              "bloqueado": False, "proxima_mantencion": "2026-12-02"},
    "CT-02": {"nombre": "Correa transportadora CT-02 (acopio)", "estado": "operativa",
              "bloqueado": False, "proxima_mantencion": "2026-11-01"},
    "CH-01": {"nombre": "Chancador primario CH-01", "estado": "en mantención",
              "bloqueado": True, "proxima_mantencion": "2026-11-20"},
}

TRABAJADORES = {
    "T-1023": {"trabajo en altura": "2027-03-10", "bloqueo de energías": "2026-08-30"},
    "T-2045": {"trabajo en altura": "2026-12-01", "espacios confinados": "2027-05-20"},
}


def estado_vigencia(fecha_vencimiento: str, hoy: date = None) -> str:
    """Devuelve 'vigente' o 'vencido' comparando la fecha con hoy (o con la fecha indicada)."""
    hoy = hoy or date.today()
    return "vigente" if date.fromisoformat(fecha_vencimiento) >= hoy else "vencido"


# ---------- Herramientas ----------

@tool
def consultar_estado_equipo(codigo_equipo: str) -> str:
    """Consulta si un equipo de la faena está operativo, bloqueado o con la mantención vencida,
    a partir de su código (por ejemplo 'CT-01' o 'CH-01'). Usar cuando el trabajador pregunta
    si puede intervenir un equipo o en qué estado está."""
    codigo = codigo_equipo.strip().upper()
    equipo = EQUIPOS.get(codigo)
    if equipo is None:
        return f"No existe un equipo con el código {codigo} en el registro de la faena."
    mantencion = estado_vigencia(equipo["proxima_mantencion"])
    bloqueo = "BLOQUEADO" if equipo["bloqueado"] else "sin bloqueo"
    return (f"{equipo['nombre']}: {equipo['estado']}, {bloqueo}. "
            f"Mantención programada para {equipo['proxima_mantencion']} ({mantencion}).")


@tool
def consultar_certificaciones_trabajador(codigo_trabajador: str) -> str:
    """Consulta qué cursos de seguridad tiene vigentes o vencidos un trabajador (por ejemplo
    trabajo en altura o bloqueo de energías), a partir de su código (por ejemplo 'T-1023').
    Usar cuando se pregunta si un trabajador está habilitado para realizar una tarea."""
    codigo = codigo_trabajador.strip().upper()
    cursos = TRABAJADORES.get(codigo)
    if cursos is None:
        return f"No existe un trabajador con el código {codigo} en el registro."
    detalle = "; ".join(f"{curso}: {estado_vigencia(fecha)} (vence {fecha})"
                        for curso, fecha in cursos.items())
    return f"Certificaciones de {codigo}: {detalle}."


HERRAMIENTAS = [consultar_estado_equipo, consultar_certificaciones_trabajador]

PROMPT_AGENTE = ChatPromptTemplate.from_messages([
    ("system",
     "Eres un asistente de seguridad para una faena minera en Chile. Responde siempre en español, "
     "de forma breve y en texto plano, sin markdown. Usa las herramientas cuando la pregunta requiera datos de un equipo o de un "
     "trabajador. Nunca inventes datos que no te haya devuelto una herramienta. Si un equipo tiene la "
     "mantención vencida o un curso está vencido, adviértelo claramente."),
    ("human", "{entrada}"),
    MessagesPlaceholder("agent_scratchpad"),
])


def construir_agente(modelo, herramientas=HERRAMIENTAS, verbose=False):
    """Arma el agente y su ejecutor. Recibe el modelo como parámetro para poder probarlo."""
    agente = create_tool_calling_agent(modelo, herramientas, PROMPT_AGENTE)
    return AgentExecutor(agent=agente, tools=herramientas, verbose=verbose,
                         return_intermediate_steps=True, max_iterations=5)


def herramientas_usadas(resultado: dict) -> list[str]:
    """Nombres de las herramientas que usó el agente, en orden (lista vacía si no usó ninguna)."""
    return [accion.tool for accion, _ in resultado.get("intermediate_steps", [])]


def texto_de_salida(salida) -> str:
    """Devuelve la respuesta del agente como texto plano.
    Con Gemini, a veces llega como una lista de bloques {'type': 'text', 'text': ...} en vez de un str."""
    if isinstance(salida, str):
        return salida
    if isinstance(salida, list):
        return "".join(bloque.get("text", "") for bloque in salida
                       if isinstance(bloque, dict) and bloque.get("type") == "text")
    return str(salida)


if __name__ == "__main__":
    ejecutor = construir_agente(crear_modelo())
    consultas = [
        "¿Puedo intervenir hoy la correa CT-02?",
        "¿El trabajador T-1023 puede hacer un bloqueo de energías?",
        "¿Qué significa la sigla AST?",
    ]
    for consulta in consultas:
        resultado = ejecutor.invoke({"entrada": consulta})
        print(f"\n=== {consulta}")
        print(
            f"Herramientas usadas: {herramientas_usadas(resultado) or 'ninguna'}")
        print(texto_de_salida(resultado["output"]))