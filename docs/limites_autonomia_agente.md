# Límites de autonomía: agente de seguridad minera

Agente implementado en `src/agente.py` (U2.4). Usa `create_tool_calling_agent` y `AgentExecutor` con `gemini-3.5-flash-lite`, memoria por sesión y cuatro herramientas. **Todos los datos de equipos, trabajadores y procedimientos son ficticios.**

Este documento describe el agente tal como está construido y probado, respaldado por una corrida real del 2026-11-19 registrada en `trazas_agente.jsonl` y `aprobaciones_agente.jsonl`.

## Herramientas y nivel de riesgo

| Herramienta | Riesgo | Por qué |
|---|---|---|
| `consultar_estado_equipo` | 🟢 Bajo | Solo lee el estado de un equipo. Si el agente la usa mal, el peor caso es una respuesta inútil, no un daño real. |
| `buscar_procedimiento_trabajo_seguro` | 🟢 Bajo | Solo lee un PTS. No modifica nada. |
| `consultar_certificaciones_trabajador` | 🟡 Bajo en acción, sensible en datos | No modifica nada, pero expone **datos personales** de un trabajador (sus cursos y vencimientos). En un sistema real debería limitarse a usuarios autorizados, por ejemplo supervisores. |
| `solicitar_bloqueo_equipo` | 🔴 Alto | **Detiene la producción.** Una detención innecesaria tiene un costo económico directo, y el agente podría invocarla por un malentendido. |

No hay herramientas de riesgo medio (escritura reversible) en esta versión.

## Herramientas que requieren aprobación humana

- **`solicitar_bloqueo_equipo`**: siempre requiere la aprobación de un supervisor antes de ejecutarse.
  - **Cómo está implementado:** la herramienta llama a `esperar_aprobacion()`, que pide confirmación por consola con un límite de 60 segundos. Usa un hilo en vez de `select.select()`, porque `select` no funciona sobre la consola en Windows.
  - **Valor por defecto seguro:** si nadie responde a tiempo, o no hay consola disponible, la solicitud **se rechaza**.
  - **No se pide aprobación** cuando no hay nada que aprobar: si el equipo no existe o ya está bloqueado, la herramienta responde sin generar la solicitud.
  - **Registro:** cada decisión, aprobada o rechazada, se guarda en `aprobaciones_agente.jsonl` con la fecha, los argumentos y el resultado.
  - **Verificado:** en la corrida del 2026-11-19 el agente pidió aprobación para bloquear la CT-01 por "polín dañado", el supervisor respondió "s" y la decisión quedó registrada. Las pruebas de `tests/test_agente.py` cubren la aprobación, el rechazo, la falta de respuesta a tiempo, la falta de consola, y que no se pida aprobación para un equipo inexistente o ya bloqueado.
- **Las demás herramientas no requieren aprobación.** Pedir confirmación para todo haría que el supervisor aprobara por costumbre, sin leer. Las herramientas de solo lectura se revisan después, con la traza.

## Revisión de trazas

- **Qué se registra:** cada interacción se guarda como una línea en `trazas_agente.jsonl`, con la sesión, la pregunta, las herramientas usadas con sus argumentos y observaciones, y la respuesta final (`registrar_traza`).
- **Revisión automática (primera pasada):**
  - `marcar_repeticiones_sospechosas()`: misma herramienta invocada dos veces seguidas en una sesión. Puede indicar que el agente no avanza.
  - `marcar_alto_riesgo_sin_decision()`: una herramienta de riesgo alto que aparece en la traza sin una decisión de aprobación en su observación. Indicaría que la supervisión no funcionó.
  - En la corrida del 2026-11-19 ambas revisiones dieron **"Sin alertas"**.
- **Frecuencia propuesta:**
  - **Todas** las trazas que incluyan `solicitar_bloqueo_equipo`: revisión diaria.
  - Una **muestra semanal** del resto, más cualquier sesión que marquen las revisiones automáticas.
- **Qué se busca a mano**, además de las alertas automáticas:
  - Respuestas finales que afirmen algo que ninguna herramienta devolvió (datos inventados).
  - Respuestas que **autoricen** una tarea basándose solo en una parte de la información (ver hallazgos).

## Hallazgos de la corrida real (2026-11-19)

- **El agente eligió la herramienta correcta en las 4 consultas**, incluida la de riesgo alto, y la memoria resolvió una referencia implícita ("cambiarle un rodillo" se refería a la CT-01).
- **El agente responde "Puedes intervenirlo" mirando solo el estado del equipo.** Ante "¿Puedo intervenir hoy la correa CT-01?", contestó que sí porque el equipo está operativo y con la mantención al día. Pero esa autorización depende también del permiso de trabajo, del AST y de las certificaciones de quien interviene, cosas que el agente no revisó. Recordó aplicar el bloqueo de energías, pero el "puedes" va más allá de lo que sabe. **Mejora pendiente:** ajustar el prompt para que informe el estado del equipo sin dar una autorización.
- **No advierte vencimientos próximos.** Para T-2045 respondió que puede trabajar en altura porque su curso está vigente hasta el 2026-12-01, a 12 días de vencer, sin mencionarlo. **Mejora pendiente:** que `consultar_certificaciones_trabajador` marque los cursos que vencen en menos de 30 días.

## Qué hacer ante un comportamiento inesperado

1. **Si el agente invoca `solicitar_bloqueo_equipo` sin que se haya pedido:** rechazar la aprobación (o dejar que expire), revisar la traza de esa sesión y, si se repite, quitar temporalmente la herramienta de la lista `HERRAMIENTAS` hasta corregir su descripción.
2. **Si aparece una alerta de `marcar_alto_riesgo_sin_decision`:** tratarla como incidente. Desactivar la herramienta de riesgo alto y revisar por qué la aprobación no quedó registrada antes de volver a habilitarla.
3. **Si el agente usa una herramienta equivocada o ninguna cuando debía:** revisar el docstring de la herramienta, que es lo que el modelo lee para decidir; ajustarlo para que describa *cuándo* usarla, y agregar o actualizar la prueba correspondiente.
4. **Si la respuesta final contiene un dato que ninguna herramienta devolvió:** reforzar en el prompt la instrucción de no inventar datos y agregar el caso a la revisión semanal.
5. **Si el agente entra en un bucle:** el ejecutor corta a las 5 iteraciones (`max_iterations=5`). Revisar en la traza qué observación lo hizo repetir y aclarar el texto que devuelve esa herramienta.

## Limitaciones conocidas

- La aprobación por consola es una simulación. En un sistema real vendría de un panel de aprobaciones o una notificación al supervisor. Además, después de un rechazo por tiempo, el hilo de lectura sigue esperando una tecla en segundo plano.
- La memoria (`RunnableWithMessageHistory` e `InMemoryChatMessageHistory`) vive en la memoria del proceso: se pierde al reiniciar y está marcada como obsoleta en LangChain 2.0. La alternativa recomendada es la persistencia de LangGraph (deuda técnica para el Gate 3).
- `solicitar_bloqueo_equipo` no bloquea nada realmente: genera la solicitud. El bloqueo físico lo hace una persona en terreno.
