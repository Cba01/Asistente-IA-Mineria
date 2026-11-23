"""Punto de supervisión humana para activar una versión nueva de prompt (U2.7, Bloque 32 · paso 2).

Grafo de LangGraph: proponer -> supervisar (interrupt) -> aplicar.
El grafo se DETIENE en supervisar hasta que una persona responde. Solo si aprueba,
"aplicar" escribe la huella en prompts/version_activa.json; si rechaza, la versión
activa no cambia.

Uso desde la raíz del repo:  python -m src.grafo_supervision
"""
import json
import uuid
from pathlib import Path
from typing import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from src.indexar_corpus import RAIZ
from src.registro_prompts import ARCHIVO_REGISTRO, RegistroDePrompts, diff_prompts, resumen_diff

ARCHIVO_ACTIVA = RAIZ / "prompts" / "version_activa.json"


class EstadoDespliegue(TypedDict):
    nombre: str
    huella_actual: str
    huella_nueva: str
    aprobado: bool


def leer_activas(archivo: Path = ARCHIVO_ACTIVA) -> dict:
    return json.loads(Path(archivo).read_text(encoding="utf-8")) if Path(archivo).exists() else {}


def construir_grafo(registro: RegistroDePrompts, archivo_activa: Path = ARCHIVO_ACTIVA, checkpointer=None):
    def proponer(estado: EstadoDespliegue):
        return {}

    def supervisar(estado: EstadoDespliegue):
        actual = registro.buscar(estado["huella_actual"])
        nueva = registro.buscar(estado["huella_nueva"])
        decision = interrupt({
            "motivo": "aprobar nueva versión de prompt en producción",
            "prompt": estado["nombre"],
            "huella_actual": estado["huella_actual"],
            "huella_propuesta": estado["huella_nueva"],
            "nota": nueva["nota"] if nueva else None,
            "cambios": resumen_diff(actual["texto"], nueva["texto"]) if actual and nueva else None,
        })
        if not isinstance(decision, bool):
            # Un texto como "no" es verdadero en Python: solo se aceptan True o False.
            raise ValueError("La decisión debe ser True o False")
        return {"aprobado": decision}

    def aplicar(estado: EstadoDespliegue):
        activas = leer_activas(archivo_activa)
        if estado["aprobado"]:
            activas[estado["nombre"]] = estado["huella_nueva"]
            Path(archivo_activa).write_text(json.dumps(activas, indent=2), encoding="utf-8")
            print(f"versión {estado['huella_nueva']} ACTIVADA")
        else:
            print(f"versión {estado['huella_nueva']} RECHAZADA, se mantiene {estado['huella_actual']}")
        return {}

    grafo = StateGraph(EstadoDespliegue)
    grafo.add_node("proponer", proponer)
    grafo.add_node("supervisar", supervisar)
    grafo.add_node("aplicar", aplicar)
    grafo.add_edge(START, "proponer")
    grafo.add_edge("proponer", "supervisar")
    grafo.add_edge("supervisar", "aplicar")
    grafo.add_edge("aplicar", END)
    return grafo.compile(checkpointer=checkpointer or InMemorySaver())


def nuevo_config(prefijo="despliegue") -> dict:
    """Un thread_id único por solicitud: reutilizarlo pisaría una aprobación pendiente."""
    return {"configurable": {"thread_id": f"{prefijo}-{uuid.uuid4().hex[:8]}"}}


def resolver(app, config, aprobar: bool):
    """Reanuda SOLO si hay una aprobación pendiente en ese thread_id."""
    if not app.get_state(config).next:
        raise ValueError("este thread_id no tiene ninguna aprobación pendiente")
    return app.invoke(Command(resume=aprobar), config=config)


def main() -> None:
    registro = RegistroDePrompts(ARCHIVO_REGISTRO)
    historial = registro.historial("prompt_rag")
    if len(historial) < 2:
        raise SystemExit("Primero corre: python -m src.registro_prompts")
    anterior, nueva = historial[-2], historial[-1]
    app = construir_grafo(registro)
    entrada = {"nombre": "prompt_rag", "huella_actual": anterior["huella"],
               "huella_nueva": nueva["huella"], "aprobado": False}

    print("=== Solicitud 1: la decides tú ===")
    config = nuevo_config()
    resultado = app.invoke(entrada, config=config)
    print("¿grafo detenido?:", "__interrupt__" in resultado)
    pendiente = app.get_state(config).interrupts[0].value
    print("pendiente:", json.dumps(pendiente, ensure_ascii=False, indent=2))
    print("\n".join(diff_prompts(anterior["texto"], nueva["texto"])[:25]), "\n(...)")
    aprobar = input("\n¿Aprobar la versión nueva? (s/n): ").strip().lower() == "s"
    print("estado final:", resolver(app, config, aprobar))

    try:
        resolver(app, config, True)
    except ValueError as error:
        print("Segundo intento sobre la misma solicitud:", error)

    print("\n=== Solicitud 2: camino de rechazo (otro thread_id) ===")
    config2 = nuevo_config()
    app.invoke(entrada, config=config2)
    print("estado final:", resolver(app, config2, False))

    print("\nVersión activa en prompts/version_activa.json:", leer_activas())


if __name__ == "__main__":
    main()
