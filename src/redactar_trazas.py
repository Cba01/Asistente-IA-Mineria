"""Enmascara los datos personales de las trazas del agente que ya están escritas.

Las trazas nuevas se enmascaran solas (registrar_traza en src/agente.py). Este script
corrige las líneas antiguas de trazas_agente.jsonl, escritas antes de esa protección.

Uso desde la raíz del repo:  python -m src.redactar_trazas
"""
import json
from pathlib import Path

from src.agente import ARCHIVO_TRAZAS, redactar_pii


def redactar_archivo(archivo: Path = ARCHIVO_TRAZAS) -> int:
    """Reescribe el archivo con los datos enmascarados. Devuelve cuántas líneas cambiaron."""
    if not Path(archivo).exists():
        return 0
    lineas = [l for l in Path(archivo).read_text(encoding="utf-8").splitlines() if l.strip()]
    nuevas = [json.dumps(redactar_pii(json.loads(l)), ensure_ascii=False) for l in lineas]
    cambiadas = sum(a != json.dumps(json.loads(b), ensure_ascii=False) for a, b in zip(nuevas, lineas))
    Path(archivo).write_text("\n".join(nuevas) + ("\n" if nuevas else ""), encoding="utf-8")
    return cambiadas


if __name__ == "__main__":
    print(f"{redactar_archivo()} líneas con datos personales enmascarados en {ARCHIVO_TRAZAS}")
