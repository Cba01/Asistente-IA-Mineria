"""Pruebas de las herramientas del agente. No llaman a la API."""
from datetime import date

import pytest
from pydantic import ValidationError
import json
from types import SimpleNamespace
from unittest.mock import patch

import src.agente as agente_modulo
from src.agente import (
    HERRAMIENTAS,
    buscar_procedimiento,
    cerrar_sesion,
    consultar_certificaciones_trabajador,
    consultar_estado_equipo,
    estado_vigencia,
    herramientas_usadas,
    normalizar_resultado,
    obtener_historial,
    texto_de_salida,
    esperar_aprobacion,
    marcar_alto_riesgo_sin_decision,
    marcar_repeticiones_sospechosas,
    registrar_traza,
    solicitar_bloqueo_equipo,
)

def test_estado_vigencia_vigente_y_vencido():
    hoy = date(2026, 11, 18)
    assert estado_vigencia("2026-12-01", hoy) == "vigente"
    assert estado_vigencia("2026-11-18", hoy) == "vigente"  # vence hoy: todavía vale
    assert estado_vigencia("2026-11-01", hoy) == "vencido"


def test_consultar_estado_equipo_bloqueado():
    resultado = consultar_estado_equipo.invoke({"codigo_equipo": "CH-01"})
    assert "BLOQUEADO" in resultado


def test_consultar_estado_equipo_acepta_minusculas_y_espacios():
    resultado = consultar_estado_equipo.invoke({"codigo_equipo": " ct-01 "})
    assert "CT-01" in resultado


def test_consultar_estado_equipo_inexistente_no_lanza_error():
    resultado = consultar_estado_equipo.invoke({"codigo_equipo": "XX-99"})
    assert "No existe" in resultado


def test_consultar_certificaciones_trabajador_lista_cursos():
    resultado = consultar_certificaciones_trabajador.invoke({"codigo_trabajador": "T-1023"})
    assert "trabajo en altura" in resultado
    assert "bloqueo de energías" in resultado


def test_consultar_certificaciones_trabajador_inexistente():
    resultado = consultar_certificaciones_trabajador.invoke({"codigo_trabajador": "T-0000"})
    assert "No existe" in resultado


def test_todas_las_herramientas_tienen_descripcion_de_cuando_usarlas():
    for herramienta in HERRAMIENTAS:
        assert "Usar cuando" in herramienta.description


def test_herramientas_usadas_sin_pasos_devuelve_lista_vacia():
    assert herramientas_usadas({"output": "ok"}) == []
    

def test_texto_de_salida_une_bloques_de_texto():
    salida = [{"type": "text", "text": "Hola, ", "extras": {"signature": "abc"}},
              {"type": "text", "text": "mundo."}]
    assert texto_de_salida(salida) == "Hola, mundo."


def test_texto_de_salida_deja_igual_un_string():
    assert texto_de_salida("respuesta simple") == "respuesta simple"
    
    
# ---------- Herramienta con args_schema ----------

def test_buscar_procedimiento_sin_pasos_solo_da_codigo_y_nombre():
    resultado = buscar_procedimiento.invoke({"tarea": "cambio de rodillo"})
    assert "PTS-MEC-014" in resultado
    assert "Pasos" not in resultado


def test_buscar_procedimiento_con_pasos():
    resultado = buscar_procedimiento.invoke({"tarea": "cambio de rodillo", "incluir_pasos": True})
    assert "Pasos" in resultado
    assert "energía cero" in resultado


def test_buscar_procedimiento_sin_coincidencia_no_lanza_error():
    resultado = buscar_procedimiento.invoke({"tarea": "pintar oficina"})
    assert "No se encontró" in resultado


def test_buscar_procedimiento_tiene_nombre_explicito():
    assert buscar_procedimiento.name == "buscar_procedimiento_trabajo_seguro"


def test_buscar_procedimiento_rechaza_argumento_invalido():
    # Pydantic valida antes de ejecutar: 'tal vez' no es un booleano
    with pytest.raises(ValidationError):
        buscar_procedimiento.invoke({"tarea": "rodillo", "incluir_pasos": "tal vez"})


# ---------- Memoria ----------

def test_misma_sesion_devuelve_el_mismo_historial():
    cerrar_sesion("prueba_1")
    assert obtener_historial("prueba_1") is obtener_historial("prueba_1")


def test_sesiones_distintas_no_comparten_historial():
    cerrar_sesion("prueba_a")
    cerrar_sesion("prueba_b")
    obtener_historial("prueba_a").add_user_message("Estoy preguntando por la CT-01")
    assert len(obtener_historial("prueba_a").messages) == 1
    assert len(obtener_historial("prueba_b").messages) == 0


def test_cerrar_sesion_borra_el_historial_y_no_falla_si_no_existe():
    obtener_historial("prueba_c").add_user_message("hola")
    cerrar_sesion("prueba_c")
    cerrar_sesion("prueba_c")  # segunda vez: no debe fallar
    assert len(obtener_historial("prueba_c").messages) == 0


def test_normalizar_resultado_deja_output_como_texto():
    resultado = {"output": [{"type": "text", "text": "Respuesta limpia"}], "intermediate_steps": []}
    assert normalizar_resultado(resultado)["output"] == "Respuesta limpia"
    
    
# ---------- Supervisión humana ----------

@pytest.fixture(autouse=True)
def archivos_temporales(tmp_path, monkeypatch):
    """Ninguna prueba escribe en los archivos reales de trazas y aprobaciones."""
    monkeypatch.setattr(agente_modulo, "ARCHIVO_APROBACIONES", tmp_path / "aprobaciones.jsonl")
    monkeypatch.setattr(agente_modulo, "ARCHIVO_TRAZAS", tmp_path / "trazas.jsonl")


def test_esperar_aprobacion_acepta_s():
    with patch("builtins.input", return_value=" S "):
        assert esperar_aprobacion("¿Aprobar?", tiempo_limite_segundos=1) is True


def test_esperar_aprobacion_rechaza_otra_respuesta():
    with patch("builtins.input", return_value="n"):
        assert esperar_aprobacion("¿Aprobar?", tiempo_limite_segundos=1) is False


def test_esperar_aprobacion_rechaza_si_no_hay_consola():
    with patch("builtins.input", side_effect=EOFError):
        assert esperar_aprobacion("¿Aprobar?", tiempo_limite_segundos=1) is False


def test_esperar_aprobacion_rechaza_si_no_responden_a_tiempo():
    import time
    with patch("builtins.input", side_effect=lambda _: time.sleep(2) or "s"):
        assert esperar_aprobacion("¿Aprobar?", tiempo_limite_segundos=0.2) is False


def test_bloqueo_aprobado_se_ejecuta_y_queda_registrado():
    with patch("src.agente.esperar_aprobacion", return_value=True):
        resultado = solicitar_bloqueo_equipo.invoke({"codigo_equipo": "CT-01", "motivo": "polín dañado"})
    assert "aprobada" in resultado
    registro = json.loads(agente_modulo.ARCHIVO_APROBACIONES.read_text(encoding="utf-8"))
    assert registro["aprobado"] is True
    assert registro["argumentos"]["codigo_equipo"] == "CT-01"


def test_bloqueo_rechazado_no_se_ejecuta_y_queda_registrado():
    with patch("src.agente.esperar_aprobacion", return_value=False):
        resultado = solicitar_bloqueo_equipo.invoke({"codigo_equipo": "CT-01", "motivo": "polín dañado"})
    assert "NO aprobada" in resultado
    registro = json.loads(agente_modulo.ARCHIVO_APROBACIONES.read_text(encoding="utf-8"))
    assert registro["aprobado"] is False


def test_bloqueo_de_equipo_inexistente_no_pide_aprobacion():
    with patch("src.agente.esperar_aprobacion") as mock_aprobacion:
        resultado = solicitar_bloqueo_equipo.invoke({"codigo_equipo": "XX-99", "motivo": "prueba"})
    assert "No existe" in resultado
    mock_aprobacion.assert_not_called()


def test_bloqueo_de_equipo_ya_bloqueado_no_pide_aprobacion():
    with patch("src.agente.esperar_aprobacion") as mock_aprobacion:
        resultado = solicitar_bloqueo_equipo.invoke({"codigo_equipo": "CH-01", "motivo": "prueba"})
    assert "ya está bloqueado" in resultado
    mock_aprobacion.assert_not_called()


# ---------- Trazas ----------

def paso_falso(herramienta, argumentos, observacion):
    """Simula un paso de intermediate_steps: (acción con .tool y .tool_input, observación)."""
    return (SimpleNamespace(tool=herramienta, tool_input=argumentos), observacion)


def test_registrar_traza_guarda_acciones_y_respuesta():
    resultado = {"output": "ok", "intermediate_steps": [
        paso_falso("consultar_estado_equipo", {"codigo_equipo": "CT-01"}, "operativa")]}
    registrar_traza("sesion_1", "¿estado CT-01?", resultado)
    linea = json.loads(agente_modulo.ARCHIVO_TRAZAS.read_text(encoding="utf-8"))
    assert linea["acciones"][0]["herramienta"] == "consultar_estado_equipo"
    assert linea["respuesta_final"] == "ok"


def test_registrar_traza_sin_pasos_guarda_lista_vacia():
    registrar_traza("sesion_1", "hola", {"output": "hola"})
    linea = json.loads(agente_modulo.ARCHIVO_TRAZAS.read_text(encoding="utf-8"))
    assert linea["acciones"] == []


def test_marca_herramienta_repetida_seguida():
    resultado = {"output": "ok", "intermediate_steps": [
        paso_falso("consultar_estado_equipo", {"codigo_equipo": "CT-01"}, "a"),
        paso_falso("consultar_estado_equipo", {"codigo_equipo": "CT-01"}, "a")]}
    registrar_traza("sesion_rep", "x", resultado)
    assert any("sesion_rep" in alerta for alerta in marcar_repeticiones_sospechosas())


def test_marca_alto_riesgo_sin_decision_de_aprobacion():
    resultado = {"output": "ok", "intermediate_steps": [
        paso_falso("solicitar_bloqueo_equipo", {"codigo_equipo": "CT-01"}, "bloqueo ejecutado")]}
    registrar_traza("sesion_riesgo", "x", resultado)
    assert any("sesion_riesgo" in alerta for alerta in marcar_alto_riesgo_sin_decision())


def test_no_marca_alto_riesgo_si_hubo_decision():
    resultado = {"output": "ok", "intermediate_steps": [
        paso_falso("solicitar_bloqueo_equipo", {"codigo_equipo": "CT-01"}, "Solicitud NO aprobada")]}
    registrar_traza("sesion_ok", "x", resultado)
    assert marcar_alto_riesgo_sin_decision() == []