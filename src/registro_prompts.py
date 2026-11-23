"""Versionado de prompts (U2.7, Bloque 32 · paso 1).

Cada versión guarda una huella (sha256) del texto exacto, el texto, el autor,
la fecha, el modelo contra el que se probó y una nota de por qué cambió.
El historial se guarda en prompts/registro_versiones.json, así sobrevive entre
ejecuciones y se versiona con git.

Con la huella en los logs (src/logging_rag.py registra prompt_sistema_huella),
la pregunta "¿qué prompt exacto generó esta respuesta?" tiene respuesta.

Uso desde la raíz del repo:  python -m src.registro_prompts
"""
import difflib
import hashlib
import json
from datetime import date
from pathlib import Path

from src.indexar_corpus import RAIZ

ARCHIVO_REGISTRO = RAIZ / "prompts" / "registro_versiones.json"


def huella_prompt(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()[:12]


class RegistroDePrompts:
    def __init__(self, archivo: Path | None = None):
        self.archivo = archivo
        self.versiones = []
        if archivo is not None and Path(archivo).exists():
            self.versiones = json.loads(Path(archivo).read_text(encoding="utf-8"))

    def registrar(self, nombre, texto, autor, nota, modelo, fecha=None) -> dict:
        """Agrega una versión. Si ese texto exacto ya está registrado para ese prompt
        (en cualquier versión, no solo la última), no duplica y devuelve la existente:
        correr el script varias veces no ensucia el historial."""
        existente = next((v for v in self.historial(nombre) if v["huella"] == huella_prompt(texto)), None)
        if existente:
            return existente
        version = {"nombre": nombre, "version": len(self.historial(nombre)) + 1,
                   "huella": huella_prompt(texto), "texto": texto, "autor": autor,
                   "fecha": fecha or str(date.today()), "modelo": modelo, "nota": nota}
        self.versiones.append(version)
        self.guardar()
        return version

    def historial(self, nombre) -> list[dict]:
        return [v for v in self.versiones if v["nombre"] == nombre]

    def ultima(self, nombre) -> dict | None:
        historial = self.historial(nombre)
        return historial[-1] if historial else None

    def buscar(self, huella) -> dict | None:
        """La versión que corresponde a una huella vista en un log."""
        return next((v for v in self.versiones if v["huella"] == huella), None)

    def guardar(self) -> None:
        if self.archivo is not None:
            Path(self.archivo).write_text(json.dumps(self.versiones, indent=2, ensure_ascii=False),
                                          encoding="utf-8")


def diff_prompts(anterior: str, nueva: str) -> list[str]:
    """Diferencias palabra por palabra (+ agregada, - quitada)."""
    return list(difflib.unified_diff(anterior.split(), nueva.split(),
                                     fromfile="version_anterior", tofile="version_nueva", lineterm=""))


def resumen_diff(anterior: str, nueva: str) -> dict:
    lineas = diff_prompts(anterior, nueva)
    agregadas = [l[1:] for l in lineas if l.startswith("+") and not l.startswith("+++")]
    quitadas = [l[1:] for l in lineas if l.startswith("-") and not l.startswith("---")]
    return {"palabras_agregadas": len(agregadas), "palabras_quitadas": len(quitadas)}


# ---------- Historial real del prompt del RAG en este proyecto ----------

# Regla de cobertura tal como estaba en la v3 (la v4 vive en src/logging_rag.py).
REGLA_COBERTURA_V3 = (
    "El contexto puede usar palabras distintas a las de la pregunta: relaciona los términos "
    "cuando el propio contexto lo permita. Si responde solo una parte, responde esa parte y "
    "di qué falta. Solo si ningún fragmento se relaciona con la pregunta, responde "
    "exactamente: "
)

def versiones_prompt_rag() -> list[tuple[str, str, str]]:
    """(texto, fecha, nota) de cada versión, en orden."""
    from src.logging_rag import PLANTILLA_USUARIO, REGLA_COBERTURA, SISTEMA_RAG
    from src.recuperacion import ADVERTENCIA, PROMPT_RAG, SIN_INFORMACION

    parrafo_nuevo = PROMPT_RAG[PROMPT_RAG.index("El contexto puede usar"):PROMPT_RAG.index("Termina siempre")]
    v1 = PROMPT_RAG.replace(
        parrafo_nuevo,
        f'Si el contexto no alcanza para responder, responde exactamente: "{SIN_INFORMACION}"\n\n')
    v1 = v1.replace("aunque los conozcas.\n\nSi el contexto", "aunque los conozcas. Si el contexto")
    v4 = SISTEMA_RAG + "\n\n" + PLANTILLA_USUARIO
    v3 = v4.replace(REGLA_COBERTURA, REGLA_COBERTURA_V3)
    assert ADVERTENCIA in v1 and ADVERTENCIA in v3 and v3 != v4
    return [
        (v1, "2026-11-20", "versión inicial del Bloque 26: citar con [n] y frase fija si no hay información"),
        (PROMPT_RAG, "2026-11-20", "relacionar términos (estanque -> espacio confinado) y responder "
                                   "parcialmente: corrige el falso 'no sé' del Bloque 26"),
        (v3, "2026-11-20", "defensa contra inyección (Bloque 31): instrucciones en SystemMessage, "
                           "contexto entre etiquetas <contexto> y tratado como datos"),
        (v4, "2026-11-23", "quita 'di qué falta' (inventaba faltantes) y aclara que no se responde "
                           "'no sé' si algún fragmento trata el tema (3 falsos 'no sé' con v2 y v3)"),
    ]


def main() -> None:
    from src.consumir_gemini import MODELO

    registro = RegistroDePrompts(ARCHIVO_REGISTRO)
    for texto, fecha, nota in versiones_prompt_rag():
        registro.registrar("prompt_rag", texto, "Sebastián", nota, MODELO, fecha=fecha)

    for v in registro.historial("prompt_rag"):
        print(f"v{v['version']}  {v['huella']}  {v['fecha']}  {v['modelo']}  - {v['nota']}")
    huellas = [v["huella"] for v in registro.historial("prompt_rag")]
    print("\nhuellas distintas:", len(set(huellas)) == len(huellas))
    print("última versión:", registro.ultima("prompt_rag")["huella"])

    v1, v2, v3 = registro.historial("prompt_rag")[:3]
    v4 = registro.ultima("prompt_rag")
    print("\n--- diff v1 -> v2 (primeras 20 líneas; + agregada, - quitada) ---")
    print("\n".join(diff_prompts(v1["texto"], v2["texto"])[:20]))
    print("resumen v1 -> v2:", resumen_diff(v1["texto"], v2["texto"]))
    print("\nresumen v2 -> v3:", resumen_diff(v2["texto"], v3["texto"]))
    print("\n--- diff v3 -> v4 ---")
    print("\n".join(l for l in diff_prompts(v3["texto"], v4["texto"]) if l[:1] in "+-" and l[:3] not in ("+++", "---")))
    print(f"\nHistorial guardado en {ARCHIVO_REGISTRO.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
