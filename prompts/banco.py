SISTEMA_BASE = "Eres un asistente de seguridad para faenas mineras en Chile. Responde siempre en español. "

BANCO_DE_PROMPTS = [
    {
        "nombre": "clasificar_riesgo",
        "system_instruction": SISTEMA_BASE + (
            "Clasifica la consulta del trabajador según el principal tipo de riesgo involucrado, "
            "indica si requiere bloqueo de energías y su nivel de criticidad."
        ),
        "ejemplo_usuario": "Tengo que cambiar un rodillo de la correa del chancador primario.",
        "claves_esperadas": ["tipo_riesgo", "requiere_bloqueo", "criticidad"],
        "response_schema": {
            "type": "OBJECT",
            "properties": {
                "tipo_riesgo": {
                    "type": "STRING",
                    "enum": ["atrapamiento", "caida_altura", "electrico", "vehiculos",
                             "sustancias_peligrosas", "izaje", "otro"],
                },
                "requiere_bloqueo": {"type": "BOOLEAN"},
                "criticidad": {"type": "STRING", "enum": ["alta", "media", "baja"]},
            },
            "required": ["tipo_riesgo", "requiere_bloqueo", "criticidad"],
        },
    },
    {
        "nombre": "extraer_epp",
        "system_instruction": SISTEMA_BASE + (
            "A partir de la descripción de una tarea, identifica la tarea principal, "
            "lista el equipo de protección personal necesario y si requiere permiso de trabajo."
        ),
        "ejemplo_usuario": "Voy a soldar una plancha en la pasarela de la correa, a unos 4 metros de altura.",
        "claves_esperadas": ["tarea", "epp", "requiere_permiso"],
        "response_schema": {
            "type": "OBJECT",
            "properties": {
                "tarea": {"type": "STRING"},
                "epp": {"type": "ARRAY", "items": {"type": "STRING"}},
                "requiere_permiso": {"type": "BOOLEAN"},
            },
            "required": ["tarea", "epp", "requiere_permiso"],
        },
    },
    {
        "nombre": "resumir_procedimiento",
        "system_instruction": SISTEMA_BASE + (
            "Resume el procedimiento entregado en una frase y extrae como máximo 5 pasos clave, "
            "en el orden en que deben ejecutarse."
        ),
        "ejemplo_usuario": (
            "Antes de intervenir la correa, el supervisor emite el permiso de trabajo. El mantenedor "
            "detiene la correa desde la sala de control, abre el interruptor en el CCM e instala su "
            "candado y tarjeta personal. Luego traba el contrapeso del take-up y verifica energía cero "
            "intentando arrancar desde la botonera local. Finalmente delimita el área con conos y cadena."
        ),
        "claves_esperadas": ["resumen", "pasos_clave"],
        "response_schema": {
            "type": "OBJECT",
            "properties": {
                "resumen": {"type": "STRING"},
                "pasos_clave": {"type": "ARRAY", "items": {"type": "STRING"}},
            },
            "required": ["resumen", "pasos_clave"],
        },
    },
]