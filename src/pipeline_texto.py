"""Pipeline de procesamiento de texto y métricas de evaluación (U2.2).

Limpia y tokeniza texto, y compara una respuesta generada contra una referencia
con precisión, cobertura y F1 (contando repeticiones de palabras).
No usa librerías externas ni llama a la API.
"""
import re
from collections import Counter


def limpiar_texto(texto: str) -> str:
    """Normaliza el texto: minúsculas, sin puntuación y sin espacios repetidos.
    Conserva tildes, ñ y números."""
    if not isinstance(texto, str):
        raise TypeError(f"limpiar_texto espera str, no {type(texto).__name__}")
    texto = texto.lower()
    texto = re.sub(r"[^\w\s]", "", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def tokenizar(texto_limpio: str) -> list[str]:
    """Convierte texto ya limpio en una lista de palabras."""
    return texto_limpio.split()


def procesar_texto(texto: str) -> list[str]:
    """Limpia y tokeniza en un solo paso, para no olvidar ninguno de los dos."""
    return tokenizar(limpiar_texto(texto))


def coincidencia_simple(tokens_referencia: list[str], tokens_respuesta: list[str]) -> float:
    """Métrica ingenua del Bloque 15: proporción de palabras distintas de la referencia
    que aparecen en la respuesta. No cuenta repeticiones."""
    if not tokens_referencia:
        return 0.0
    comunes = set(tokens_referencia) & set(tokens_respuesta)
    return len(comunes) / len(set(tokens_referencia))


def contar_coincidencias(tokens_referencia: list[str], tokens_respuesta: list[str]) -> int:
    """Cuenta las palabras en común respetando repeticiones (mínimo entre ambos lados)."""
    interseccion = Counter(tokens_referencia) & Counter(tokens_respuesta)
    return sum(interseccion.values())


def calcular_precision_cobertura_f1(tokens_referencia: list[str],
                                    tokens_respuesta: list[str]) -> dict[str, float]:
    """Precisión: qué parte de la respuesta está en la referencia.
    Cobertura: qué parte de la referencia aparece en la respuesta.
    F1: combinación de ambas."""
    if not tokens_referencia or not tokens_respuesta:
        return {"precision": 0.0, "cobertura": 0.0, "f1": 0.0}
    coincidencias = contar_coincidencias(tokens_referencia, tokens_respuesta)
    precision = coincidencias / len(tokens_respuesta)
    cobertura = coincidencias / len(tokens_referencia)
    if precision + cobertura == 0:
        f1 = 0.0
    else:
        f1 = 2 * precision * cobertura / (precision + cobertura)
    return {"precision": precision, "cobertura": cobertura, "f1": f1}


def calcular_metricas(texto_referencia: str, texto_respuesta: str) -> dict[str, float]:
    """De dos textos crudos a sus métricas: procesa ambos lados antes de comparar."""
    return calcular_precision_cobertura_f1(procesar_texto(texto_referencia),
                                           procesar_texto(texto_respuesta))


def resumir_metricas(resultados: list[dict]) -> dict[str, float]:
    """Promedia precisión, cobertura y F1 de una lista de resultados."""
    if not resultados:
        return {"precision_promedio": 0.0, "cobertura_promedio": 0.0, "f1_promedio": 0.0}
    n = len(resultados)
    return {
        "precision_promedio": sum(r["precision"] for r in resultados) / n,
        "cobertura_promedio": sum(r["cobertura"] for r in resultados) / n,
        "f1_promedio": sum(r["f1"] for r in resultados) / n,
    }