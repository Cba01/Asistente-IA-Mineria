"""Pruebas de la mitigación del riesgo CRÍTICO de la matriz (agente que autoriza intervenciones)
y del aviso de cursos por vencer. No llaman a la API."""
from datetime import date, timedelta

from src import agente


def test_respuesta_que_autoriza_recibe_la_aclaracion():
    texto, corregido = agente.revisar_autorizacion("La CT-01 está operativa. Puedes intervenirla hoy.")
    assert corregido and texto.endswith(agente.ACLARACION_AUTORIZACION)


def test_varias_formas_de_autorizar():
    for frase in ["Estás autorizado para subir.", "El trabajador puede trabajar en altura.",
                  "Tienes autorización para ingresar."]:
        assert agente.revisar_autorizacion(frase)[1], frase


def test_respuesta_informativa_no_se_modifica_y_no_se_duplica():
    informativa = "La CT-01 está operativa y sin bloqueo. La autorización la da el supervisor."
    assert agente.revisar_autorizacion(informativa) == (informativa, False)
    ya_corregida, _ = agente.revisar_autorizacion("Puedes intervenirla.")
    assert agente.revisar_autorizacion(ya_corregida) == (ya_corregida, False)


def test_normalizar_resultado_aplica_la_revision():
    resultado = agente.normalizar_resultado({"output": [{"type": "text", "text": "Puedes intervenirlo."}]})
    assert resultado["aclaracion_agregada"] is True
    assert agente.ACLARACION_AUTORIZACION in resultado["output"]


def test_aviso_de_curso_por_vencer(monkeypatch):
    hoy = date.today()
    monkeypatch.setitem(agente.TRABAJADORES, "T-9999", {
        "trabajo en altura": str(hoy + timedelta(days=8)),
        "bloqueo de energías": str(hoy + timedelta(days=200)),
    })
    texto = agente.consultar_certificaciones_trabajador.invoke({"codigo_trabajador": "T-9999"})
    assert "ATENCIÓN: trabajo en altura vence en 8 días" in texto
    assert "bloqueo de energías vence en" not in texto


def test_sin_aviso_si_nada_vence_pronto(monkeypatch):
    monkeypatch.setitem(agente.TRABAJADORES, "T-8888", {"trabajo en altura": str(date.today() + timedelta(days=90))})
    assert "ATENCIÓN" not in agente.consultar_certificaciones_trabajador.invoke({"codigo_trabajador": "T-8888"})


# ---------- Trazas sin datos personales (criterio no compensable 3 del Gate 2) ----------

def test_redactar_pii_enmascara_codigos_correos_rut_y_telefonos():
    texto = ("¿El trabajador T-2045 puede subir? Escribir a ana.perez@example.com, "
             "RUT 12.345.678-5, fono +56 9 8765 4321. Equipo CT-01.")
    limpio = agente.redactar_pii(texto)
    for sensible in ["T-2045", "ana.perez@example.com", "12.345.678-5", "8765 4321"]:
        assert sensible not in limpio
    assert "CT-01" in limpio  # los códigos de equipo no son datos personales


def test_redactar_pii_no_confunde_numeros_con_telefonos():
    for texto in ['"costo_usd": 0.00022229999999999998', '"ts": "2026-11-20T03:43:32.480742"',
                  '"input_tokens": 509']:
        assert agente.redactar_pii(texto) == texto
    assert agente.redactar_pii("llamar al 987654321") == "llamar al [telefono]"


def test_registrar_traza_no_escribe_datos_personales(tmp_path):
    from langchain_core.agents import AgentAction
    archivo = tmp_path / "trazas.jsonl"
    accion = AgentAction(tool="consultar_certificaciones_trabajador",
                         tool_input={"codigo_trabajador": "T-2045"}, log="")
    resultado = {"intermediate_steps": [(accion, "Certificaciones de T-2045: altura vigente.")],
                 "output": "T-2045 tiene el curso vigente."}
    agente.registrar_traza("s1", "¿T-2045 puede subir? mi correo es ana@example.com", resultado, archivo)
    texto = archivo.read_text(encoding="utf-8")
    assert "T-2045" not in texto and "ana@example.com" not in texto
    assert "consultar_certificaciones_trabajador" in texto


def test_revisiones_automaticas_siguen_funcionando_con_trazas_enmascaradas(tmp_path):
    from langchain_core.agents import AgentAction
    archivo = tmp_path / "trazas.jsonl"
    accion = AgentAction(tool="solicitar_bloqueo_equipo", tool_input={"codigo_equipo": "CT-01"}, log="")
    resultado = {"intermediate_steps": [(accion, "Solicitud de bloqueo de CT-01 aprobada por el supervisor")],
                 "output": "ok"}
    agente.registrar_traza("s1", "bloquear CT-01", resultado, archivo)
    assert agente.marcar_alto_riesgo_sin_decision(archivo) == []


def test_redactar_archivo_existente(tmp_path):
    import json
    from src.redactar_trazas import redactar_archivo
    archivo = tmp_path / "trazas.jsonl"
    archivo.write_text(json.dumps({"entrada": "¿T-2045 puede subir?"}, ensure_ascii=False) + "\n"
                       + json.dumps({"entrada": "¿CT-01 operativa?"}, ensure_ascii=False) + "\n",
                       encoding="utf-8")
    assert redactar_archivo(archivo) == 1
    assert "T-2045" not in archivo.read_text(encoding="utf-8")
