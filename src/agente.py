"""Agente de seguridad minera con herramientas y memoria (U2.4, Bloques 21 y 22).

El agente decide por sí mismo qué herramienta usar según la pregunta, o si no necesita ninguna.
Con memoria, recuerda lo conversado dentro de una misma sesión (session_id).
Los datos de equipos, trabajadores y procedimientos son FICTICIOS, solo para el ejercicio.

Uso desde la raíz del repo:  python -m src.agente
"""

import json
import threading
from datetime import date, datetime, timezone
from pathlib import Path

from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableLambda
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.tools import tool
from pydantic import BaseModel, Field

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

PROCEDIMIENTOS = {
    "PTS-MEC-014": {
        "nombre": "Cambio de rodillo en correa transportadora",
        "palabras_clave": ["rodillo", "polín", "polin"],
        "pasos": ["Emitir permiso de trabajo y confeccionar el AST",
                  "Detener la correa y bloquear la energía en el CCM con candado y tarjeta personal",
                  "Trabar mecánicamente la correa y el contrapeso del take-up",
                  "Verificar energía cero intentando arrancar desde la botonera local",
                  "Delimitar el área y realizar el cambio con herramientas e izaje adecuados"],
    },
    "PTS-GEN-002": {
        "nombre": "Bloqueo y etiquetado de energías",
        "palabras_clave": ["bloqueo", "bloquear", "energía", "energia", "loto"],
        "pasos": ["Identificar todas las fuentes de energía del equipo",
                  "Detener el equipo con el procedimiento normal",
                  "Aislar las energías e instalar candado y tarjeta personal",
                  "Liberar o bloquear las energías residuales",
                  "Verificar energía cero antes de intervenir"],
    },
    "PTS-GEN-007": {
        "nombre": "Trabajo en altura física",
        "palabras_clave": ["altura", "arnés", "arnes", "pasarela", "andamio"],
        "pasos": ["Verificar curso de trabajo en altura vigente",
                  "Inspeccionar arnés de cuerpo completo y doble cabo de vida",
                  "Anclarse a un punto o línea de vida certificada",
                  "Delimitar el nivel inferior y asegurar las herramientas contra caídas"],
    },
}


DIAS_AVISO_VENCIMIENTO = 30


def dias_para_vencer(fecha_vencimiento: str, hoy: date = None) -> int:
    hoy = hoy or date.today()
    return (date.fromisoformat(fecha_vencimiento) - hoy).days


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
    # Aviso de vencimiento próximo (hallazgo de la U2.4: el curso de altura de T-2045
    # vencía en 12 días y el agente no lo mencionó).
    por_vencer = [f"{curso} vence en {dias_para_vencer(fecha)} días"
                  for curso, fecha in cursos.items()
                  if 0 <= dias_para_vencer(fecha) <= DIAS_AVISO_VENCIMIENTO]
    aviso = f" ATENCIÓN: {'; '.join(por_vencer)}, coordinar la renovación." if por_vencer else ""
    return f"Certificaciones de {codigo}: {detalle}.{aviso}"


class ArgumentosBuscarProcedimiento(BaseModel):
    tarea: str = Field(description="Tarea que se quiere realizar, en pocas palabras, "
                                   "por ejemplo 'cambio de rodillo' o 'trabajo en altura'.")
    incluir_pasos: bool = Field(default=False,
                                description="Si es True, incluye los pasos del procedimiento. "
                                            "Si es False, solo el nombre y el código del PTS.")


@tool("buscar_procedimiento_trabajo_seguro", args_schema=ArgumentosBuscarProcedimiento)
def buscar_procedimiento(tarea: str, incluir_pasos: bool = False) -> str:
    """Busca el Procedimiento de Trabajo Seguro (PTS) de la faena que corresponde a una tarea.
    Usar cuando el trabajador pregunta cómo realizar una tarea o qué procedimiento debe seguir."""
    texto = tarea.lower()
    encontrados = [(codigo, pts) for codigo, pts in PROCEDIMIENTOS.items()
                   if any(clave in texto for clave in pts["palabras_clave"])]
    if not encontrados:
        return f"No se encontró un PTS para la tarea '{tarea}'. Consulte con su supervisor."
    respuestas = []
    for codigo, pts in encontrados:
        texto_pts = f"{codigo}: {pts['nombre']}"
        if incluir_pasos:
            pasos = " ".join(f"{i}. {paso}." for i,
                             paso in enumerate(pts["pasos"], start=1))
            texto_pts += f". Pasos: {pasos}"
        respuestas.append(texto_pts)
    return " | ".join(respuestas)


# ---------- Supervisión humana (herramientas de riesgo alto) ----------

ARCHIVO_APROBACIONES = Path("aprobaciones_agente.jsonl")
ARCHIVO_TRAZAS = Path("trazas_agente.jsonl")
HERRAMIENTAS_ALTO_RIESGO = {"solicitar_bloqueo_equipo"}


def esperar_aprobacion(mensaje: str, tiempo_limite_segundos: float = 60) -> bool:
    """Pide aprobación por consola con un tiempo límite. Funciona en Windows (usa un hilo, no select).
    Si no hay respuesta a tiempo o no hay consola disponible, RECHAZA por seguridad."""
    respuesta = []

    def leer():
        try:
            respuesta.append(input(mensaje))
        except EOFError:
            pass

    hilo = threading.Thread(target=leer, daemon=True)
    hilo.start()
    hilo.join(tiempo_limite_segundos)
    if not respuesta:
        print("\n(Sin respuesta a tiempo: la acción se rechaza por seguridad.)")
        return False
    return respuesta[0].strip().lower() == "s"


def registrar_aprobacion(herramienta: str, argumentos: dict, aprobado: bool, archivo: Path = None) -> None:
    """Guarda cada decisión de aprobación (aprobada o rechazada) en un archivo JSONL."""
    archivo = archivo or ARCHIVO_APROBACIONES
    registro = {"momento": datetime.now(timezone.utc).isoformat(), "herramienta": herramienta,
                "argumentos": argumentos, "aprobado": aprobado}
    with open(archivo, "a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False) + "\n")


class ArgumentosSolicitarBloqueo(BaseModel):
    codigo_equipo: str = Field(
        description="Código del equipo a detener y bloquear, por ejemplo 'CT-01'.")
    motivo: str = Field(
        description="Motivo de la detención, por ejemplo 'polín dañado' o 'cambio de rodillo'.")


@tool("solicitar_bloqueo_equipo", args_schema=ArgumentosSolicitarBloqueo)
def solicitar_bloqueo_equipo(codigo_equipo: str, motivo: str) -> str:
    """Genera una solicitud para detener y bloquear un equipo de la faena. Acción de RIESGO ALTO:
    detiene la producción y requiere la aprobación de un supervisor antes de ejecutarse.
    Usar cuando el trabajador pide explícitamente detener o bloquear un equipo."""
    codigo = codigo_equipo.strip().upper()
    equipo = EQUIPOS.get(codigo)
    if equipo is None:
        return f"No existe un equipo con el código {codigo}. No se generó ninguna solicitud."
    if equipo["bloqueado"]:
        return f"{codigo} ya está bloqueado. No se requiere una nueva solicitud."
    mensaje = (f"\n[APROBACIÓN REQUERIDA] El agente quiere detener y bloquear {codigo} "
               f"por: {motivo}. ¿Aprobar? (s/n): ")
    aprobado = esperar_aprobacion(mensaje)
    registrar_aprobacion("solicitar_bloqueo_equipo", {
                         "codigo_equipo": codigo, "motivo": motivo}, aprobado)
    if not aprobado:
        return f"Solicitud de bloqueo de {codigo} NO aprobada por el supervisor. El equipo sigue operando."
    return (f"Solicitud de bloqueo de {codigo} aprobada por el supervisor y registrada. "
            f"Coordinar la detención con la sala de control antes de intervenir.")


HERRAMIENTAS = [consultar_estado_equipo, consultar_certificaciones_trabajador,
                buscar_procedimiento, solicitar_bloqueo_equipo]

PROMPT_AGENTE = ChatPromptTemplate.from_messages([
    ("system",
     "Eres un asistente de seguridad para una faena minera en Chile. Responde siempre en español, "
     "de forma breve y en texto plano, sin markdown. Usa las herramientas cuando la pregunta requiera "
     "datos de un equipo, de un trabajador o de un procedimiento. Nunca inventes datos que no te haya "
     "devuelto una herramienta. Si un equipo tiene la mantención vencida o un curso está vencido o "
     "por vencer, adviértelo claramente. Nunca le digas al trabajador que puede intervenir un equipo "
     "o que está autorizado para una tarea: informa el estado del equipo o de sus cursos y recuerda "
     "que la autorización la da el supervisor con el permiso de trabajo, el AST y, cuando "
     "corresponde, el bloqueo de energías."),
    MessagesPlaceholder("chat_history", optional=True),
    ("human", "{entrada}"),
    MessagesPlaceholder("agent_scratchpad"),
])


# ---------- Agente ----------

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


# Segunda capa contra el riesgo CRÍTICO de la matriz: aunque el prompt lo prohíbe, si la
# respuesta igual "autoriza" una intervención, se agrega la aclaración en código.
PATRONES_AUTORIZACION = [
    r"\bpuedes?\s+(?:intervenir|realizar|hacer|cambiar|trabajar|subir|ingresar)",
    r"\best[áa]s?\s+(?:autorizad|habilitad)",
    r"\btienes?\s+autorizaci[óo]n",
    r"\bpuede\s+(?:intervenir|realizar|trabajar|subir|ingresar)",
]
ACLARACION_AUTORIZACION = ("Importante: esta información no es una autorización. La autorización para "
                           "intervenir la da el supervisor con el permiso de trabajo, el AST y, "
                           "cuando corresponde, el bloqueo de energías.")


def revisar_autorizacion(texto: str) -> tuple[str, bool]:
    """Si la respuesta suena a autorización, agrega la aclaración. Devuelve (texto, se_agregó)."""
    import re
    if ACLARACION_AUTORIZACION in texto:
        return texto, False
    if any(re.search(p, texto.lower()) for p in PATRONES_AUTORIZACION):
        return f"{texto.rstrip()}\n\n{ACLARACION_AUTORIZACION}", True
    return texto, False


def normalizar_resultado(resultado: dict) -> dict:
    """Deja 'output' como texto plano (para que la memoria guarde un mensaje limpio)
    y agrega la aclaración si la respuesta suena a una autorización."""
    texto, corregido = revisar_autorizacion(texto_de_salida(resultado["output"]))
    return {**resultado, "output": texto, "aclaracion_agregada": corregido}


# ---------- Memoria ----------

historiales: dict[str, InMemoryChatMessageHistory] = {}


def obtener_historial(session_id: str) -> InMemoryChatMessageHistory:
    """Devuelve el historial de una sesión, creándolo si no existe."""
    if session_id not in historiales:
        historiales[session_id] = InMemoryChatMessageHistory()
    return historiales[session_id]


def cerrar_sesion(session_id: str) -> None:
    """Borra el historial de una sesión (no falla si no existe)."""
    historiales.pop(session_id, None)


def construir_agente_con_memoria(modelo, herramientas=HERRAMIENTAS):
    """Envuelve el agente con memoria por sesión. Cada invoke necesita
    config={'configurable': {'session_id': '...'}}."""
    ejecutor = construir_agente(
        modelo, herramientas) | RunnableLambda(normalizar_resultado)
    return RunnableWithMessageHistory(
        ejecutor,
        obtener_historial,
        input_messages_key="entrada",
        history_messages_key="chat_history",
        output_messages_key="output",
    )


def config_sesion(session_id: str) -> dict:
    return {"configurable": {"session_id": session_id}}


# ---------- Trazas de decisión ----------

def registrar_traza(session_id: str, entrada: str, resultado: dict, archivo: Path = None) -> None:
    """Guarda una interacción del agente como una línea JSON: qué se preguntó,
    qué herramientas usó, con qué argumentos, qué observó y qué respondió."""
    archivo = archivo or ARCHIVO_TRAZAS
    registro = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "entrada": entrada,
        "acciones": [{"herramienta": accion.tool, "argumentos": accion.tool_input,
                      "observacion": str(observacion)}
                     for accion, observacion in resultado.get("intermediate_steps", [])],
        "respuesta_final": texto_de_salida(resultado.get("output", "")),
        "aclaracion_agregada": resultado.get("aclaracion_agregada", False),
    }
    with open(archivo, "a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False) + "\n")


def leer_trazas(archivo: Path = None) -> list[dict]:
    archivo = archivo or ARCHIVO_TRAZAS
    if not Path(archivo).exists():
        return []
    with open(archivo, encoding="utf-8") as f:
        return [json.loads(linea) for linea in f if linea.strip()]


def marcar_repeticiones_sospechosas(archivo: Path = None) -> list[str]:
    """Primera revisión automática: sesiones donde la misma herramienta se usó dos veces seguidas.
    Son candidatas a revisar a mano, no una conclusión."""
    alertas = []
    for registro in leer_trazas(archivo):
        herramientas = [a["herramienta"] for a in registro.get("acciones", [])]
        for anterior, actual in zip(herramientas, herramientas[1:]):
            if anterior == actual:
                alertas.append(
                    f"Revisar: {registro['session_id']} usó '{actual}' dos veces seguidas")
                break
    return alertas


def marcar_alto_riesgo_sin_decision(archivo: Path = None) -> list[str]:
    """Alerta si una herramienta de riesgo alto aparece en la traza sin una decisión de aprobación."""
    alertas = []
    for registro in leer_trazas(archivo):
        for accion in registro.get("acciones", []):
            if (accion["herramienta"] in HERRAMIENTAS_ALTO_RIESGO
                    and "aprobada" not in accion["observacion"].lower()):
                alertas.append(f"Revisar: {registro['session_id']} usó '{accion['herramienta']}' "
                               f"sin una decisión de aprobación registrada")
    return alertas


if __name__ == "__main__":
    agente = construir_agente_con_memoria(crear_modelo())

    conversacion = [
        ("turno_A", "¿Puedo intervenir hoy la correa CT-01?"),
        ("turno_A", "¿Qué procedimiento debo seguir para cambiarle un rodillo? Dame los pasos."),
        ("turno_A", "Vi un polín dañado en la CT-01. Solicita detenerla y bloquearla."),
        ("turno_B", "¿El trabajador T-2045 puede trabajar en altura?"),
    ]
    for session_id, entrada in conversacion:
        resultado = agente.invoke(
            {"entrada": entrada}, config=config_sesion(session_id))
        registrar_traza(session_id, entrada, resultado)
        print(f"\n=== [{session_id}] {entrada}")
        print(
            f"Herramientas usadas: {herramientas_usadas(resultado) or 'ninguna'}")
        print(resultado["output"])

    print("\n--- Revisión automática de trazas ---")
    alertas = marcar_repeticiones_sospechosas() + marcar_alto_riesgo_sin_decision()
    print("\n".join(alertas) if alertas else "Sin alertas.")
