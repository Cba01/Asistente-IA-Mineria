"""Casos de evaluación: preguntas de seguridad minera con una referencia escrita a mano.
La referencia es la respuesta esperada contra la que se comparan las salidas del modelo.
Datos numéricos verificados con fuentes chilenas (ACHS, ISP, DS 594, DS 54) el 2026-11-10."""

CASOS = [
    # Datos numéricos y normativa (la métrica suele fallar con cifras)
    {"pregunta": "¿Desde qué altura se considera trabajo en altura?",
     "referencia": "Se considera trabajo en altura desde 1,8 metros sobre el nivel inferior."},
    {"pregunta": "¿Qué ley regula el seguro de accidentes del trabajo en Chile?",
     "referencia": "El seguro de accidentes del trabajo y enfermedades profesionales está regulado por la Ley 16.744."},
    {"pregunta": "¿Cuál es el límite de exposición a ruido en una jornada de 8 horas?",
     "referencia": "Según el DS 594, el límite de exposición a ruido es de 85 dB(A) para una jornada de 8 horas."},
    {"pregunta": "¿Qué concentración de oxígeno debe haber para entrar a un espacio confinado?",
     "referencia": "El oxígeno debe estar entre 19,5 % y 23,5 %; bajo ese rango hay deficiencia y sobre él hay riesgo por exceso de oxígeno."},
    {"pregunta": "¿Cuántos representantes tiene un Comité Paritario de Higiene y Seguridad?",
     "referencia": "El Comité Paritario tiene tres representantes de la empresa y tres de los trabajadores, y es obligatorio en empresas de más de 25 trabajadores."},

    # Preguntas de sí o no (la métrica suele fallar con negaciones)
    {"pregunta": "¿Se puede usar el pull cord de una correa como bloqueo para intervenirla?",
     "referencia": "No. El pull cord es un dispositivo de parada de emergencia, no de aislamiento; para intervenir hay que bloquear en el interruptor."},
    {"pregunta": "¿Se puede usar un cinturón de seguridad para detener una caída?",
     "referencia": "No. Para detener una caída se debe usar un arnés de cuerpo completo; el cinturón solo sirve para posicionamiento."},
    {"pregunta": "¿Se puede pasar bajo una carga suspendida durante un izaje?",
     "referencia": "No. Nunca se debe pasar ni permanecer bajo una carga suspendida."},
    {"pregunta": "¿Basta con apagar un equipo desde la botonera para intervenirlo?",
     "referencia": "No. Hay que aislar la energía en el interruptor, instalar candado y tarjeta, y verificar energía cero."},

    # Conceptos
    {"pregunta": "¿Qué es el bloqueo y etiquetado de energías?",
     "referencia": "Es un procedimiento que aísla las fuentes de energía de un equipo con candado y tarjeta para evitar que se energice mientras se interviene."},
    {"pregunta": "¿Qué es un AST?",
     "referencia": "El AST, Análisis Seguro de Trabajo, identifica los peligros de una tarea y sus medidas de control antes de ejecutarla."},
    {"pregunta": "¿Qué es un PTS?",
     "referencia": "El PTS, Procedimiento de Trabajo Seguro, describe paso a paso cómo realizar una tarea de forma segura."},
    {"pregunta": "¿Qué es el DS 132?",
     "referencia": "El DS 132 es el Reglamento de Seguridad Minera de Chile."},
    {"pregunta": "¿Qué enfermedad produce la exposición prolongada a polvo de sílice?",
     "referencia": "La exposición prolongada a polvo de sílice produce silicosis."},
    {"pregunta": "¿Qué es la energía residual en un equipo?",
     "referencia": "Es la energía que queda acumulada en un equipo después de desconectarlo, como tensión mecánica, presión o gravedad."},

    # Procedimientos
    {"pregunta": "¿Qué se debe hacer después de instalar el candado de bloqueo?",
     "referencia": "Después de instalar el candado y la tarjeta hay que liberar o bloquear las energías residuales y verificar energía cero intentando arrancar el equipo."},
    {"pregunta": "¿Por qué cada trabajador debe usar su propio candado?",
     "referencia": "Cada trabajador usa su propio candado para que el equipo no se pueda energizar hasta que todos hayan retirado el suyo."},
    {"pregunta": "¿Para qué sirve el barbiquejo del casco?",
     "referencia": "El barbiquejo mantiene el casco firme en la cabeza para que no se caiga con un golpe, el viento o al agacharse."},
    {"pregunta": "¿Qué se debe hacer antes de intervenir una correa inclinada?",
     "referencia": "Antes de intervenir una correa inclinada hay que bloquear la energía y trabar mecánicamente la correa para que no se mueva por gravedad."},
    {"pregunta": "¿Por qué hay que delimitar el área de trabajo?",
     "referencia": "Hay que delimitar el área para impedir que personas ajenas ingresen a la zona de riesgo."},
]