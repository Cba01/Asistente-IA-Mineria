"""Chequeo previo a la evaluación del Gate 2. No llama a la API ni imprime la clave.

Uso desde la raíz del repo:  python -m src.verificar_entorno
Termina con código 1 si falta algo.
"""
import os
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version

from dotenv import load_dotenv

from src.indexar_corpus import PERSIST_DIR, RAIZ

PAQUETES = ["langchain-core", "langchain-chroma", "chromadb", "langchain-google-genai",
            "langchain-classic", "langgraph", "google-genai", "python-dotenv", "pytest"]


def main() -> int:
    load_dotenv()
    problemas = []
    print("Python:", sys.version.split()[0])
    if sys.version_info < (3, 10):
        problemas.append("usar Python 3.10 o superior")

    for paquete in PAQUETES:
        try:
            print(f"{paquete}: {version(paquete)}")
        except PackageNotFoundError:
            print(f"{paquete}: NO instalado")
            problemas.append(f"instalar {paquete} (pip install -r requirements.txt)")

    clave = "definida" if os.getenv("GEMINI_API_KEY") else "FALTA"
    print(f"GEMINI_API_KEY: {clave}")
    if clave == "FALTA":
        problemas.append('definir GEMINI_API_KEY en el archivo ".env"')

    ignorado = subprocess.run(["git", "check-ignore", ".env"], cwd=RAIZ, capture_output=True, text=True)
    print(".env ignorado por git:", "sí" if ignorado.stdout.strip() else "NO")
    if not ignorado.stdout.strip():
        problemas.append('agregar ".env" a .gitignore')

    indice_ok = (PERSIST_DIR / "chroma.sqlite3").exists()
    print(f"Índice en {PERSIST_DIR.name}/:", "ok" if indice_ok else "no existe (se crea en la primera consulta "
                                                                  "o con python -m src.indexar_corpus)")

    from src.grafo_supervision import leer_activas
    from src.logging_rag import PROMPT_HUELLA
    aprobada = leer_activas().get("prompt_rag")
    print(f"Prompt del código: {PROMPT_HUELLA} · aprobado: {aprobada}")
    if aprobada != PROMPT_HUELLA:
        problemas.append("aprobar la versión actual del prompt (python -m src.grafo_supervision)")

    # Ningún log del repo puede tener datos personales en texto plano (criterio no compensable 3).
    import re
    from src.agente import PATRONES_PII
    archivos_log = [RAIZ / "trazas_agente.jsonl", RAIZ / "aprobaciones_agente.jsonl",
                    RAIZ / "registros_latencia_costo.jsonl", *sorted((RAIZ / "logs").glob("*.jsonl"))]
    con_pii = []
    for archivo in archivos_log:
        if archivo.exists():
            texto = archivo.read_text(encoding="utf-8")
            if any(re.search(patron, texto) for patron, _ in PATRONES_PII):
                con_pii.append(archivo.name)
    print("Datos personales en logs:", ", ".join(con_pii) if con_pii else "ninguno")
    if con_pii:
        problemas.append(f"enmascarar datos personales en {', '.join(con_pii)} (python -m src.redactar_trazas)")

    print()
    if problemas:
        print("Pendiente: " + "; ".join(problemas))
        return 1
    print("Entorno listo para la evaluación")
    return 0


if __name__ == "__main__":
    sys.exit(main())
