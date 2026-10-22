# Asistente IA de Seguridad Minera

Miniaplicación en Python que responde consultas de seguridad para faenas mineras usando la API de Google Gemini.

Para cada consulta, la aplicación:

1. **Clasifica el riesgo** (tipo de riesgo, criticidad y si requiere bloqueo de energías) con una respuesta JSON validada.
2. **Responde la consulta** usando esa clasificación como contexto, con terminología chilena y una advertencia de seguridad al final.

> Proyecto desarrollado en la *Especialización en Desarrollo con IA Generativa* (Accenture · Skillnest). Esta versión corresponde al **Gate 1 – Habilitación técnica**.

> ⚠️ Las respuestas son orientativas. No reemplazan el procedimiento oficial de la faena ni las instrucciones del supervisor.

---

## Requisitos

- **Python 3.10 o superior**
- **Git**
- **Una API key de Google Gemini.** Es gratis y no pide tarjeta: entra a [Google AI Studio](https://aistudio.google.com), inicia sesión y haz clic en **Get API key → Create API key**.

---

## Instalación

### 1. Clonar el repositorio

```bash
git clone https://github.com/Cba01/Asistente-IA-Mineria.git
cd Asistente-IA-Mineria
```

### 2. Crear y activar el entorno virtual

**Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**macOS / Linux / WSL:**
```bash
python3 -m venv venv
source venv/bin/activate
```

Si el entorno quedó activo, al inicio de la línea de la terminal aparece `(venv)`.

### 3. Instalar las dependencias

```bash
pip install -r requirements.txt
```

### 4. Configurar las variables de entorno

Copia el archivo de ejemplo:

```powershell
# Windows (PowerShell)
Copy-Item .env.example .env
```
```bash
# macOS / Linux / WSL
cp .env.example .env
```

Abre el archivo `.env` y pega tu API key:

```dotenv
GEMINI_API_KEY=tu_llave_real
GEMINI_MODEL=gemini-3.6-flash
```

| Variable | Obligatoria | Descripción |
|---|---|---|
| `GEMINI_API_KEY` | Sí | API key de Google Gemini. |
| `GEMINI_MODEL` | No | Modelo a usar. Si se deja vacía, se usa `gemini-3.6-flash`. |

El archivo `.env` está excluido en `.gitignore` y **nunca se sube al repositorio**.

---

## Uso

### Con la consulta como argumento

```bash
python main.py "¿Qué debo hacer antes de intervenir una correa transportadora?"
```

> En macOS / Linux usa `python3` en lugar de `python`.

### Sin argumento (la consulta se pide por teclado)

```bash
python main.py
```

En Windows, si PowerShell elimina las tildes de la consulta al pasarla como argumento, usa esta forma.

### Ejemplo de salida

```text
Consultando a gemini-3.6-flash...

--- Clasificación ---
Tipo de riesgo:   atrapamiento
Criticidad:       alta
Requiere bloqueo: sí

--- Respuesta ---
1. Coordinación y permisos: informa a la sala de control, tramita el permiso de trabajo
   y confecciona el AST con todo el equipo.
2. Aislamiento y bloqueo: ...
...

Recuerda que esta orientación no reemplaza el procedimiento oficial de la faena
ni las instrucciones del supervisor.

(modelo: gemini-3.6-flash · tokens usados en la respuesta: 1422)
```

Cada ejecución hace **2 peticiones** a la API: una para clasificar y otra para responder.

---

## Otros scripts

Se ejecutan desde la raíz del repositorio. Son opcionales y consumen más cuota de la API.

| Script | Qué hace | Peticiones |
|---|---|---|
| `python src/consumir_gemini.py` | Prueba rápida de conexión con la API. | 1 |
| `python prompts/test_consistencia.py` | Ejecuta cada prompt del banco 3 veces y guarda los resultados en `prompts/registro_resultados.json`. | 9 |
| `python src/comparar_modelos.py` | Compara dos modelos en latencia, costo y calidad. Guarda las respuestas en `docs/respuestas_comparacion.md`. | 14 |

---

## Estructura del proyecto

```text
Asistente-IA-Mineria/
├── main.py                       # Script principal de la miniaplicación
├── requirements.txt              # Dependencias con versiones fijas
├── .env.example                  # Plantilla de variables de entorno (sin valores reales)
├── src/
│   ├── consumir_gemini.py        # Cliente de la API: petición, errores, JSON y costo
│   └── comparar_modelos.py       # Comparación de modelos (latencia, costo y calidad)
├── prompts/
│   ├── banco.py                  # Banco de prompts con su esquema JSON
│   ├── test_consistencia.py      # Validación de consistencia del banco
│   └── registro_resultados.json  # Resultados de la validación
├── docs/
│   ├── diagrama_arquitectura.png
│   ├── decision-arquitectura.md  # Elección de modelo justificada con datos
│   ├── respuestas_comparacion.md
│   └── evidencia_*.png           # Capturas de evidencia
└── tests/
```

---

## Arquitectura

![Diagrama de arquitectura](docs/diagrama_arquitectura.png)

El módulo `src/consumir_gemini.py` separa cada responsabilidad en su propia función:

| Función | Responsabilidad |
|---|---|
| `armar_peticion` | Valida la entrada, lee la API key desde el entorno y arma la URL, los headers y el body (con prompt de sistema y esquema JSON opcionales). |
| `enviar_peticion` | Envía la petición con timeout, reintenta ante saturación y traduce los errores HTTP a mensajes claros. |
| `extraer_texto` | Obtiene el texto generado desde la respuesta de Gemini. |
| `parsear_respuesta_json` | Convierte la respuesta en un diccionario y valida que tenga las claves esperadas. |
| `calcular_costo` | Calcula el costo en USD, incluidos los tokens de "pensamiento" del modelo. |

La elección del modelo (`gemini-3.6-flash` frente a `gemini-3.5-flash-lite`) está documentada en [`docs/decision_arquitectura.md`](docs/decision_arquitectura.md).

---

## Manejo de errores

La aplicación nunca termina con un *Traceback*. Ante cualquier falla muestra un mensaje claro:

| Situación | Comportamiento |
|---|---|
| Consulta vacía | `La pregunta no puede estar vacía.` |
| Falta `GEMINI_API_KEY` | `No se encontró GEMINI_API_KEY. Revisa tu archivo .env.` |
| Sin conexión o tiempo de espera agotado | Mensaje de conexión o de timeout. |
| Error 429, 500 o 503 (cuota o servicio saturado) | Reintenta hasta 3 veces con espera creciente (2 s, 4 s). |
| API key inválida u otro error HTTP | Mensaje con el código y el detalle que entrega Google. |
| Respuesta sin el formato esperado | Mensaje indicando qué faltó. |

---

## Problemas comunes

| Problema | Causa probable | Solución |
|---|---|---|
| `Quota exceeded ... limit: 5` | Límite de 5 peticiones por minuto del plan gratuito. | Espera un minuto y vuelve a ejecutar. |
| `Quota exceeded ... limit: 20` | Límite diario de 20 peticiones del plan gratuito para `gemini-3.6-flash`. | Cambia a otro modelo en el `.env`: `GEMINI_MODEL=gemini-3.5-flash-lite`. |
| `(servicio ocupado, error 503 ...)` | Los servidores de Google están saturados. | Normalmente se resuelve solo con los reintentos. Si persiste, espera unos minutos. |
| `error 400 ... API key not valid` | API key mal copiada o incompleta. | Vuelve a copiarla desde Google AI Studio, sin comillas ni espacios. |
| `No se encontró GEMINI_API_KEY` | No existe el `.env`, no está en la raíz o la variable tiene otro nombre. | Revisa el paso 4 de la instalación. |
| `No module named 'requests'` o `'dotenv'` | El entorno virtual no está activo o no se instalaron las dependencias. | Activa el entorno y ejecuta `pip install -r requirements.txt`. |
| PowerShell no permite activar el entorno | Política de ejecución de scripts de Windows. | Ejecuta `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` y vuelve a activarlo. |
| `python` no se reconoce (macOS / Linux) | El comando se llama `python3`. | Usa `python3` y `pip3`. |

---

## Seguridad

- La API key se lee desde una variable de entorno y **nunca está escrita en el código**.
- `.env` está excluido en `.gitignore`. Solo se versiona `.env.example`, sin valores reales.
- La key viaja en el header `x-goog-api-key` y no en la URL, para que no quede expuesta en logs ni en mensajes de error.

---

## Limitaciones conocidas

- Las respuestas provienen del conocimiento general del modelo y **no citan normativa chilena** (por ejemplo, el DS 132). Esto se abordará con RAG sobre documentos propios en el Módulo 2.
- El modelo puede **omitir pasos** de un procedimiento u ofrecer listas de EPP que varían entre ejecuciones 
- El plan gratuito de la API limita la cantidad de peticiones por minuto y por día.

---

## Registro del ensayo de instalación limpia

- **Fecha:** _AAAA-MM-DD_
- **Procedimiento:** se clonó el repositorio en una carpeta nueva, se creó un entorno virtual nuevo, se instalaron las dependencias desde `requirements.txt`, se creó el `.env` desde `.env.example` y se ejecutó `main.py` siguiendo solo este README.
- **Hallazgos:** _(completar: lo que falló o "sin hallazgos")_
- **Correcciones:** _(completar, si hubo)_
- **Resultado:** _(completar)_