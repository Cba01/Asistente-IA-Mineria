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
