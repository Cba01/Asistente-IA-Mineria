"""Pruebas de las herramientas del agente. No llaman a la API."""
from datetime import date

from src.agente import (
    HERRAMIENTAS,
    consultar_certificaciones_trabajador,
    consultar_estado_equipo,
    estado_vigencia,
    herramientas_usadas,
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