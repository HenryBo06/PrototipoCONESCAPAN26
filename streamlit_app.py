"""Presentación pública de los resultados guardados del Paper 73.

No carga modelos ni recalcula métricas. Todas las cifras provienen de outputs/.
"""

from __future__ import annotations

import base64
import csv
import html
import io
import math
import os
from pathlib import Path
from urllib.parse import urlsplit

import qrcode
import streamlit as st


ROOT = Path(__file__).resolve().parent
OUTPUTS = ROOT / "outputs"
SUMMARY = OUTPUTS / "extended/tables/extended_summary_metrics.csv"
RUNS = OUTPUTS / "extended/tables/extended_run_metrics.csv"
SELECTED = OUTPUTS / "extended/tables/extended_dataset_manifest.csv"
INVENTORY = OUTPUTS / "dataset_source_manifest.csv"
ARTIFACT_HASHES = OUTPUTS / "demo_sha256.csv"
SOURCE_HASHES = OUTPUTS / "demo_source_sha256.csv"

PLUM = "#41173d"
PURPLE = "#870d93"
BLUE = "#408df5"
GOLD = "#ecc014"

# Figuras 2 y 3 del manuscrito presentado. El orden también sigue al paper.
F1_SPECS = [
    ("TraceRCA-main rca_all_dataset explicit-label CSV", "RandomForest", "TraceRCA-main · RF", PURPLE),
    ("TraceRCA-main rca_all_dataset explicit-label CSV", "XGBoost", "TraceRCA-main · XGB", PURPLE),
    ("TraceRCA-main rca_all_dataset explicit-label CSV", "Autoencoder", "TraceRCA-main · AE", PURPLE),
    ("TraceRCA all dataset recursive service-fault CSV windows", "XGBoost", "TraceRCA-all · XGB", BLUE),
    ("RCAEval recursive service-fault CSV windows", "XGBoost", "RCAEval · XGB", BLUE),
    ("TrainTicket graph-cache derived multimodal tensors", "XGBoost", "TrainTicket* · XGB", PLUM),
    ("Sock Shop scenario-aware metrics evaluation", "XGBoost", "Sock Shop · XGB", GOLD),
]
ERROR_SPECS = [
    ("TraceRCA-main rca_all_dataset explicit-label CSV", "XGBoost", "TR-XGB"),
    ("TraceRCA-main rca_all_dataset explicit-label CSV", "RandomForest", "TR-RF"),
    ("TraceRCA-main rca_all_dataset explicit-label CSV", "Autoencoder", "TR-AE"),
    ("Sock Shop scenario-aware metrics evaluation", "XGBoost", "SS-XGB"),
    ("Sock Shop scenario-aware metrics evaluation", "RandomForest", "SS-RF"),
    ("Sock Shop scenario-aware metrics evaluation", "Autoencoder", "SS-AE"),
]


@st.cache_data(show_spinner=False)
def csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def first_rows(path: Path, limit: int = 60) -> list[dict[str, str]]:
    """Stream only the preview; the broad source inventory is 61 MB."""
    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        return [row for _, row in zip(range(limit), reader)]


def result_map() -> dict[tuple[str, str], dict[str, str]]:
    return {(row["experimental_view"], row["model"]): row for row in csv_rows(SUMMARY)}


def chart_f1(results: dict[tuple[str, str], dict[str, str]]) -> str:
    rows = []
    for view, model, label, color in F1_SPECS:
        score = float(results[view, model]["f1_mean"])
        if not 0 <= score <= 1:
            raise ValueError(f"F1 fuera de rango: {view} {model}")
        rows.append(
            f'<div class="f1-row" title="{html.escape(view)} · {html.escape(model)}" '
            f'aria-label="{html.escape(label)}: F1 {score:.4f}">'
            f'<span class="row-label">{html.escape(label)}</span>'
            f'<span class="bar-track"><span class="bar-fill" style="width:{score * 100:.3f}%;background:{color}"></span></span>'
            f'<strong>{score:.4f}</strong></div>'
        )
    return '<section class="plot"><div class="plot-heading"><h2>F1 por vista y modelo</h2><small>Figura 2 del paper</small></div>' + "".join(rows) + (
        '<div class="f1-axis"><span>0</span><span>0.25</span><span>0.50</span><span>0.75</span><span>1.00</span></div>'
        '<div class="legend"><span><i style="background:#870d93"></i>CSV con etiqueta</span>'
        '<span><i style="background:#408df5"></i>Ventanas recursivas</span>'
        '<span><i style="background:#41173d"></i>Cache derivado</span>'
        '<span><i style="background:#ecc014"></i>Sock Shop</span></div></section>'
    )


def chart_errors(results: dict[tuple[str, str], dict[str, str]]) -> str:
    pairs = []
    max_log = math.log10(1 + 14649.2)
    for view, model, label in ERROR_SPECS:
        row = results[view, model]
        lines = []
        for kind, field, color in (("FP", "false_positives_mean", GOLD), ("FN", "false_negatives_mean", BLUE)):
            count = float(row[field])
            if count < 0:
                raise ValueError(f"Conteo negativo: {view} {model} {kind}")
            width = min(100, math.log10(1 + count) / max_log * 100)
            lines.append(
                f'<div class="error-line" aria-label="{html.escape(label)} {kind}: {count:,.1f}">'
                f'<em>{kind}</em><span class="bar-track"><span class="bar-fill" style="width:{width:.3f}%;background:{color}"></span></span>'
                f'<strong>{count:,.1f}</strong></div>'
            )
        pairs.append(f'<div class="error-row"><span>{html.escape(label)}</span><div>{"".join(lines)}</div></div>')
    return '<section class="plot"><div class="plot-heading"><h2>Falsos positivos y negativos</h2><small>Figura 3 del paper</small></div>' + "".join(pairs) + (
        '<p class="plot-note">TR = TraceRCA-main · SS = Sock Shop. Longitud de barra: log10(1 + conteo). Cifras: medias reales de 10 semillas.</p></section>'
    )


@st.cache_data(show_spinner=False)
def qr_png(url: str) -> str:
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=7, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    image = qr.make_image(fill_color=PLUM, back_color="white")
    out = io.BytesIO()
    image.save(out, format="PNG")
    return base64.b64encode(out.getvalue()).decode("ascii")


def current_url() -> str | None:
    # ponytail: orden explícito ?public= > secrets > env > url actual; localhost jamás es público.
    try:
        query = st.query_params.get("public")
    except Exception:
        query = None
    if query:
        return query
    try:
        secret = st.secrets.get("PUBLIC_URL")
    except Exception:
        secret = None
    if secret:
        return str(secret).strip()
    env = os.environ.get("PUBLIC_URL")
    if env and env.strip():
        return env.strip()
    try:
        url = st.context.url
    except Exception:
        return None
    parsed = urlsplit(url or "")
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None
    if parsed.hostname in ("localhost", "127.0.0.1"):
        return None
    return url


def qr_button(url: str | None) -> None:
    if not url:
        with st.expander("Compartir / QR (falta URL pública)", expanded=False):
            st.warning("Esta copia corre en local (localhost): el QR aún no tiene un enlace público que los teléfonos puedan abrir.")
            st.caption("Despliega la app en Streamlit Community Cloud y pega aquí la URL pública para generar el QR. También puedes abrir la app con ?public=TU_URL.")
            pasted = st.text_input("URL pública de la app", placeholder="https://....streamlit.app")
            pasted = (pasted or "").strip()
            if pasted:
                safe_pasted = html.escape(pasted, quote=True)
                st.html(
                    f'<div class="qr-card" style="position:static;width:245px;margin-top:8px">'
                    f'<strong>Escanea para abrir el dashboard</strong>'
                    f'<img src="data:image/png;base64,{qr_png(pasted)}" alt="Código QR para abrir esta página">'
                    f'<a href="{safe_pasted}" target="_blank" rel="noopener noreferrer">{safe_pasted}</a>'
                    f'</div>'
                )
                st.download_button("Descargar QR (PNG)", base64.b64decode(qr_png(pasted)), "qr-dashboard.png", "image/png")
        return
    safe_url = html.escape(url, quote=True)
    st.html(
        f'<details class="qr-float"><summary aria-label="Mostrar QR del enlace público">'
        f'<span aria-hidden="true">▦</span> Compartir</summary>'
        f'<div class="qr-card"><strong>Escanea para abrir el dashboard</strong>'
        f'<img src="data:image/png;base64,{qr_png(url)}" alt="Código QR para abrir esta página">'
        f'<a href="{safe_url}" target="_blank" rel="noopener noreferrer">{safe_url}</a>'
        f'</div></details>'
        '<script>'
        'if(window.__paper73QrScroll)document.removeEventListener("scroll",window.__paper73QrScroll,true);'
        'const qr=document.querySelector(".qr-float");let previous=0;'
        'window.__paper73QrScroll=function(event){'
        'const node=event.target===document?document.scrollingElement:event.target;'
        'const current=Number(node?.scrollTop??window.scrollY);'
        'if(!Number.isFinite(current)||Math.abs(current-previous)<5)return;'
        'if(!qr.open){if(current>previous&&current>120)qr.classList.add("scroll-hidden");'
        'else if(current<previous)qr.classList.remove("scroll-hidden")}'
        'previous=current};'
        'document.addEventListener("scroll",window.__paper73QrScroll,true);'
        'qr.addEventListener("toggle",()=>{if(qr.open)qr.classList.remove("scroll-hidden")});'
        '</script>',
        unsafe_allow_javascript=True,
    )
    st.download_button("Descargar QR (PNG)", base64.b64decode(qr_png(url)), "qr-dashboard.png", "image/png")


def safe_preview(path: Path) -> list[dict[str, str]]:
    # ponytail: una vista de 40 filas basta para la demo; la descarga conserva el CSV íntegro.
    preview = first_rows(path, 40)
    if path == SELECTED or path == INVENTORY:
        for row in preview:
            row.pop("source_file", None)
    return preview


def evidence() -> None:
    with st.expander("Explorar datos, CSV y SHA-256", expanded=False):
        csv_tab, sources_tab, hashes_tab = st.tabs(["CSV finales", "Fuentes y graph-cache", "Huellas SHA-256"])
        with csv_tab:
            files = sorted(OUTPUTS.rglob("*.csv"))
            if not files:
                st.warning("No hay CSV guardados en esta copia.")
            else:
                selected = st.selectbox(
                    "Archivo", files, index=files.index(SUMMARY) if SUMMARY in files else 0,
                    format_func=lambda path: path.relative_to(ROOT).as_posix(),
                )
                st.dataframe(safe_preview(selected), hide_index=True, width="stretch", height=250)
                st.download_button("Descargar CSV completo", selected.read_bytes(), selected.name, "text/csv")
                st.caption("Vista previa de 40 filas. Los CSV corresponden a resultados ya guardados; abrirlos no ejecuta el procesamiento.")
        with sources_tab:
            st.caption("Cinco vistas modeladas. Los archivos fuente originales están registrados en los manifiestos, no alojados en esta demo. TrainTicket proviene de tensores derivados del graph-cache; el cache original tampoco se aloja aquí. Sock Shop incluye métricas y metadatos de inyección.")
            if SELECTED.exists():
                with SELECTED.open(encoding="utf-8-sig") as file:
                    selected_count = sum(1 for _ in file) - 1
                st.metric("Fuentes seleccionadas", f"{selected_count:,}")
                st.dataframe(first_rows(SELECTED, 40), hide_index=True, width="stretch", height=240)
            if INVENTORY.exists():
                if st.checkbox("Mostrar muestra del inventario amplio (61 MB)"):
                    st.dataframe(first_rows(INVENTORY, 40), hide_index=True, width="stretch", height=240)
                    st.caption("Muestra de 40 filas. El inventario completo está guardado como CSV en esta copia.")
        with hashes_tab:
            st.caption("Huellas calculadas para esta demostración después del procesamiento. Una fila marcada como no disponible no tiene SHA-256 verificable aquí.")
            kind = st.radio("Catálogo", ["Artefactos finales", "Fuentes seleccionadas"], horizontal=True)
            path = ARTIFACT_HASHES if kind == "Artefactos finales" else SOURCE_HASHES
            if path.exists():
                query = st.text_input("Filtrar ruta o estado").casefold().strip()
                matches = []
                with path.open(encoding="utf-8-sig", newline="") as file:
                    for row in csv.DictReader(file):
                        row["alojamiento"] = (
                            "Disponible" if kind == "Artefactos finales" and (ROOT / row["relative_path"]).is_file()
                            else "Registrado, no alojado"
                        )
                        if not query or any(query in value.casefold() for value in row.values()):
                            matches.append(row)
                            if len(matches) >= 100:
                                break
                st.dataframe(matches, hide_index=True, width="stretch", height=280)
                st.caption("Hasta 100 coincidencias en pantalla. El catálogo completo se descarga abajo.")
                st.download_button("Descargar catálogo SHA-256", path.read_bytes(), path.name, "text/csv")
            else:
                st.warning("El catálogo de huellas no está incluido en esta copia.")


st.set_page_config(page_title="Resultados · Paper 73", page_icon="📊", layout="wide")
st.html(
    """
<style>
:root{--plum:#41173d;--purple:#870d93;--blue:#408df5;--gold:#ecc014;--muted:#6a596b;--line:#e9e1ea}
.stApp{background:white;color:var(--plum)}
.block-container{max-width:1480px;padding-top:1rem;padding-bottom:2rem}
h1,h2{font-family:'Arial Narrow','Aptos Narrow',Arial,sans-serif!important;text-transform:uppercase;letter-spacing:.01em}
.palette{height:9px;display:grid;grid-template-columns:repeat(4,1fr);margin:-1rem -1rem 20px}
.palette i:nth-child(1){background:var(--plum)}.palette i:nth-child(2){background:var(--purple)}
.palette i:nth-child(3){background:var(--blue)}.palette i:nth-child(4){background:var(--gold)}
.hero{display:flex;justify-content:space-between;align-items:center;gap:20px}
.eyebrow{font-size:11px;color:var(--purple);font-weight:800;letter-spacing:.12em;text-transform:uppercase}
.hero h1{font-size:clamp(29px,3vw,43px);line-height:1.04;margin:5px 0;color:var(--plum);font-weight:900}
.hero p{margin:0;color:var(--muted);font-size:14px}
.paper{border-left:4px solid var(--gold);padding:7px 0 7px 13px;text-align:right;white-space:nowrap}
.paper strong{display:block;color:var(--purple);font-size:13px}.paper span{font-size:12px;color:var(--muted)}
.facts{display:grid;grid-template-columns:repeat(4,1fr);border-block:1px solid var(--line);margin:18px 0 8px}
.facts>div{padding:10px 16px;border-right:1px solid var(--line)}.facts>div:first-child{padding-left:0}.facts>div:last-child{border:0}
.facts strong{display:block;color:var(--purple);font-size:23px;line-height:1.05}.facts span{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.06em}
.plot{border:1px solid var(--line);border-radius:10px;padding:16px 18px 11px;min-height:345px}
.plot-heading{display:flex;justify-content:space-between;align-items:baseline;gap:10px;margin-bottom:13px}
.plot-heading h2{font-size:20px;color:var(--purple);margin:0;font-weight:900}.plot-heading small{color:var(--muted);white-space:nowrap;font-size:11px}
.f1-row{display:grid;grid-template-columns:178px minmax(0,1fr) 49px;gap:9px;align-items:center;min-height:34px;font:11px Arial,sans-serif}
.f1-row .row-label{font-weight:700;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.f1-row strong,.error-line strong{font-family:Consolas,monospace;text-align:right}
.bar-track{display:block;background:#f0eaf0;height:12px;border-radius:3px;overflow:hidden}.bar-fill{display:block;height:100%;min-width:2px;border-radius:3px}
.f1-axis{display:flex;justify-content:space-between;margin:5px 49px 0 187px;color:var(--muted);font:10px Consolas,monospace}
.legend{border-top:1px solid var(--line);margin-top:11px;padding-top:9px;display:flex;gap:11px;flex-wrap:wrap;color:var(--muted);font-size:10px}
.legend span{display:inline-flex;align-items:center;gap:5px}.legend i{width:9px;height:9px;border-radius:2px}
.error-row{display:grid;grid-template-columns:69px minmax(0,1fr);gap:8px;align-items:center;min-height:44px;border-bottom:1px solid #f3edf3;font:11px Arial,sans-serif}
.error-row:last-of-type{border:0}.error-row>span{font-weight:800}.error-line{display:grid;grid-template-columns:18px minmax(0,1fr) 63px;gap:6px;align-items:center;min-height:16px}
.error-line em{font-size:10px;font-style:normal;font-weight:700;color:var(--muted)}.error-line .bar-track{height:8px;background:#f4f1f5}.error-line strong{font-size:10px}
.plot-note{color:var(--muted);font-size:10px;line-height:1.35;margin:9px 0 0}
.explain{background:#faf8fb;border-left:4px solid var(--purple);border-radius:8px;padding:11px 15px;margin-top:14px;font-size:11px}
.explain p{margin:0}.explain p+p{margin-top:3px;color:var(--muted)}
.qr-float{position:fixed;right:24px;bottom:22px;z-index:999999;font:13px Arial,sans-serif;color:var(--plum);transition:opacity .2s ease,transform .2s ease}
.qr-float.scroll-hidden{opacity:0;transform:translateY(14px);pointer-events:none}
.qr-float summary{list-style:none;cursor:pointer;display:block;background:var(--purple);color:#fff;padding:12px 17px;border-radius:999px;box-shadow:0 8px 25px #41173d55;font-weight:800}
.qr-float summary::-webkit-details-marker{display:none}.qr-float summary:focus-visible{outline:3px solid var(--blue);outline-offset:3px}
.qr-float[open] summary{animation:none;background:var(--plum)}
.qr-card{position:absolute;right:0;bottom:54px;width:245px;max-width:calc(100vw - 36px);background:#fff;border:1px solid var(--line);box-shadow:0 12px 40px #41173d44;border-radius:10px;padding:14px;text-align:center}
.qr-card strong{display:block;font-size:12px;margin-bottom:7px}.qr-card img{display:block;width:170px;height:170px;margin:auto}.qr-card a{display:block;overflow-wrap:anywhere;color:var(--purple);font-size:10px;margin-top:7px}
@media(max-width:900px){.hero .paper{display:none}.facts{grid-template-columns:repeat(2,1fr)}.facts>div:nth-child(2){border-right:0}.facts>div:nth-child(-n+2){border-bottom:1px solid var(--line)}.plot{min-height:unset}}
@media(max-width:600px){.f1-row{grid-template-columns:126px minmax(0,1fr) 47px;gap:5px}.f1-axis{margin-left:131px;margin-right:47px}.plot{padding:14px 12px}.qr-float{right:13px;bottom:13px}}
@media(prefers-reduced-motion:reduce){.qr-float{transition:none}}
</style>
"""
)

if not SUMMARY.exists():
    st.error("Falta el CSV oficial de métricas guardadas: outputs/extended/tables/extended_summary_metrics.csv")
    st.stop()

results = result_map()
expected = {(view, model) for view, model, *_ in F1_SPECS} | {(view, model) for view, model, _ in ERROR_SPECS}
missing = expected - results.keys()
if missing:
    st.error(f"Faltan {len(missing)} resultados requeridos para las figuras del paper.")
    st.stop()

run_rows = csv_rows(RUNS) if RUNS.exists() else []
seeds = len({row["seed"] for row in run_rows}) if run_rows else 10
views = len({view for view, _ in results})
st.html('<div class="palette" aria-hidden="true"><i></i><i></i><i></i><i></i></div>')
st.html(
    '<header class="hero"><div><div class="eyebrow">Prototipo experimental · Paper 73</div>'
    '<h1>Detección de anomalías en microservicios</h1>'
    '<p>Resultados guardados de la evaluación offline</p></div>'
    '<div class="paper"><strong>CONESCAPAN 2026</strong><span>IEEE · Costa Rica</span></div></header>'
)
st.html(
    f'<div class="facts"><div><strong>{seeds}</strong><span>semillas</span></div>'
    f'<div><strong>{views}</strong><span>vistas modeladas</span></div>'
    f'<div><strong>{len(results)}</strong><span>resúmenes de modelo</span></div>'
    f'<div><strong>{len(run_rows)}</strong><span>corridas</span></div></div>'
)
left, right = st.columns([1.13, 1], gap="medium")
with left:
    st.html(chart_f1(results))
with right:
    st.html(chart_errors(results))
st.html(
    '<div class="explain"><p><strong>Qué muestran:</strong> F1 equilibra precisión y recall; FP son falsas alertas y FN son anomalías omitidas.</p>'
    '<p>TrainTicket usa un graph-cache derivado. Sock Shop usa métricas y metadatos de inyección. Estos resultados no son monitoreo en vivo.</p></div>'
)
evidence()
qr_button(current_url())
