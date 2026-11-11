"""Pruebas del pipeline de texto y las métricas. No necesitan mocks: nada toca la red."""
import pytest

from src.pipeline_texto import (
    calcular_metricas,
    calcular_precision_cobertura_f1,
    coincidencia_simple,
    contar_coincidencias,
    procesar_texto,
    resumir_metricas,
)


def test_procesar_texto_normaliza_mayusculas_y_puntuacion():
    assert procesar_texto("El Cielo, es AZUL!") == ["el", "cielo", "es", "azul"]


def test_procesar_texto_solo_puntuacion_devuelve_lista_vacia():
    assert procesar_texto("¡¡¡...!!!") == []


def test_procesar_texto_conserva_tildes_ene_y_numeros():
    assert procesar_texto("¿Cuántos metros? Más de 1,8 en la pañolera.") == \
        ["cuántos", "metros", "más", "de", "18", "en", "la", "pañolera"]


def test_procesar_texto_rechaza_lo_que_no_es_texto():
    with pytest.raises(TypeError):
        procesar_texto(None)


def test_pipeline_corrige_diferencias_de_formato():
    # Mismo contenido, distinto formato: sin limpiar da 50 %, limpiando da 100 %
    assert coincidencia_simple("El cielo es azul.".split(), "el cielo es azul".split()) == 0.5
    assert coincidencia_simple(procesar_texto("El cielo es azul."), procesar_texto("el cielo es azul")) == 1.0


def test_contar_coincidencias_respeta_repeticiones():
    assert contar_coincidencias(["el", "gato"], ["el", "gato", "el", "gato"]) == 2


def test_metricas_ejemplo_calculado_a_mano():
    # Ejemplo de la lección: 5 coincidencias, 9 tokens de respuesta, 6 de referencia
    m = calcular_metricas("El gato duerme en el sofá.", "El gato duerme en el sillón todo el día.")
    assert m["precision"] == pytest.approx(5 / 9)
    assert m["cobertura"] == pytest.approx(5 / 6)
    assert m["f1"] == pytest.approx(2 / 3)


def test_metricas_con_texto_vacio_devuelven_cero():
    assert calcular_precision_cobertura_f1([], ["algo"]) == {"precision": 0.0, "cobertura": 0.0, "f1": 0.0}


def test_metricas_no_detectan_orden_invertido():
    # Límite conocido: dicen lo contrario, pero usan las mismas palabras
    m = calcular_metricas("El perro persiguió al gato.", "El gato persiguió al perro.")
    assert m["f1"] == 1.0


def test_resumir_metricas_promedia():
    resultados = [{"precision": 1.0, "cobertura": 0.5, "f1": 0.6},
                  {"precision": 0.5, "cobertura": 0.5, "f1": 0.4}]
    resumen = resumir_metricas(resultados)
    assert resumen["precision_promedio"] == pytest.approx(0.75)
    assert resumen["f1_promedio"] == pytest.approx(0.5)


def test_resumir_metricas_lista_vacia():
    assert resumir_metricas([])["f1_promedio"] == 0.0