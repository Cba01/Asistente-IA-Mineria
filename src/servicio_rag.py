"""Servicio RAG del Gate 2: punto de entrada único del Asistente IA de Seguridad Minera.

Une todas las piezas del Módulo 2 en una sola consulta:
1. Revisa que el índice persistido exista (si está vacío, lo construye una vez).
2. Revisa que la versión del prompt que usa el código sea la APROBADA en
   prompts/version_activa.json (punto de supervisión del Bloque 32). Si no lo es, no responde.
3. Corre la consulta con src/logging_rag.py: recuperación, filtro de inyección,
   roles separados, generación, citas, logs JSON con trace_id y consumo.
4. Devuelve la respuesta con sus fuentes escritas al final (nombre de archivo).

Uso desde la raíz del repo:
    python -m src.servicio_rag "¿Qué debo hacer antes de cambiar un rodillo de la correa?"
    python -m src.servicio_rag            # pide la pregunta por teclado (conserva las tildes)
"""
import argparse
import logging
import sys

from dotenv import load_dotenv

from src.grafo_supervision import leer_activas
from src.logging_rag import PROMPT_HUELLA, configurar_logger, log_evento, procesar_consulta

load_dotenv()


class VersionNoAprobada(Exception):
    pass


def verificar_version_prompt(activas: dict | None = None) -> None:
    """El servicio solo responde con la versión de prompt que una persona aprobó."""
    activas = leer_activas() if activas is None else activas
    aprobada = activas.get("prompt_rag")
    if aprobada != PROMPT_HUELLA:
        raise VersionNoAprobada(
            f"El código usa la versión de prompt {PROMPT_HUELLA}, pero la aprobada es {aprobada}. "
            "Regístrala y apruébala con: python -m src.registro_prompts y python -m src.grafo_supervision")


def asegurar_indice() -> int:
    """Devuelve la cantidad de chunks del índice. Si está vacío, indexa el corpus una vez."""
    from src.indexar_corpus import (cargar_corpus, cargar_vectorstore, crear_embeddings, indexar,
                                    partir_en_chunks)
    embeddings = crear_embeddings()
    total = cargar_vectorstore(embeddings)._collection.count()
    if total == 0:
        print("El índice está vacío: indexando el corpus por primera vez...")
        chunks, ids = partir_en_chunks(cargar_corpus())
        indexar(chunks, ids, embeddings)
        total = cargar_vectorstore(embeddings)._collection.count()
    return total


def armar_respuesta_final(resultado: dict) -> tuple[str, list[str]]:
    """Agrega al final de la respuesta los archivos que la respaldan.

    - Si el modelo citó: "Fuentes:" con cada [n] y su archivo.
    - Si respondió sin citar (no debería, el prompt lo exige): se listan los documentos
      que recibió como contexto, marcados como tales, para que nunca quede sin fuente.
    - Si dijo que no tiene información: no hay fuente que citar.
    """
    texto = resultado["respuesta"].strip()
    if resultado["citas_usadas"]:
        fuentes = sorted(set(resultado["citas_usadas"].values()))
        detalle = "\n".join(f"  [{n}] {f}" for n, f in sorted(resultado["citas_usadas"].items()))
        return f"{texto}\n\nFuentes:\n{detalle}", fuentes
    if not resultado["sin_informacion"] and resultado["fuentes_contexto"]:
        fuentes = resultado["fuentes_contexto"]
        detalle = "\n".join(f"  - {f}" for f in fuentes)
        return f"{texto}\n\nDocumentos consultados (la respuesta no los citó):\n{detalle}", fuentes
    return texto, []


def responder(pregunta: str, retriever=None, modelo=None) -> dict:
    """Una consulta completa. Devuelve {trace_id, respuesta (con fuentes), fuentes, ...}."""
    if not pregunta or not pregunta.strip():
        raise ValueError("La pregunta no puede estar vacía.")
    verificar_version_prompt()
    resultado = procesar_consulta(pregunta.strip(), retriever=retriever, modelo=modelo)
    texto, fuentes = armar_respuesta_final(resultado)
    return {**resultado, "respuesta": texto, "fuentes": fuentes}


def main() -> int:
    parser = argparse.ArgumentParser(description="Asistente IA de Seguridad Minera (servicio RAG).")
    parser.add_argument("pregunta", nargs="?", help="Pregunta. Si se omite, se pide por teclado.")
    parser.add_argument("--sin-logs-en-consola", action="store_true",
                        help="Los logs van solo a logs/rag.jsonl.")
    args = parser.parse_args()
    configurar_logger(consola=not args.sin_logs_en_consola)

    try:
        verificar_version_prompt()
        print(f"Índice listo: {asegurar_indice()} chunks")
        pregunta = args.pregunta or input("Pregunta: ")
        resultado = responder(pregunta)
    except VersionNoAprobada as error:
        print(f"\nNo se respondió: {error}")
        return 1
    except ValueError as error:
        print(f"\nNo se respondió: {error}")
        return 1
    except Exception as error:
        mensaje = str(error)
        if "429" in mensaje or "RESOURCE_EXHAUSTED" in mensaje:
            print("\nSe agotó la cuota de la API. Espera un minuto y vuelve a intentar.")
        elif "API key" in mensaje or "401" in mensaje or "403" in mensaje:
            print('\nLa API rechazó la clave. Revisa GEMINI_API_KEY en tu ".env".')
        else:
            print(f"\nNo se pudo responder ({type(error).__name__}). Revisa logs/rag.jsonl.")
        log_evento("servicio_fallo", logging.ERROR, tipo=type(error).__name__)
        return 1

    print("\n--- Respuesta ---")
    print(resultado["respuesta"])
    print(f"\n(trace_id: {resultado['trace_id']}; el detalle está en logs/rag.jsonl)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
