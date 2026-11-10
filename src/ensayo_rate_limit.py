"""Ensayo: provoca un rate limit real para comprobar el backoff y el registro de costo.
Uso desde la raíz del repo:  python -m src.ensayo_rate_limit"""
from src import cliente

PETICIONES = 8

for i in range(PETICIONES):
    try:
        respuesta = cliente.consultar_modelo(f"Di solo el número {i}.")
        print(f"Respuesta {i}: {respuesta.strip()[:40]}")
    except RuntimeError as error:
        print(f"Respuesta {i} falló definitivamente: {error}")

print(f"\nCosto total del ensayo: ${cliente.costo_total_sesion:.6f}")