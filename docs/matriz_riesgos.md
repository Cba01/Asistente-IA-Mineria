# Matriz de riesgos: Asistente IA de Seguridad Minera

Generada con `python -m src.matriz_riesgos`. Probabilidad (P) e impacto (I) de 1 a 5, estimados con las mitigaciones actuales. Puntaje = P × I. Cortes: CRÍTICO ≥ 15, ALTO ≥ 9, MEDIO ≥ 4. "Al límite" = un punto de diferencia en P o I cambia la categoría.

| # | Riesgo | P | I | Puntaje | Categoría | Mitigación actual | Supervisión humana |
|---|---|---|---|---|---|---|---|
| 1 | API caída o cuota agotada (429/503) justo durante una consulta de emergencia | 3 | 4 | 12 | **ALTO** (al límite) | Reintentos con backoff (U2.1) y respuesta de emergencia fija sin modelo (U2.3) | Si se usa la respuesta de respaldo, se notifica al supervisor de turno |
| 2 | El agente autoriza una intervención ('puedes intervenirlo') mirando solo el estado del equipo, sin permiso de trabajo, AST ni certificaciones | 2 | 5 | 10 | **ALTO** (al límite) | Prompt del agente que informa sin autorizar + revisión en código que agrega la aclaración si la respuesta suena a autorización (revisar_autorizacion en src/agente.py, Gate 2) | La autorización para intervenir siempre la da el supervisor con el permiso de trabajo; el asistente solo informa. Revisión diaria de trazas con 'puedes' en la respuesta |
| 3 | Respuesta con un dato de seguridad incorrecto (cifra, límite o paso omitido) que el trabajador sigue | 2 | 5 | 10 | **ALTO** (al límite) | RAG con fuente citada y detección de citas inventadas (Bloque 26, recall 0,964 en el Bloque 27) + advertencia al final de cada respuesta | Los documentos del corpus los aprueba un prevencionista antes de indexarlos; revisión semanal de respuestas con citas inválidas o sin citas (logs/rag.jsonl) |
| 4 | Inyección de prompt vía un documento del corpus que cambie una instrucción de seguridad (por ejemplo, 'no es necesario bloquear') | 2 | 5 | 10 | **ALTO** (al límite) | Filtro de patrones + SystemMessage + contexto entre etiquetas <contexto> (src/logging_rag.py, Bloque 31) | Un chunk descartado por el filtro genera un WARNING y bloquea su documento hasta que una persona lo revise; ningún documento entra al corpus sin aprobación |
| 5 | Datos personales de trabajadores (códigos, cursos, vencimientos) expuestos en logs o a usuarios no autorizados | 3 | 3 | 9 | **ALTO** (al límite) | Los logs guardan largo y huella de la pregunta, no su texto (Bloque 31) | Acceso a logs y a la herramienta de certificaciones solo para supervisores, aprobado por el jefe de área |
| 6 | Un cambio de prompt empeora las respuestas sin que nadie lo note | 3 | 3 | 9 | **ALTO** (al límite) | Versionado con huella, huella del prompt en cada log, evaluación de la generación por versión (src/evaluar_generacion.py) y el servicio se niega a responder con un prompt no aprobado (src/servicio_rag.py, Gate 2) | Grafo de aprobación antes de activar una versión (src/grafo_supervision.py, Bloque 32) |
| 7 | PTS revisado en la faena pero no reindexado: el asistente cita una versión vieja | 2 | 4 | 8 | **MEDIO** (al límite) | Reindexación completa y sin duplicados con un solo comando (Bloque 24) | No requiere |
| 8 | El modelo responde 'no tengo información' teniendo el documento correcto en el contexto | 3 | 2 | 6 | **MEDIO** (al límite) | Prompts v2 y v4 (relacionar términos, no decir 'no sé' si algún fragmento trata el tema), campo sin_informacion en logs y evaluación de la generación (Gate 2) | No requiere |
| 9 | El modelo de texto o de embeddings cambia o queda deprecado | 2 | 3 | 6 | **MEDIO** (al límite) | Modelo configurable en .env y decisión documentada (U1.4); el índice guarda el modelo de embeddings usado | No requiere |

## Evidencia de cada estimación

1. 503 frecuentes con 3.6-flash y 429 en el ensayo de rate limit (U2.1); plan gratuito.
2. Ocurrió en la corrida real del 2026-11-19 (U2.4). Tras la corrección, la corrida del 2026-11-23 no autorizó en ninguna de las 4 consultas.
3. Módulo 1: rango de oxígeno 19,5-22 % en vez de 19,5-23,5 %; U2.2: paso de energías residuales omitido.
4. El corpus es interno, pero se planea agregar documentos; el filtro por patrones no detecta frases reescritas.
5. La herramienta consultar_certificaciones_trabajador devuelve datos personales (U2.4); las preguntas pueden incluir códigos de trabajador.
6. El prompt del RAG tuvo 4 versiones; la v3 se aprobó sin medir y agregó faltantes inventados (2 de 15), corregidos en la v4 aprobada con evaluación.
7. El índice no se actualiza solo (Bloque 25).
8. 3 casos reales: estanque (Bloque 26), vigía (Bloque 28) y otra pregunta del vigía con el prompt v3 (Bloque 31), siempre con el chunk correcto recuperado.
9. Nombres de modelo inconsistentes en el curso; cambio forzado de 3.6-flash a flash-lite.
