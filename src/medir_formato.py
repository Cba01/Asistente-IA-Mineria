"""Mide cuántas respuestas reales del modelo incumplen el formato esperado (U2.6, Bloque 30).

Es la evidencia para la pregunta "problema_de_formato_o_tono" del método de
decisión: el curso pide revisar 20 respuestas reales con una lista fija de
criterios y contar los incumplimientos (umbral: 15 % o más).

Usa las 20 respuestas guardadas en la U2.2 (docs/resultados_metricas.json),
así que no llama a la API.

Formato esperado de una respuesta del asistente:
1. completa:        termina en punto, signo de cierre o paréntesis (no cortada),
2. breve:           como máximo 2 oraciones (en la U2.2 se pidió "una o dos frases"),
3. texto plano:     sin markdown (**negrita**, # títulos, viñetas),
4. solo español:    sin letras de otros alfabetos (chino, canarés...).

Limitación conocida: una palabra de otro idioma escrita con letras latinas
(por ejemplo "silicose") no se detecta automáticamente; se cuenta aparte,
según la revisión manual de la U2.2.

Uso desde la raíz del repo:  python -m src.medir_formato
"""
import json
import re
import unicodedata
from pathlib import Path

from src.indexar_corpus import RAIZ

ARCHIVO_RESPUESTAS = RAIZ / "docs" / "resultados_metricas.json"
UMBRAL_INCUMPLIMIENTO = 0.15
MAX_ORACIONES = 2


def esta_completa(texto: str) -> bool:
    return texto.rstrip()[-1:] in {".", "!", "?", ")", "»", '"'}


def contar_oraciones(texto: str) -> int:
    """Cuenta oraciones cortando en . ! ? seguidos de espacio o fin de texto.
    "16.744" o "1,8" no cortan, porque el punto o la coma van seguidos de un dígito."""
    partes = re.split(r"[.!?](?:\s+|$)", texto.strip())
    return len([p for p in partes if p.strip()])


def tiene_markdown(texto: str) -> bool:
    return bool(re.search(r"\*\*|__|^\s*#|^\s*[-*•]\s", texto, flags=re.MULTILINE))


def tiene_otro_alfabeto(texto: str) -> bool:
    """True si hay letras fuera del alfabeto latino (incluye tildes, ñ y ü)."""
    return any(unicodedata.category(c).startswith("L") and ord(c) > 0x24F for c in texto)


def revisar_respuesta(texto: str) -> list[str]:
    """Devuelve la lista de criterios que la respuesta incumple (vacía si cumple todos)."""
    fallas = []
    if not esta_completa(texto):
        fallas.append("cortada")
    if contar_oraciones(texto) > MAX_ORACIONES:
        fallas.append(f"más de {MAX_ORACIONES} oraciones")
    if tiene_markdown(texto):
        fallas.append("markdown")
    if tiene_otro_alfabeto(texto):
        fallas.append("otro alfabeto")
    return fallas


def evaluar_respuestas(respuestas: list[str]) -> dict:
    detalle = [revisar_respuesta(r) for r in respuestas]
    con_fallas = sum(1 for d in detalle if d)
    por_criterio = {}
    for fallas in detalle:
        for f in fallas:
            por_criterio[f] = por_criterio.get(f, 0) + 1
    proporcion = con_fallas / len(respuestas) if respuestas else 0.0
    return {
        "total": len(respuestas),
        "con_fallas": con_fallas,
        "proporcion": proporcion,
        "por_criterio": por_criterio,
        "detalle": detalle,
        "supera_umbral": proporcion >= UMBRAL_INCUMPLIMIENTO,
    }


def evaluar_archivo(archivo: Path = ARCHIVO_RESPUESTAS) -> dict:
    datos = json.loads(Path(archivo).read_text(encoding="utf-8"))
    resultado = evaluar_respuestas([d["respuesta"] for d in datos])
    resultado["preguntas"] = [d["pregunta"] for d in datos]
    return resultado


def main() -> None:
    r = evaluar_archivo()
    for i, (pregunta, fallas) in enumerate(zip(r["preguntas"], r["detalle"]), start=1):
        estado = "ok" if not fallas else ", ".join(fallas)
        print(f"{i:>2}. {estado:<40} {pregunta[:55]}")
    print(f"\nRespuestas con al menos una falla: {r['con_fallas']} de {r['total']} "
          f"({r['proporcion']:.0%}). Umbral del curso: {UMBRAL_INCUMPLIMIENTO:.0%}.")
    print("Fallas por criterio:", r["por_criterio"] or "ninguna")
    print("problema_de_formato_o_tono =", r["supera_umbral"])


if __name__ == "__main__":
    main()
