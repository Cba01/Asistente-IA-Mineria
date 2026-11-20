# Latencia y costo del flujo RAG

Medición real del 2026-11-20 con `python -m src.registro_rag`. Datos en `registros_latencia_costo.jsonl`.

Configuración: `gemini-3.5-flash-lite` para generar, `gemini-embedding-001` para los embeddings, Chroma local, chunk_size 500.

## Resultados

| k | Embed (ms) | Búsqueda (ms) | Generación (ms) | Total (ms) | Tokens entrada | Tokens salida | Costo USD | Pregunta |
|---|---|---|---|---|---|---|---|---|
| 3 | 1205 | 299,4 | 1503 | 3007 | 509 | 62 | 0,000308 | ¿Cómo compruebo que el equipo quedó realmente sin energía? |
| 3 | 1023 | 2,1 | 1393 | 2418 | 466 | 33 | 0,000222 | ¿Qué debe hacer el vigía si alguien se desmaya dentro del estanque? |
| 3 | 999 | 1,4 | 1523 | 2524 | 452 | 62 | 0,000291 | ¿La empresa me puede cobrar los zapatos de seguridad? |
| 6 | 994 | 2,0 | 1522 | 2518 | 764 | 66 | 0,000394 | ¿Cómo compruebo que el equipo quedó realmente sin energía? |

## Lectura

- **La generación es la etapa más lenta** en las 4 consultas (alrededor de 1,5 s). Para reducir la latencia que percibe el usuario, ahí hay que optimizar, por ejemplo mostrando la respuesta a medida que se genera.
- **El embedding de la pregunta pesa casi tanto como la generación** (alrededor de 1 s, cerca del 40 % del total). Es una llamada por red, aunque el texto sea corto.
- **La búsqueda en Chroma es despreciable:** unos 2 ms. La primera consulta tardó 299 ms porque Chroma carga el índice en memoria al buscar por primera vez.
- **Subir k de 3 a 6** aumentó los tokens de entrada un 50 % (de 509 a 764), pero el costo solo un 28 % (de USD 0,000308 a 0,000394), porque los tokens de salida, que son más caros, casi no cambiaron. Según la evaluación del Bloque 27, k=6 no recupera ningún chunk relevante adicional: es costo sin beneficio. Esto confirma k=3.
- **Costo típico:** unos USD 0,0003 por consulta en generación, es decir, unos USD 0,30 cada mil consultas con tarifa pagada. En el plan gratuito, el límite real son las peticiones por minuto y por día, no el costo.

## Hallazgo: el modelo dijo "no sé" con el chunk correcto en la mano

En la consulta del vigía, la búsqueda trajo el chunk correcto en primer lugar (`pts_gen_010_espacios_confinados_5`: "El vigía nunca ingresa a rescatar: da la alarma y activa el plan de rescate"). Aun así, el modelo respondió que no tenía información suficiente. Lo mismo ocurrió en el Bloque 26 con la pregunta del estanque, antes de ajustar el prompt.

Es un falso "no sé" de la generación, no de la búsqueda: un recall alto garantiza que el chunk llegó al contexto, no que el modelo lo use. El campo `sin_informacion` de cada registro permite detectar estos casos.

**Pendiente para el Gate 2:** medir también la generación, contando cuántas respuestas dicen "no sé" teniendo el chunk relevante en el contexto, y ajustar el prompt o probar otro modelo con esa métrica. Para un asistente de seguridad, este error es preferible a inventar, pero reduce su utilidad.
