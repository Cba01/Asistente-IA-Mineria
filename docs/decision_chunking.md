# Decisión de chunking del corpus

Corpus: 8 documentos en `corpus/`. Son 4 PTS ficticios y 4 resúmenes de normativa pública (DS 132, DS 594, Ley 16.744 y DS 40), cada uno organizado en secciones `##`.

## Estrategia

1. **Cada documento se parte por secciones `##`** antes de aplicar el splitter, así un chunk nunca mezcla dos temas (por ejemplo, "Requisitos previos" y "Riesgos").
2. **Dentro de cada sección** se usa `RecursiveCharacterTextSplitter` con `chunk_size=500` y `chunk_overlap=80` (16 %). Corta entre párrafos o líneas, nunca a mitad de un paso.
3. **Cada chunk empieza con el título del documento y de su sección.** Sin esto, una pieza como "6. Verificar energía cero..." no dice de qué procedimiento es, ni para la búsqueda ni para el modelo que la lee.
4. **El aviso inicial** ("Documento FICTICIO..." o "Resumen orientativo...") no se indexa como chunk propio: no responde ninguna pregunta y solo competiría con los chunks útiles.

## Comparación (`python -m src.indexar_corpus --comparar`)

| chunk_size | Chunks | Secciones divididas en más de un chunk | Observación |
|---|---|---|---|
| 300 | 54 | 13 piezas extra | Los pasos de un procedimiento quedan repartidos en varios chunks. |
| **500** | **44** | **3 piezas extra** | Casi todas las secciones quedan completas. Solo se dividen las listas de pasos largas. |
| 800 | 42 | 1 pieza extra | Casi igual que 500, pero los chunks de pasos se vuelven largos y suman más tokens a cada consulta. |

Se eligió **500**. Pasar de 500 a 800 casi no cambia la cantidad de chunks, porque las secciones ya son unidades naturales, pero sí aumenta el contexto que se envía al modelo.

## Primera versión descartada

Con el splitter aplicado al documento completo, incluso agregando `"\n## "` como primer separador, quedaban chunks formados solo por un título (por ejemplo `## Pasos del bloqueo`), con su contenido en el chunk siguiente. Partir primero por secciones y repetir el encabezado eliminó ese problema.

## Cuándo reindexar

Hay que volver a correr `python -m src.indexar_corpus` si se agrega, edita o elimina un documento, si cambia `chunk_size` o la estrategia de chunking, o si cambia el modelo de embeddings. El script borra la colección y la reconstruye completa, así que no quedan chunks viejos ni duplicados.
