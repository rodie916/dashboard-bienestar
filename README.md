# Dashboard de bienestar integral (Streamlit)

Lee las respuestas del Google Form (y las de la encuesta en Streamlit), las pasa por el sistema difuso
jerárquico v10 y muestra el panorama del grupo y el desglose de cada persona. Se actualiza solo: cada vez
que alguien responde, la respuesta aparece en el dashboard en menos de un minuto.

```
Google Form ──► Google Sheet (pestaña 1) ──┐
                                           ├──► dashboard.py ──► motor difuso v10 ──► gráficos
Encuesta Streamlit ──► pestaña "respuestas_streamlit" ──┘
```

## Archivos

| Archivo | Qué hace |
|---|---|
| `dashboard.py` | La app del dashboard (5 pestañas: Panorama, Personas, Detalle por persona, Validación, Modelo) |
| `fuzzy_engine.py` | Motor Mamdani jerárquico (mismo algoritmo que el código de Python, MATLAB y el simulador web) |
| `fis_v10_spec.json` | Variables, funciones de pertenencia y las 71 reglas |
| `datos.py` | Lee las fuentes y convierte las respuestas en las 10 variables (Sí/No → 1/0, “4 o menos” → 4, ítems invertidos, promedio de cursos) |
| `guardar_respuesta.py` | Función para que la encuesta de Streamlit guarde sus respuestas en el mismo Google Sheet |
| `.streamlit/secrets.toml.example` | Plantilla de la configuración (contraseña y conexión) |

## Paso 1. Vincular el Form a un Google Sheet (2 minutos)

En el Google Form: **Respuestas → Vincular con Hojas de cálculo → Crear una hoja de cálculo nueva**.
Desde ese momento, cada respuesta nueva se agrega sola como una fila.

## Paso 2. Dar acceso al dashboard (elige una opción)

**Opción A — recomendada (la hoja sigue privada).**
1. En [console.cloud.google.com](https://console.cloud.google.com) crea un proyecto y activa **Google Sheets API** y **Google Drive API**.
2. **IAM y administración → Cuentas de servicio → Crear cuenta de servicio**. Luego, en la cuenta: **Claves → Agregar clave → JSON**. Se descarga un archivo.
3. Abre el Google Sheet → **Compartir** → pega el `client_email` de ese JSON. Dale **Editor** si la encuesta de Streamlit va a escribir; si no, **Lector**.
4. Copia los datos del JSON en los secretos (paso 4) dentro de `[gcp_service_account]`, junto con el `SHEET_ID`.

**Opción B — rápida (solo lectura, la hoja queda pública con el enlace).**
En el Sheet: **Archivo → Compartir → Publicar en la web → la pestaña de respuestas → CSV → Publicar**.
Copia el enlace en `FORM_CSV_URL`. Úsala solo para la demo: cualquiera con el enlace puede ver las respuestas.

## Paso 3. Que la encuesta de Streamlit también alimente el dashboard (opcional)

En la app de la encuesta, después de calcular las 10 variables:

```python
from guardar_respuesta import guardar_respuesta
guardar_respuesta(x, cursos=["Física", "Estrategia"], R1=r1, R2=r2, R3=r3, carrera=carrera, ciclo=ciclo)
```

La primera vez crea la pestaña `respuestas_streamlit`. El dashboard la lee junto con las del Form y marca
cada persona con su origen (Formulario o Streamlit). Requiere la opción A.

## Paso 4. Publicarlo en Streamlit Cloud

1. Sube esta carpeta a un repositorio de GitHub (sin `secrets.toml` ni Excel de respuestas: ya están en `.gitignore`).
2. En [share.streamlit.io](https://share.streamlit.io): **Create app** → el repositorio → archivo principal `dashboard.py`.
3. **Advanced settings → Secrets**: pega el contenido de `secrets.toml.example` con tus datos.

Recomendación: publícalo como una app **separada** de la encuesta y con `DASHBOARD_PASSWORD`, porque muestra
resultados individuales y alertas internas. Si prefieres una sola app, copia los archivos al repositorio de la
encuesta y mueve `dashboard.py` a `pages/2_Dashboard.py`.

## Probarlo en tu computadora

```bash
pip install -r requirements.txt
# Sin Google Sheets: deja el Excel de respuestas como respuestas.xlsx en esta carpeta, o súbelo en la barra lateral
streamlit run dashboard.py
```

## Cuándo se actualiza

El dashboard vuelve a leer el Sheet como máximo cada 60 segundos mientras alguien lo usa, y al instante con el
botón **Actualizar ahora**. No hace falta volver a publicar nada cuando llegan respuestas nuevas.
