# Registro del ensayo de rate limit

- **Fecha:** 2026-11-10
- **Script:** `python -m src.ensayo_rate_limit` (8 peticiones seguidas, sin pausa entre ellas)
- **Modelo:** gemini-3.6-flash (plan gratuito: 5 peticiones/minuto, 20 peticiones/día)
- **Primer error temporal:** en la petición 6 (índice 5), justo después de 5 peticiones seguidas, coherente con el límite de 5/minuto. Muy probablemente un 429. El mensaje de reintento de esta versión no mostraba el código; ya se corrigió para que lo muestre.
- **Esperas observadas:** 2,1 s en las peticiones 6 y 7 (backoff con jitter). Ambas se recuperaron en el segundo intento, así que no hizo falta llegar a la espera de 4 s.
- **Resultado:** 8 de 8 peticiones terminaron con éxito. Ninguna agotó los reintentos ni produjo un Traceback.
- **Costo:** se registró solo en las 8 operaciones exitosas (entre 85 y 154 tokens cada una, la mayoría de pensamiento). Costo total del ensayo: USD 0,003728.