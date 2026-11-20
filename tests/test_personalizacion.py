"""Pruebas de la U2.6: dataset de tuning, medición de formato y método de decisión. Sin API."""
from google.genai import types

from src.dataset_tuning import (CLAVES, EJEMPLOS_RAW, VALORES_TIPO, chequear_balance,
                                construir_ejemplos, validar_dataset)
from src.decision import analisis_sensibilidad, recomendar_estrategia
from src.medir_formato import (contar_oraciones, esta_completa, evaluar_respuestas,
                               revisar_respuesta, tiene_markdown, tiene_otro_alfabeto)

# ---------- dataset ----------

def test_dataset_tiene_al_menos_10_ejemplos_y_es_valido():
    examples = construir_ejemplos()
    assert len(examples) >= 10
    assert validar_dataset(examples) == []


def test_dataset_cubre_todos_los_tipos_de_riesgo_del_esquema():
    assert set(chequear_balance(EJEMPLOS_RAW, "tipo_riesgo")) == VALORES_TIPO


def test_validador_detecta_valores_fuera_del_esquema_y_duplicados():
    ok = construir_ejemplos()[:1]
    rotos = ok + [types.TuningExample(text_input=ok[0].text_input,
                                      output='{"tipo_riesgo": "caida", "requiere_bloqueo": "si", '
                                             '"criticidad": "Alta"}')]
    problemas = validar_dataset(rotos)
    assert any("duplicado" in p for p in problemas)
    assert any("tipo_riesgo" in p for p in problemas)
    assert any("criticidad" in p for p in problemas)
    assert any("requiere_bloqueo" in p for p in problemas)


def test_validador_detecta_json_invalido_y_clave_faltante():
    rotos = [types.TuningExample(text_input="a", output="no es json"),
             types.TuningExample(text_input="b", output='{"tipo_riesgo": "otro"}')]
    problemas = validar_dataset(rotos)
    assert any("JSON" in p for p in problemas)
    assert sum("falta la clave" in p for p in problemas) == len(CLAVES) - 1

# ---------- medición de formato ----------

def test_criterios_de_formato():
    assert esta_completa("Es la Ley 16.744.") and not esta_completa("Lo forman tres. Ambos")
    assert contar_oraciones("Es la Ley N° 16.744. Desde 1,8 metros.") == 2
    assert tiene_markdown("Es **85 dB(A)**.") and not tiene_markdown("Es 85 dB(A).")
    assert tiene_otro_alfabeto("Usa casco 安全.") and not tiene_otro_alfabeto("Señalización y pingüino.")


def test_revisar_respuesta_reporta_todas_las_fallas():
    fallas = revisar_respuesta("Uno. **Dos**. Tres. Cuatro")
    assert set(fallas) == {"cortada", "más de 2 oraciones", "markdown"}


def test_evaluar_respuestas_y_umbral():
    r = evaluar_respuestas(["Correcta.", "Con **negrita**.", "Bien.", "Bien otra vez."])
    assert r["con_fallas"] == 1 and r["proporcion"] == 0.25 and r["supera_umbral"] is True

# ---------- método de decisión ----------

def test_recomendar_reporta_empates():
    respuestas = {"informacion_cambia_seguido": False, "problema_de_formato_o_tono": True,
                  "dataset_grande_y_de_calidad": True, "presupuesto_limitado_o_iterar_rapido": False,
                  "necesita_multiples_variantes": False}
    puntos, ganadoras = recomendar_estrategia(respuestas)
    assert puntos == {"RAG": 0, "Fine-tuning completo": 3, "PEFT": 3}
    assert ganadoras == ["Fine-tuning completo", "PEFT"]


def test_sensibilidad_cambia_una_respuesta_a_la_vez():
    respuestas = {"informacion_cambia_seguido": True, "problema_de_formato_o_tono": True,
                  "dataset_grande_y_de_calidad": False, "presupuesto_limitado_o_iterar_rapido": True,
                  "necesita_multiples_variantes": False}
    filas = analisis_sensibilidad(respuestas)
    assert len(filas) == 5
    fila_info = next(f for f in filas if f[0] == "informacion_cambia_seguido")
    assert fila_info[1] is False and fila_info[2] == ["PEFT"] and fila_info[3] is True
