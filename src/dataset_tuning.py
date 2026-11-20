"""Dataset de tuning para la clasificación de riesgo (U2.6, Bloque 29).

Tarea: dada la consulta de un trabajador, devolver SIEMPRE el mismo JSON que el
prompt "clasificar_riesgo" de prompts/banco.py:
    {"tipo_riesgo": ..., "requiere_bloqueo": true/false, "criticidad": ...}

Es un problema de comportamiento consistente (formato y criterio de clasificación
fijos), no de información faltante: por eso es candidato a PEFT y no a RAG.

Criterios de etiquetado (escritos ANTES de etiquetar, para no ser inconsistente):
- tipo_riesgo: el riesgo PRINCIPAL de la tarea (uno solo).
- requiere_bloqueo: true si la tarea interviene un equipo o circuito con energía
  que podría activarse mientras alguien trabaja en él.
- criticidad: alta si puede causar una lesión grave o fatal; media si puede causar
  una lesión que requiere atención médica; baja si a lo más causa una lesión leve.

Este script NO envía un trabajo de tuning: solo construye, revisa y valida el dataset.
Uso desde la raíz del repo:  python -m src.dataset_tuning
"""
import json
from collections import Counter

from google.genai import types

from prompts.banco import BANCO_DE_PROMPTS

# Las categorías válidas se leen del esquema real del prompt, no se copian a mano:
# si cambia el esquema en banco.py, la validación lo detecta.
ESQUEMA = next(p for p in BANCO_DE_PROMPTS if p["nombre"] == "clasificar_riesgo")["response_schema"]
CLAVES = tuple(ESQUEMA["required"])
VALORES_TIPO = set(ESQUEMA["properties"]["tipo_riesgo"]["enum"])
VALORES_CRITICIDAD = set(ESQUEMA["properties"]["criticidad"]["enum"])


def salida(tipo: str, bloqueo: bool, criticidad: str) -> dict:
    return {"tipo_riesgo": tipo, "requiere_bloqueo": bloqueo, "criticidad": criticidad}


# 21 ejemplos: 3 por cada uno de los 7 tipos de riesgo.
EJEMPLOS_RAW = [
    # atrapamiento
    ("Tengo que cambiar un rodillo de la correa CT-01.", salida("atrapamiento", True, "alta")),
    ("Hay que sacar el material acumulado bajo la polea de cola de la correa.", salida("atrapamiento", True, "alta")),
    ("Voy a revisar desde el pasillo que las guardas de la correa estén puestas, sin abrirlas.",
     salida("atrapamiento", False, "baja")),
    # caida_altura
    ("Debo inspeccionar los pernos de una estructura a 6 metros de altura.", salida("caida_altura", False, "alta")),
    ("Voy a limpiar la canaleta del techo de la bodega, a unos 4 metros.", salida("caida_altura", False, "alta")),
    ("Tengo que subir dos peldaños de una escalera para leer un manómetro.", salida("caida_altura", False, "baja")),
    # electrico
    ("Hay que cambiar un interruptor en el tablero eléctrico de la sala de bombas.", salida("electrico", True, "alta")),
    ("Debo reapretar los terminales de la caja de conexiones de un motor.", salida("electrico", True, "alta")),
    ("Voy a cambiar el enchufe de un hervidor de la oficina, ya desenchufado.", salida("electrico", False, "baja")),
    # vehiculos
    ("Tengo que cruzar a pie la ruta de los camiones de extracción para llegar al taller.",
     salida("vehiculos", False, "alta")),
    ("Voy a guiar el retroceso de una camioneta en el estacionamiento del campamento.",
     salida("vehiculos", False, "media")),
    ("Debo manejar una camioneta de noche por el camino interior de la mina.", salida("vehiculos", False, "media")),
    # sustancias_peligrosas
    ("Voy a trasvasijar ácido sulfúrico desde un bidón a un estanque.", salida("sustancias_peligrosas", False, "alta")),
    ("Hay que limpiar un derrame chico de aceite hidráulico en el taller.",
     salida("sustancias_peligrosas", False, "baja")),
    ("Hay que destapar la línea de descarga de la bomba de solución de cianuro.",
     salida("sustancias_peligrosas", True, "alta")),
    # izaje
    ("Vamos a levantar un motor de 2 toneladas con el puente grúa.", salida("izaje", False, "alta")),
    ("Hay que cambiar el cable de acero del puente grúa.", salida("izaje", True, "alta")),
    ("Voy a revisar las eslingas antes de empezar el turno.", salida("izaje", False, "baja")),
    # otro
    ("Me tropecé con una manguera en el pasillo del taller.", salida("otro", False, "baja")),
    ("Voy a trabajar toda la tarde a pleno sol en el patio de acopio.", salida("otro", False, "media")),
    ("Hay que revisar la fecha de carga de los extintores del campamento.", salida("otro", False, "baja")),
]


def construir_ejemplos(ejemplos_raw=EJEMPLOS_RAW) -> list[types.TuningExample]:
    """Convierte (texto, dict) al formato que exige la API de tuning: el output es el JSON exacto."""
    return [types.TuningExample(text_input=texto, output=json.dumps(sal, ensure_ascii=False))
            for texto, sal in ejemplos_raw]


def chequear_balance(ejemplos_raw, clave: str) -> Counter:
    return Counter(sal[clave] for _, sal in ejemplos_raw)


def validar_dataset(examples: list[types.TuningExample]) -> list[str]:
    """Revisa cada ejemplo y reporta TODOS los problemas, no solo el primero.

    Además de lo que valida el curso (vacíos, duplicados, JSON válido, claves),
    revisa que los valores estén dentro del esquema real de banco.py: un modelo
    entrenado con un "Alta" o un "caida" mal escrito aprendería a producirlos.
    """
    problemas, vistos = [], set()
    for i, ej in enumerate(examples):
        if not ej.text_input or not ej.text_input.strip():
            problemas.append(f"ejemplo {i}: text_input vacío")
        elif ej.text_input in vistos:
            problemas.append(f"ejemplo {i}: text_input duplicado")
        vistos.add(ej.text_input)

        if not ej.output or not ej.output.strip():
            problemas.append(f"ejemplo {i}: output vacío")
            continue
        try:
            sal = json.loads(ej.output)
        except json.JSONDecodeError:
            problemas.append(f"ejemplo {i}: output no es JSON válido")
            continue

        for clave in CLAVES:
            if clave not in sal:
                problemas.append(f'ejemplo {i}: falta la clave "{clave}"')
        extras = set(sal) - set(CLAVES)
        if extras:
            problemas.append(f"ejemplo {i}: claves que no están en el esquema: {sorted(extras)}")
        if "tipo_riesgo" in sal and sal["tipo_riesgo"] not in VALORES_TIPO:
            problemas.append(f'ejemplo {i}: tipo_riesgo "{sal["tipo_riesgo"]}" no está en el esquema')
        if "criticidad" in sal and sal["criticidad"] not in VALORES_CRITICIDAD:
            problemas.append(f'ejemplo {i}: criticidad "{sal["criticidad"]}" no está en el esquema')
        if "requiere_bloqueo" in sal and not isinstance(sal["requiere_bloqueo"], bool):
            problemas.append(f"ejemplo {i}: requiere_bloqueo debe ser true/false, no texto")
    return problemas


def main() -> None:
    examples = construir_ejemplos()
    print(f"{len(examples)} ejemplos construidos")
    print("Ejemplo:", examples[0].text_input, "->", examples[0].output)

    for clave in CLAVES:
        balance = chequear_balance(EJEMPLOS_RAW, clave)
        conteo = ", ".join(f"{k}: {v}" for k, v in balance.most_common())
        razon = max(balance.values()) / min(balance.values())
        print(f"\nBalance de {clave}: {conteo}  (razón máx/mín {razon:.1f}x)")
    faltantes = VALORES_TIPO - set(chequear_balance(EJEMPLOS_RAW, "tipo_riesgo"))
    if faltantes:
        print("Tipos de riesgo del esquema sin ningún ejemplo:", sorted(faltantes))

    problemas = validar_dataset(examples)
    print(f"\nValidación: {len(examples)} ejemplos, {len(problemas)} problemas")
    for p in problemas:
        print(" -", p)

    # Prueba del validador con un dataset roto a propósito.
    rotos = examples + [
        types.TuningExample(text_input="", output='{"tipo_riesgo": "electrico"}'),
        types.TuningExample(text_input=EJEMPLOS_RAW[0][0],
                            output='{"tipo_riesgo": "caida", "requiere_bloqueo": "si", "criticidad": "Alta"}'),
    ]
    problemas_rotos = validar_dataset(rotos)
    print(f"\nPrueba con 2 ejemplos rotos a propósito: {len(problemas_rotos)} problemas detectados")
    for p in problemas_rotos:
        print(" -", p)


if __name__ == "__main__":
    main()
