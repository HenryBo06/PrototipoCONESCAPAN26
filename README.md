# Prototipo CONESCAPAN 2026 — dashboard de resultados

Vista de presentación del Paper 73. Muestra las dos gráficas de resultados del manuscrito (F1 y falsos positivos/negativos) a partir de los CSV guardados de la evaluación offline con 10 semillas. La paleta sigue la plantilla CONESCAPAN/IEEE Costa Rica.

## Ver en línea (QR para el teléfono)

La página pública es `index.html` vía GitHub Pages (sin cuentas ni login):

1. Haz el repo público: `Settings` → `Danger Zone` → `Change visibility` → `Make public`.
2. Activa Pages: `Settings` → `Pages` → `Deploy from a branch` → rama `main`, carpeta `/ (root)` → `Save`.
3. Abre https://henrybo06.github.io/PrototipoCONESCAPAN26/ y verifica que carga. Ese es el link del QR (`qr.png`).

## Ver localmente (Streamlit)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run streamlit_app.py
```

En Streamlit Community Cloud, seleccione este repositorio, la rama `main` y el archivo `streamlit_app.py`. La app puede hacerse pública en **Settings → Sharing** aunque el repositorio GitHub permanezca privado. El QR de la página usa su URL actual.

## Datos de la demostración

`outputs/extended/tables/extended_summary_metrics.csv` es la fuente de las barras; `extended_run_metrics.csv` contiene las 150 corridas. Los manifiestos, CSV finales pequeños y catálogos SHA-256 están disponibles como evidencia en la app. Las huellas SHA-256 se calcularon para esta demostración, después del experimento.

Los archivos crudos o procesados de más de 100 MB no se alojan en este repositorio; el catálogo indica sus nombres y huellas, sin atribuirles descarga. El graph-cache original de TrainTicket tampoco está disponible en esta copia. La aplicación muestra resultados guardados y no ejecuta entrenamiento ni procesamiento de datos.
