"""Pruebas de las herramientas del agente. No llaman a la API."""
from datetime import date

import pytest
from pydantic import ValidationError

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