# Decisión de personalización: Asistente IA de Seguridad Minera

Método de la U2.6 (Bloque 30), aplicado con `python -m src.decision` el 2026-11-20. Cada respuesta se apoya en un dato del proyecto, no en una impresión.

## 1. El problema

El asistente tiene que responder consultas de seguridad con información **propia de la faena** (sus PTS, sus estándares internos) y de la **normativa chilena**, que el modelo base no conoce o recuerda mal. En el Módulo 1 dio un rango de oxígeno equivocado (19,5–22 % en vez de 19,5–23,5 %) atribuido a "la normativa vigente". Además, las respuestas deben tener un formato consistente: texto plano, completas y breves.

## 2. Resultado del método de decisión

| Pregunta | Respuesta | Evidencia |
|---|---|---|
| ¿La información cambia seguido? | **Sí** | Los 8 documentos del corpus se crearon o modificaron en los últimos 3 meses; 3 PTS se corrigieron el 2026-11-19 para alinearlos con el agente. En una faena real, los PTS se agregan y revisan por cambios de equipos, incidentes y auditorías. |
| ¿Hay un problema de formato o tono? | **Sí** | `python -m src.medir_formato`: **7 de 20** respuestas reales de la U2.2 (**35 %**, umbral 15 %) incumplen algún criterio: 5 con markdown y 2 cortadas. Ninguna supera las 2 oraciones y ninguna tiene letras de otro alfabeto. |
| ¿Hay un dataset grande y de calidad? | **No** | `src/dataset_tuning.py` tiene **21 ejemplos** etiquetados y validados; el umbral es 200. |
| ¿Presupuesto limitado o iteración rápida? | **Sí** | Plan gratuito de Gemini: no se puede pagar ningún entrenamiento. Un cambio de prompt o de corpus se prueba en minutos. |
| ¿Se necesitan varias variantes del modelo? | **No** | Una sola faena y un solo comportamiento esperado. |

**Puntaje:** RAG 5 · PEFT 3 · Fine-tuning completo 1. **Ganador claro: RAG**, sin empate.

**Sensibilidad** (cambiando una respuesta a la vez):

| Si cambiara... | Recomendación |
|---|---|
| La información **no** cambia seguido | PEFT (cambia) |
| **No** hay problema de formato | RAG (igual) |
| **Sí** hay dataset grande | RAG (igual) |
| **No** hay presupuesto limitado | RAG (igual) |
| **Sí** se necesitan variantes | Empate RAG / PEFT (cambia) |

La respuesta que decide es **"la información cambia seguido"**: es también la más discutible, porque la evidencia viene de un corpus de proyecto, no de una faena real.

## 3. Técnica elegida y por qué

**Elijo RAG**, que ya está implementado en la U2.5 (`src/indexar_corpus.py` y `src/recuperacion.py`), y **descarto por ahora PEFT y el fine-tuning completo.**

- **RAG sigue siendo correcto aunque la información no cambiara seguido.** Si esa respuesta fuera falsa, el puntaje recomendaría PEFT. Pero el problema central no es solo que la información cambie: es que el modelo **no tiene** los datos de la faena. El curso advierte que el fine-tuning no sirve para enseñar hechos nuevos, porque el modelo los memoriza mal y los mezcla con lo que ya sabía. RAG además entrega la fuente citada, y la evaluación del Bloque 27 dio un recall de 0,964.
- **El problema de formato existe, pero no es del modelo.** Las 2 respuestas cortadas se generaron antes de corregir `extraer_texto`, que leía solo `parts[0]`: era un bug del cliente, ya corregido. Las 5 con markdown respondían a un prompt de evaluación que no pedía texto plano: el de `src/evaluar_salidas.py` solo dice "Responde siempre en español, de forma directa, en una o dos frases", y esa parte sí se cumplió (ninguna respuesta pasó de 2 oraciones). Los prompts del proyecto desde la U2.3 piden "texto plano, sin markdown", y el clasificador de riesgo usa `response_schema`, que en el Módulo 1 dio 9 de 9 salidas con el formato correcto. Corregir el formato con el prompt cuesta cero; PEFT costaría etiquetar casi 180 ejemplos más y pagar entrenamientos.
- **PEFT queda como plan B, con un criterio objetivo para activarlo:** si al volver a medir con los prompts actuales sigue fallando el 15 % o más de las respuestas, se entrena un adapter para el clasificador de riesgo con el dataset de `src/dataset_tuning.py`.

## 4. Qué se necesitaría para ejecutarla

**RAG (elegido):**

- El corpus tiene 8 documentos (44 chunks). Revisando a mano las 20 preguntas de la U2.2 contra el corpus, **6 no tienen respuesta en él**: qué es un AST, qué es un PTS, el barbiquejo del casco, si un cinturón de seguridad sirve para detener una caída, si se puede pasar bajo una carga suspendida durante un izaje e intervenir una correa inclinada. Faltan **4 documentos**:
  - un glosario de seguridad (AST, PTS, permiso de trabajo),
  - un estándar de EPP (casco, barbiquejo, arnés frente a cinturón),
  - un PTS de izaje (zona de exclusión bajo la carga, señalero, revisión de eslingas),
  - un PTS de correas inclinadas.
- Indexarlos toma segundos con `python -m src.indexar_corpus` y no requiere reentrenar nada.
- Después, repetir la evaluación del Bloque 27 agregando casos de esos temas.
- Pendiente de la U2.5: medir también la generación. Ya van 3 respuestas "no tengo información" con el chunk correcto recuperado (Bloques 26, 28 y 31).

**PEFT (solo si se activa el plan B):**

- **Datos:** hay 21 ejemplos validados y se necesitan al menos 200, así que faltan **179**. A 5 minutos por ejemplo son unas **15 horas** de etiquetado, más una revisión de una muestra.
- **Balance:** la categoría menos representada es `criticidad: media`, con 3 ejemplos frente a 11 de `alta`. Habría que priorizarla al completar el dataset.
- **Cuenta:** se necesita una cuenta con tuning habilitado y presupuesto para al menos 2 intentos de entrenamiento. Hoy no se cumple ninguna de las dos condiciones.
