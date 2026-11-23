"""Matriz de riesgos del Asistente IA de Seguridad Minera (U2.7, Bloque 32 · paso 3).

Probabilidad e impacto (1 a 5) se estiman CON las mitigaciones que ya existen en
el proyecto (riesgo actual, no el peor escenario imaginable). Puntaje = P x I.
Cortes fijos del curso: CRITICO >= 15, ALTO >= 9, MEDIO >= 4, BAJO < 4.

Regla: todo riesgo ALTO o CRITICO debe tener un punto de supervisión humana.
El script lo verifica y genera docs/matriz_riesgos.md.

Uso desde la raíz del repo:  python -m src.matriz_riesgos
"""
from src.indexar_corpus import RAIZ

ARCHIVO_MATRIZ = RAIZ / "docs" / "matriz_riesgos.md"

RIESGOS = [
    {"riesgo": "El agente autoriza una intervención ('puedes intervenirlo') mirando solo el estado "
               "del equipo, sin permiso de trabajo, AST ni certificaciones",
     "probabilidad": 4, "impacto": 5,
     "evidencia": "Ocurrió en la corrida real del agente del 2026-11-19 (U2.4)",
     "mitigacion": "Ninguna en código todavía: hallazgo documentado en docs/limites_autonomia_agente.md "
                   "(U2.4). Pendiente: prompt que informe el estado sin autorizar",
     "supervision": "La autorización para intervenir siempre la da el supervisor con el permiso de "
                    "trabajo; el asistente solo informa. Revisión diaria de trazas con 'puedes' en la respuesta"},
    {"riesgo": "Respuesta con un dato de seguridad incorrecto (cifra, límite o paso omitido) que el "
               "trabajador sigue",
     "probabilidad": 2, "impacto": 5,
     "evidencia": "Módulo 1: rango de oxígeno 19,5-22 % en vez de 19,5-23,5 %; U2.2: paso de energías "
                  "residuales omitido",
     "mitigacion": "RAG con fuente citada y detección de citas inventadas (Bloque 26, recall 0,964 en "
                   "el Bloque 27) + advertencia al final de cada respuesta",
     "supervision": "Los documentos del corpus los aprueba un prevencionista antes de indexarlos; "
                    "revisión semanal de respuestas con citas inválidas o sin citas (logs/rag.jsonl)"},
    {"riesgo": "Inyección de prompt vía un documento del corpus que cambie una instrucción de "
               "seguridad (por ejemplo, 'no es necesario bloquear')",
     "probabilidad": 2, "impacto": 5,
     "evidencia": "El corpus es interno, pero se planea agregar documentos; el filtro por patrones no "
                  "detecta frases reescritas",
     "mitigacion": "Filtro de patrones + SystemMessage + contexto entre etiquetas <contexto> "
                   "(src/logging_rag.py, Bloque 31)",
     "supervision": "Un chunk descartado por el filtro genera un WARNING y bloquea su documento hasta que "
                    "una persona lo revise; ningún documento entra al corpus sin aprobación"},
    {"riesgo": "Datos personales de trabajadores (códigos, cursos, vencimientos) expuestos en logs o "
               "a usuarios no autorizados",
     "probabilidad": 3, "impacto": 3,
     "evidencia": "La herramienta consultar_certificaciones_trabajador devuelve datos personales (U2.4); "
                  "las preguntas pueden incluir códigos de trabajador",
     "mitigacion": "Los logs guardan largo y huella de la pregunta, no su texto (Bloque 31)",
     "supervision": "Acceso a logs y a la herramienta de certificaciones solo para supervisores, "
                    "aprobado por el jefe de área"},
    {"riesgo": "Un cambio de prompt empeora las respuestas sin que nadie lo note",
     "probabilidad": 3, "impacto": 3,
     "evidencia": "El prompt del RAG tuvo 4 versiones; la v3 se aprobó sin medir y agregó faltantes "
                  "inventados (2 de 15), corregidos en la v4 aprobada con evaluación",
     "mitigacion": "Versionado con huella, huella del prompt en cada log, evaluación de la generación "
                   "por versión (src/evaluar_generacion.py) y el servicio se niega a responder con un "
                   "prompt no aprobado (src/servicio_rag.py, Gate 2)",
     "supervision": "Grafo de aprobación antes de activar una versión (src/grafo_supervision.py, Bloque 32)"},
    {"riesgo": "API caída o cuota agotada (429/503) justo durante una consulta de emergencia",
     "probabilidad": 3, "impacto": 4,
     "evidencia": "503 frecuentes con 3.6-flash y 429 en el ensayo de rate limit (U2.1); plan gratuito",
     "mitigacion": "Reintentos con backoff (U2.1) y respuesta de emergencia fija sin modelo (U2.3)",
     "supervision": "Si se usa la respuesta de respaldo, se notifica al supervisor de turno"},
    {"riesgo": "El modelo responde 'no tengo información' teniendo el documento correcto en el contexto",
     "probabilidad": 3, "impacto": 2,
     "evidencia": "3 casos reales: estanque (Bloque 26), vigía (Bloque 28) y otra pregunta del vigía con "
                  "el prompt v3 (Bloque 31), siempre con el chunk correcto recuperado",
     "mitigacion": "Prompts v2 y v4 (relacionar términos, no decir 'no sé' si algún fragmento trata el "
                   "tema), campo sin_informacion en logs y evaluación de la generación (Gate 2)",
     "supervision": ""},
    {"riesgo": "PTS revisado en la faena pero no reindexado: el asistente cita una versión vieja",
     "probabilidad": 2, "impacto": 4,
     "evidencia": "El índice no se actualiza solo (Bloque 25)",
     "mitigacion": "Reindexación completa y sin duplicados con un solo comando (Bloque 24)",
     "supervision": ""},
    {"riesgo": "El modelo de texto o de embeddings cambia o queda deprecado",
     "probabilidad": 2, "impacto": 3,
     "evidencia": "Nombres de modelo inconsistentes en el curso; cambio forzado de 3.6-flash a flash-lite",
     "mitigacion": "Modelo configurable en .env y decisión documentada (U1.4); el índice guarda el modelo "
                   "de embeddings usado",
     "supervision": ""},
]


def puntaje_riesgo(probabilidad: int, impacto: int) -> int:
    return probabilidad * impacto


def categoria_riesgo(puntaje: int) -> str:
    if puntaje >= 15:
        return "CRITICO"
    if puntaje >= 9:
        return "ALTO"
    if puntaje >= 4:
        return "MEDIO"
    return "BAJO"


def esta_en_el_limite(probabilidad: int, impacto: int) -> bool:
    actual = categoria_riesgo(puntaje_riesgo(probabilidad, impacto))
    for p2, i2 in [(probabilidad + 1, impacto), (probabilidad - 1, impacto),
                   (probabilidad, impacto + 1), (probabilidad, impacto - 1)]:
        if 1 <= p2 <= 5 and 1 <= i2 <= 5 and categoria_riesgo(puntaje_riesgo(p2, i2)) != actual:
            return True
    return False


def evaluar(riesgos=RIESGOS) -> list[dict]:
    filas = []
    for r in riesgos:
        puntaje = puntaje_riesgo(r["probabilidad"], r["impacto"])
        filas.append({**r, "puntaje": puntaje, "categoria": categoria_riesgo(puntaje),
                      "al_limite": esta_en_el_limite(r["probabilidad"], r["impacto"])})
    return sorted(filas, key=lambda x: -x["puntaje"])


def validar(filas) -> list[str]:
    problemas = []
    if len(filas) < 5:
        problemas.append("La matriz debe tener al menos 5 riesgos")
    for f in filas:
        if not (1 <= f["probabilidad"] <= 5 and 1 <= f["impacto"] <= 5):
            problemas.append(f"Valores fuera de 1-5: {f['riesgo'][:50]}")
        if f["categoria"] in ("ALTO", "CRITICO") and not f["supervision"].strip():
            problemas.append(f"{f['categoria']} sin punto de supervisión: {f['riesgo'][:50]}")
    return problemas


def a_markdown(filas) -> str:
    lineas = ["# Matriz de riesgos: Asistente IA de Seguridad Minera", "",
              "Generada con `python -m src.matriz_riesgos`. Probabilidad (P) e impacto (I) de 1 a 5, "
              "estimados con las mitigaciones actuales. Puntaje = P × I. Cortes: CRÍTICO ≥ 15, "
              "ALTO ≥ 9, MEDIO ≥ 4. \"Al límite\" = un punto de diferencia en P o I cambia la categoría.",
              "", "| # | Riesgo | P | I | Puntaje | Categoría | Mitigación actual | Supervisión humana |",
              "|---|---|---|---|---|---|---|---|"]
    for n, f in enumerate(filas, start=1):
        limite = " (al límite)" if f["al_limite"] else ""
        lineas.append(f"| {n} | {f['riesgo']} | {f['probabilidad']} | {f['impacto']} | {f['puntaje']} | "
                      f"**{f['categoria']}**{limite} | {f['mitigacion']} | {f['supervision'] or 'No requiere'} |")
    lineas += ["", "## Evidencia de cada estimación", ""]
    lineas += [f"{n}. {f['evidencia']}." for n, f in enumerate(filas, start=1)]
    return "\n".join(lineas) + "\n"


def main() -> None:
    filas = evaluar()
    for f in filas:
        marca = " [AL LIMITE]" if f["al_limite"] else ""
        print(f"{f['categoria']:8} ({f['puntaje']:2}) - {f['riesgo'][:80]}{marca}")
    problemas = validar(filas)
    print("\nValidación:", "sin problemas" if not problemas else problemas)
    print("Revisar con otra persona:", sum(f["al_limite"] for f in filas), "filas al límite")
    ARCHIVO_MATRIZ.write_text(a_markdown(filas), encoding="utf-8")
    print(f"Matriz escrita en docs/{ARCHIVO_MATRIZ.name}")


if __name__ == "__main__":
    main()
