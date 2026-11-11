# Límites de la métrica de evaluación

## Qué mide

Coincidencia de palabras entre una respuesta generada y una referencia escrita a mano, después de limpiar el texto (minúsculas, sin puntuación) y contando repeticiones: **precisión** (qué parte de la respuesta está en la referencia), **cobertura** (qué parte de la referencia aparece en la respuesta) y **F1** (combinación de ambas). Implementada en `src/pipeline_texto.py`.

## Modos de falla conocidos

Cada caso se puede rastrear en `docs/revision_manual.json` y `docs/resultados_metricas.json`.

- **Paráfrasis correctas puntúan muy bajo.** El caso con el F1 más bajo de toda la evaluación (caso 17, "¿Por qué cada trabajador debe usar su propio candado?", F1 = 0,16) es una respuesta correcta dicha con otras palabras. Lo mismo pasa con el caso 20 (F1 = 0,23), que usa "personal no autorizado" en vez de "personas ajenas".
- **Siglas en lugar de palabras.** Cuando el modelo escribe "LOTO" en vez de "candado y tarjeta", la métrica no encuentra esas palabras y baja el puntaje aunque la respuesta sea correcta (caso 9, F1 = 0,32).
- **Respuestas truncadas pueden obtener el mejor puntaje.** El caso con el F1 más alto (caso 5, Comité Paritario, F1 = 0,70) es una respuesta cortada que termina en "Ambos" y omite un dato de la referencia. La métrica no detecta que la respuesta quedó incompleta.
- **Una palabra clave equivocada casi no cambia el puntaje.** En el caso 14 el modelo escribió "silicose" (portugués) en vez de "silicosis": la palabra más importante está mal, pero la cobertura sigue en 0,78 porque el resto de la oración coincide.
- **Cifras incorrectas pesan como una palabra cualquiera.** En el caso 4 el modelo dio un rango de oxígeno de 19,5 % a 22 % (el límite de referencia es 23,5 %). En una consulta de seguridad, ese error es grave, pero para la métrica es solo una palabra distinta.
- **Las negaciones casi no influyen.** En preguntas de sí o no (casos 6 a 9), la palabra "no" es una entre muchas: una respuesta que dijera "sí" con el mismo resto de la oración obtendría un F1 casi igual.
- **El orden de las palabras no importa.** "El perro persiguió al gato" y "El gato persiguió al perro" obtienen F1 = 1,0 (cubierto por la prueba `test_metricas_no_detectan_orden_invertido`).
- **La limpieza deforma números con decimales.** "1,8 metros" se convierte en "18", y "19,5 %" en "195". Dos cifras distintas solo coinciden si se escriben igual.
- **Omitir un paso de seguridad casi no baja el puntaje.** En el caso 16 la respuesta omite liberar las energías residuales y su F1 (0,45) queda en el promedio.
- **Respuestas más largas que la referencia bajan la precisión.** Aunque se pidió responder en una o dos frases, el modelo agrega frases de relleno ("su cumplimiento es obligatorio..."). Por eso la precisión promedio (0,34) es mucho menor que la cobertura promedio (0,64).
- **La limpieza no siempre sube la coincidencia.** En el caso 18 la coincidencia simple bajó de 62 % a 60 % al limpiar, porque al pasar a minúsculas palabras como "El" y "el" se juntan y cambia el número de palabras distintas de la referencia.

## Muestra revisada

**12 de 20 casos**, evaluados el 2026-11-10 con `gemini-3.5-flash-lite`:

- los 5 con F1 más bajo (casos 17, 20, 4, 9 y 10),
- los 5 con F1 más alto (casos 5, 2, 3, 12 y 6),
- 2 casos de F1 intermedio donde la lectura detectó un problema (casos 14 y 16).

Resultado: de los 5 casos con F1 más bajo, **4 eran respuestas correctas** (solo el caso 4 tenía un error factual). De los 5 con F1 más alto, **1 estaba cortado e incompleto**. Además, la revisión de casos intermedios encontró **una palabra clave en otro idioma** y **un paso de seguridad omitido** que la métrica no detectó.

## Recomendación de uso

Usar el F1 solo para **comparar en volumen** entre versiones del cliente o del prompt (por ejemplo, si un cambio sube o baja el promedio), **nunca para decidir si una respuesta individual es correcta**. Revisar siempre a mano las respuestas con **cifras, normas o pasos de un procedimiento**, y las que estén **cortadas** o tengan **palabras en otro idioma**, sin importar su puntaje.


**Corrección posterior:** las respuestas cortadas (casos 5 y 7) se debían probablemente a que `extraer_texto` solo leía la primera parte de la respuesta. Se corrigió para unir todas las partes.