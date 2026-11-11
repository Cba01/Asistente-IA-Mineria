"""Revisión manual de una muestra de respuestas evaluadas (U2.2, Bloque 17).

Muestra: 12 de los 20 casos de docs/resultados_metricas.json (2026-11-10, gemini-3.5-flash-lite):
- los 5 con F1 más bajo,
- los 5 con F1 más alto,
- 2 casos de F1 intermedio donde la lectura detectó un problema que la métrica no refleja.

Rúbrica (tres preguntas):
- correccion_factual: ¿lo que dice es correcto?          (si / parcial / no)
- completitud: ¿cubre lo esencial de la referencia?        (si / parcial / no)
- contradiccion: ¿contradice a la referencia?             (si / no)

Uso desde la raíz del repo:  python -m src.revision_manual
Genera docs/revision_manual.json.
"""
import json
from pathlib import Path

ARCHIVO_SALIDA = Path("docs/revision_manual.json")

REVISION_MANUAL = [
    # ---------- F1 más bajos ----------
    {
        "caso": 17,
        "pregunta": "¿Por qué cada trabajador debe usar su propio candado?",
        "f1": 0.16,
        "correccion_factual": "si",
        "completitud": "parcial",
        "contradiccion": "no",
        "nota": "Respuesta correcta dicha con otras palabras ('bloqueo exclusivo', 'evitar que otra persona reactive'). "
                "No menciona la idea clave de que el equipo queda bloqueado hasta que todos retiren su candado. "
                "La métrica la castiga como la peor, pero es una paráfrasis válida.",
    },
    {
        "caso": 20,
        "pregunta": "¿Por qué hay que delimitar el área de trabajo?",
        "f1": 0.23,
        "correccion_factual": "si",
        "completitud": "si",
        "contradiccion": "no",
        "nota": "Dice lo mismo que la referencia con sinónimos ('personal no autorizado' en vez de 'personas ajenas') "
                "y agrega ejemplos correctos (caídas, atropellos). Respuesta buena con F1 muy bajo.",
    },
    {
        "caso": 4,
        "pregunta": "¿Qué concentración de oxígeno debe haber para entrar a un espacio confinado?",
        "f1": 0.26,
        "correccion_factual": "no",
        "completitud": "parcial",
        "contradiccion": "si",
        "nota": "Da un rango de 19,5 % a 22 %, pero el límite superior de referencia es 23,5 %. "
                "Además afirma que es 'según la normativa chilena vigente' sin respaldo. Error factual en una cifra de seguridad. "
                "Aquí el F1 bajo sí coincide con una mala respuesta, pero por casualidad: el límite equivocado "
                "solo cambia una palabra ('22' en vez de '235').",
    },
    {
        "caso": 9,
        "pregunta": "¿Basta con apagar un equipo desde la botonera para intervenirlo?",
        "f1": 0.32,
        "correccion_factual": "si",
        "completitud": "parcial",
        "contradiccion": "no",
        "nota": "Responde 'No' correctamente y exige bloqueo LOTO y verificación de energía cero. "
                "Usa la sigla LOTO en vez de nombrar el interruptor, el candado y la tarjeta, por eso la métrica no encuentra esas palabras.",
    },
    {
        "caso": 10,
        "pregunta": "¿Qué es el bloqueo y etiquetado de energías?",
        "f1": 0.35,
        "correccion_factual": "si",
        "completitud": "parcial",
        "contradiccion": "no",
        "nota": "Definición correcta, pero no menciona el candado ni la tarjeta, que son el núcleo del procedimiento. "
                "Agrega una frase genérica sobre proteger la vida que no aporta y baja la precisión.",
    },
    # ---------- F1 más altos ----------
    {
        "caso": 5,
        "pregunta": "¿Cuántos representantes tiene un Comité Paritario de Higiene y Seguridad?",
        "f1": 0.70,
        "correccion_factual": "si",
        "completitud": "parcial",
        "contradiccion": "no",
        "nota": "Es el F1 más alto, pero la respuesta está CORTADA: termina en 'Ambos'. "
                "Tampoco menciona que es obligatorio en empresas de más de 25 trabajadores. "
                "La métrica no detecta respuestas truncadas: una respuesta incompleta obtuvo el mejor puntaje.",
    },
    {
        "caso": 2,
        "pregunta": "¿Qué ley regula el seguro de accidentes del trabajo en Chile?",
        "f1": 0.68,
        "correccion_factual": "si",
        "completitud": "si",
        "contradiccion": "no",
        "nota": "Correcta y completa (Ley 16.744). La segunda frase es relleno y baja la precisión, pero no es incorrecta.",
    },
    {
        "caso": 3,
        "pregunta": "¿Cuál es el límite de exposición a ruido en una jornada de 8 horas?",
        "f1": 0.61,
        "correccion_factual": "si",
        "completitud": "si",
        "contradiccion": "no",
        "nota": "Correcta: 85 dB(A) en 8 horas según el DS 594. Agrega una indicación general sobre protección auditiva.",
    },
    {
        "caso": 12,
        "pregunta": "¿Qué es un PTS?",
        "f1": 0.53,
        "correccion_factual": "si",
        "completitud": "si",
        "contradiccion": "no",
        "nota": "Correcta y completa. Agrega una frase de relleno sobre la obligatoriedad.",
    },
    {
        "caso": 6,
        "pregunta": "¿Se puede usar el pull cord de una correa como bloqueo para intervenirla?",
        "f1": 0.51,
        "correccion_factual": "si",
        "completitud": "si",
        "contradiccion": "no",
        "nota": "Responde 'No' correctamente y explica por qué. Ojo: si hubiera respondido 'Sí' con las mismas palabras, "
                "el F1 casi no cambiaría, porque 'no' es una sola palabra entre muchas.",
    },
    # ---------- F1 intermedio, con problemas que la métrica no refleja ----------
    {
        "caso": 14,
        "pregunta": "¿Qué enfermedad produce la exposición prolongada a polvo de sílice?",
        "f1": 0.38,
        "correccion_factual": "parcial",
        "completitud": "parcial",
        "contradiccion": "no",
        "nota": "Escribe 'silicose' (portugués) en vez de 'silicosis': la palabra más importante de la respuesta está mal. "
                "Aun así la cobertura es 0,78, porque el resto de la oración coincide. "
                "Es la misma falla de idioma que se observó con este modelo en la comparación de la U1.4.",
    },
    {
        "caso": 16,
        "pregunta": "¿Qué se debe hacer después de instalar el candado de bloqueo?",
        "f1": 0.45,
        "correccion_factual": "si",
        "completitud": "parcial",
        "contradiccion": "no",
        "nota": "Omite liberar o bloquear las energías residuales, un paso crítico antes de verificar energía cero. "
                "Agrega un paso administrativo (registrar la tarjeta). La omisión de un paso de seguridad casi no baja el F1.",
    },
]


def main() -> None:
    ARCHIVO_SALIDA.write_text(json.dumps(REVISION_MANUAL, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Revisión manual guardada en {ARCHIVO_SALIDA} ({len(REVISION_MANUAL)} casos)")


if __name__ == "__main__":
    main()
