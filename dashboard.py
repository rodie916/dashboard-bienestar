"""Dashboard de bienestar integral (uso interno).

Lee las respuestas del Google Form (y, si existe, las de la app de Streamlit), las pasa por el
sistema difuso jerárquico v10 y muestra el panorama del grupo y el desglose de cada persona.

Correr:  streamlit run dashboard.py
"""
import math
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import datos
import fuzzy_engine as fe

st.set_page_config(page_title="Dashboard · Bienestar integral", page_icon="📊", layout="wide")

COL = {"bajo": "#B9382A", "medio": "#C98A16", "alto": "#2B7A49"}
COL_BLOQUE = {"A": "#2F6DB5", "C": "#7A4BB0", "Co": "#B5602F", "I": "#3D3BB0"}
NOMBRE_VAR = {"notas": "Notas (0–20)", "asistencia": "Asistencia (%)", "horas": "Horas de estudio (h/sem)",
              "entendimiento": "Entendimiento (1–5)", "interes": "Interés (1–5)", "metodo": "Método (0/1)",
              "participacion": "Participación (1–5)", "amonestaciones": "Amonestaciones",
              "sueno": "Sueño (h/noche)", "emocion": "Estado emocional (1–5)"}
RANGO_VAR = {"notas": (0, 20), "asistencia": (0, 100), "horas": (0, 10), "entendimiento": (1, 5), "interes": (1, 5),
             "metodo": (0, 1), "participacion": (1, 5), "amonestaciones": (0, 5), "sueno": (3, 13), "emocion": (1, 5)}
ETIQ_NIVEL = {"limitrofe": "limítrofe"}
ETIQ_VAR = {"metodo": {"bajo": "no", "alto": "sí"},
            "amonestaciones": {"bajo": "2 o más", "medio": "una", "alto": "ninguna"}}


def etiqueta(var, nv):
    return ETIQ_VAR.get(var, {}).get(nv, ETIQ_NIVEL.get(nv, nv))
SENALES = [
    ("Duerme menos de 6 h", lambda x: x["sueno"] < 6),
    ("Ánimo bajo (≤ 2.5)", lambda x: x["emocion"] <= 2.5),
    ("Sin método de estudio", lambda x: x["metodo"] < 0.5),
    ("Asistencia < 75 %", lambda x: x["asistencia"] < 75),
    ("Nota < 11", lambda x: x["notas"] < 11),
    ("Entendimiento ≤ 2.5", lambda x: x["entendimiento"] <= 2.5),
    ("Interés ≤ 2.5", lambda x: x["interes"] <= 2.5),
    ("Participa poco (≤ 2)", lambda x: x["participacion"] <= 2),
    ("Duerme 10 h o más", lambda x: x["sueno"] >= 10),
    ("Tiene amonestaciones", lambda x: x["amonestaciones"] >= 1),
]


def layout(fig, h=320, **kw):
    fig.update_layout(height=h, margin=dict(l=10, r=10, t=36, b=10), plot_bgcolor="rgba(0,0,0,0)",
                      paper_bgcolor="rgba(0,0,0,0)", font=dict(size=13), **kw)
    return fig


def secretos():
    try:
        return {k: st.secrets[k] for k in st.secrets}
    except Exception:
        return {}


# ---------- acceso (opcional) ----------
def acceso():
    clave = secretos().get("DASHBOARD_PASSWORD")
    if not clave or st.session_state.get("ok"):
        return True
    st.title("Dashboard de bienestar integral")
    st.caption("Uso interno: muestra resultados individuales y alertas.")
    if st.text_input("Contraseña", type="password") == clave:
        st.session_state["ok"] = True
        st.rerun()
    return False


@st.cache_data(ttl=60, show_spinner="Leyendo respuestas…")
def cargar(_clave_cache, archivo_bytes=None):
    s = secretos()
    excel_local = s.get("EXCEL_LOCAL") if s else None
    if excel_local is None and Path("respuestas.xlsx").exists():
        excel_local = "respuestas.xlsx"
    import io
    subida = io.BytesIO(archivo_bytes) if archivo_bytes else None
    df_f, df_s, fuente = datos.leer_fuentes(s, subida, excel_local)
    personas = datos.cargar_personas(df_f, df_s)
    for p in personas:
        if p["valida"]:
            p["res"] = fe.evaluar(p["x"])
            p["recs"] = fe.recomendaciones(p["x"], p["res"])
    return personas, fuente, pd.Timestamp.now(tz="America/Lima").strftime("%d/%m/%Y %H:%M:%S")


def tabla(personas):
    filas = []
    for p in personas:
        r = p["res"]
        v = r["valor"]
        fila = {"ID": p["id"], "Origen": p["origen"], "Fecha": p["marca"], "Carrera": p["carrera"], "Ciclo": p["ciclo"],
                "Cursos": ", ".join(p["cursos"]),
                "Académico": round(v["A"], 1), "Cognitivo": round(v["C"], 1), "Conductual": round(v["Co"], 1),
                "Bienestar": round(v["I"], 1), "Nivel": fe.nivel(v["I"]).capitalize(),
                "Alerta": "Sí" if v["I"] < 35 else "",
                "R1 desaprobados": p["R1"], "R2 abandono": p["R2"], "R3 riesgo curso": p["R3"]}
        for b, nb in (("A", "Académico"), ("C", "Cognitivo"), ("Co", "Conductual")):
            m = r["memb_bloques"][b]
            fila[f"{nb} · conjuntos"] = f"B {m['bajo']:.2f} · M {m['medio']:.2f} · A {m['alto']:.2f}"
        f = r["fuerza"]["I"]
        fila["Bienestar · conjuntos"] = f"B {f['bajo']:.2f} · M {f['medio']:.2f} · A {f['alto']:.2f}"
        fila.update({NOMBRE_VAR[k]: round(p["x"][k], 2) for k in datos.VARS})
        filas.append(fila)
    return pd.DataFrame(filas)


def grafico_conjuntos(var, valor=None, h=210):
    sets = fe.spec()["inputs"][var]["sets"]
    lo, hi = RANGO_VAR[var]
    xs = np.linspace(lo - (0.5 if hi <= 5 else 0), hi + (0.5 if hi <= 5 else 0), 300)
    fig = go.Figure()
    paleta = ["#B9382A", "#C98A16", "#2B7A49", "#7A4BB0"]
    for i, (nv, formas) in enumerate(sets.items()):
        if var == "metodo" and nv == "medio":
            continue
        ys = [fe.mu(x, formas) for x in xs]
        nombre = etiqueta(var, nv)
        if valor is not None:
            nombre += f" ({fe.mu(valor, formas):.2f})"
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", name=nombre, line=dict(width=2.5, color=paleta[i % 4])))
    if valor is not None:
        fig.add_vline(x=valor, line=dict(color="#1C1B3A", width=2, dash="dash"),
                      annotation_text=f"{valor:.2f}", annotation_position="top")
    layout(fig, h, title=dict(text=NOMBRE_VAR[var], font=dict(size=14)), showlegend=True,
           legend=dict(orientation="h", y=-0.25, font=dict(size=11)), yaxis=dict(range=[0, 1.1], title=None))
    return fig


def grafico_salida(res, bloque):
    S = fe.spec()
    fig = go.Figure()
    for nv, formas in S["out_mf"].items():
        fig.add_trace(go.Scatter(x=fe.Y, y=[fe.mu(y, formas) for y in fe.Y], mode="lines",
                                 line=dict(color=COL[nv], width=1.2, dash="dot"), name=f"{nv} (fuerza {res['fuerza'][bloque][nv]:.2f})"))
    fig.add_trace(go.Scatter(x=fe.Y, y=res["curva"][bloque], fill="tozeroy", mode="lines",
                             line=dict(color=COL_BLOQUE[bloque], width=2), fillcolor="rgba(61,59,176,0.18)", name="salida agregada"))
    v = res["valor"][bloque]
    fig.add_vline(x=v, line=dict(color="#1C1B3A", width=2), annotation_text=f"centroide {v:.1f}")
    return layout(fig, 250, title=dict(text=f"{fe.NOMBRE_BLOQUE[bloque]}: salida difusa y centroide", font=dict(size=14)),
                  legend=dict(orientation="h", y=-0.3, font=dict(size=11)), yaxis=dict(range=[0, 1.1]), xaxis=dict(range=[0, 100]))


def texto_regla(r):
    cond = " Y ".join(f"{NOMBRE_VAR.get(v, fe.NOMBRE_BLOQUE.get(v, v)).split(' (')[0].lower()} {etiqueta(v, l)}" for v, l in r["if"].items())
    return f"SI {cond} → {r['then']}"


# ====================================================================================
if not acceso():
    st.stop()

with st.sidebar:
    st.header("Datos")
    subido = st.file_uploader("Excel de respuestas (solo si no hay Google Sheets)", type=["xlsx"])
    if st.button("🔄 Actualizar ahora", width="stretch"):
        st.cache_data.clear()
    personas, fuente, hora = cargar("v10", subido.getvalue() if subido else None)
    st.caption(f"Fuente: **{fuente}**  \nÚltima lectura: {hora}  \nSe vuelve a leer sola cada 60 s al usar la página.")

if not personas:
    st.title("Dashboard de bienestar integral")
    st.info("No hay respuestas todavía. Configura la conexión con Google Sheets (ver README) o sube el Excel en la barra lateral.")
    st.stop()

validas = [p for p in personas if p["valida"]]
excluidas = [p for p in personas if not p["valida"]]
df = tabla(validas)

with st.sidebar:
    st.header("Filtros")
    f_nivel = st.multiselect("Nivel", ["Bajo", "Medio", "Alto"], default=["Bajo", "Medio", "Alto"])
    f_carrera = st.multiselect("Carrera", sorted(df["Carrera"].unique()))
    f_ciclo = st.multiselect("Ciclo", sorted(df["Ciclo"].astype(str).unique()))
    cursos = sorted({c for p in validas for c in p["cursos"]})
    f_curso = st.multiselect("Curso", cursos)
    f_origen = st.multiselect("Origen", sorted(df["Origen"].unique()))

m = df["Nivel"].isin(f_nivel)
if f_carrera: m &= df["Carrera"].isin(f_carrera)
if f_ciclo: m &= df["Ciclo"].astype(str).isin(f_ciclo)
if f_curso: m &= df["Cursos"].apply(lambda s: any(c in s for c in f_curso))
if f_origen: m &= df["Origen"].isin(f_origen)
dff = df[m]
ids = set(dff["ID"])
sel = [p for p in validas if p["id"] in ids]

st.title("Dashboard de bienestar integral")
st.caption("Sistema difuso jerárquico Mamdani · 10 variables · 3 bloques + integrador · 71 reglas · uso interno")

# ---------- KPIs ----------
k = st.columns(6)
k[0].metric(f"Respuestas válidas (de {len(personas)})", f"{len(dff)}")
k[1].metric("Bienestar promedio", f"{dff['Bienestar'].mean():.1f}" if len(dff) else "–")
for i, nv in enumerate(["Bajo", "Medio", "Alto"]):
    n = int((dff["Nivel"] == nv).sum())
    k[2 + i].metric(f"Nivel {nv.lower()} · {(100 * n / len(dff)) if len(dff) else 0:.0f} %", f"{n}")
k[5].metric("🔴 Alertas internas (< 35)", f"{int((dff['Alerta'] == 'Sí').sum())}")

tab1, tab2, tab3, tab4, tab5 = st.tabs(["Panorama", "Personas", "Detalle por persona", "Validación", "Modelo"])

# ---------- Panorama ----------
with tab1:
    c1, c2 = st.columns(2)
    with c1:
        fig = go.Figure()
        for a, b, nv in ((0, 35, "bajo"), (35, 65, "medio"), (65, 100, "alto")):
            fig.add_vrect(x0=a, x1=b, fillcolor=COL[nv], opacity=0.08, line_width=0)
        fig.add_trace(go.Histogram(x=dff["Bienestar"], xbins=dict(start=0, end=100, size=5), marker_color="#3D3BB0"))
        st.plotly_chart(layout(fig, title="Distribución del bienestar integral", xaxis=dict(range=[0, 100], title="Bienestar"),
                               yaxis=dict(title="Personas"), bargap=0.08), width="stretch")
    with c2:
        fig = go.Figure()
        for b, nb in (("A", "Académico"), ("C", "Cognitivo"), ("Co", "Conductual"), ("I", "Bienestar")):
            fig.add_trace(go.Box(y=dff[nb], name=nb, marker_color=COL_BLOQUE[b], boxpoints="all", jitter=0.4, pointpos=0))
        st.plotly_chart(layout(fig, title="Las tres dimensiones y el resultado", showlegend=False,
                               yaxis=dict(range=[0, 100])), width="stretch")
    c3, c4 = st.columns(2)
    with c3:
        fig = go.Figure()
        fig.add_shape(type="rect", x0=65, x1=100, y0=0, y1=35, fillcolor="#B9382A", opacity=0.07, line_width=0)
        for nv in ("Bajo", "Medio", "Alto"):
            d = dff[dff["Nivel"] == nv]
            fig.add_trace(go.Scatter(x=d["Académico"], y=d["Conductual"], mode="markers", name=nv, text=d["ID"],
                                     marker=dict(size=11, color=COL[nv.lower()], line=dict(color="white", width=1)),
                                     hovertemplate="%{text}<br>Académico %{x}<br>Conductual %{y}<extra></extra>"))
        st.plotly_chart(layout(fig, 340, title="Académico vs. conductual", xaxis=dict(range=[0, 100], title="Académico"),
                               yaxis=dict(range=[0, 100], title="Conductual")), width="stretch")
        st.caption("Zona sombreada: académico ≥ 65 y conductual < 35, es decir, rinde bien pero no está bien.")
    with c4:
        cnt = [(nombre, sum(f(p["x"]) for p in sel)) for nombre, f in SENALES]
        cnt = sorted(cnt, key=lambda t: t[1])
        fig = go.Figure(go.Bar(y=[c[0] for c in cnt], x=[100 * c[1] / max(len(sel), 1) for c in cnt], orientation="h",
                               marker_color="#B5602F", text=[f"{c[1]}" for c in cnt], textposition="outside"))
        st.plotly_chart(layout(fig, 340, title="Señales más frecuentes (% de personas)", xaxis=dict(title="%", range=[0, 105])),
                        width="stretch")
    c5, c6 = st.columns(2)
    with c5:
        ap = pd.Series([a for p in sel for a in p["apoyo"] if a]).value_counts().sort_values()
        if len(ap):
            fig = go.Figure(go.Bar(y=ap.index, x=ap.values, orientation="h", marker_color="#3D3BB0"))
            st.plotly_chart(layout(fig, 300, title="Apoyo que piden los estudiantes"), width="stretch")
        else:
            st.caption("Sin datos de apoyo solicitado.")
    with c6:
        if dff["Fecha"].notna().any():
            fechas = pd.to_datetime(dff["Fecha"], errors="coerce", dayfirst=True).dt.date.value_counts().sort_index()
            fig = go.Figure(go.Bar(x=[str(d) for d in fechas.index], y=fechas.cumsum().values, marker_color="#2F6DB5"))
            st.plotly_chart(layout(fig, 300, title="Respuestas acumuladas por día", xaxis=dict(type="category")), width="stretch")

# ---------- Personas ----------
with tab2:
    st.caption("Cada fila es una persona. “Conjuntos” = grado de pertenencia del valor de cada dimensión a bajo (B), medio (M) y alto (A); "
               "en el bienestar es la fuerza con que se activó cada nivel de salida.")
    cols = ["ID", "Fecha", "Carrera", "Ciclo", "Cursos", "Académico", "Académico · conjuntos", "Cognitivo", "Cognitivo · conjuntos",
            "Conductual", "Conductual · conjuntos", "Bienestar", "Bienestar · conjuntos", "Nivel", "Alerta", "Origen"]
    st.dataframe(dff[cols].sort_values("Bienestar"), width="stretch", hide_index=True, height=520,
                 column_config={c: st.column_config.ProgressColumn(c, min_value=0, max_value=100, format="%.1f")
                                for c in ("Académico", "Cognitivo", "Conductual", "Bienestar")})
    st.download_button("Descargar CSV completo (incluye las 10 variables)", dff.to_csv(index=False).encode("utf-8-sig"),
                       "bienestar_resultados.csv", "text/csv")
    if excluidas:
        with st.expander(f"Respuestas excluidas ({len(excluidas)})"):
            st.dataframe(pd.DataFrame([{"ID": p["id"], "Fecha": p["marca"], "Motivo": p["motivo"]} for p in excluidas]),
                         hide_index=True, width="stretch")

# ---------- Detalle por persona ----------
with tab3:
    if not sel:
        st.info("No hay personas con estos filtros.")
    else:
        opciones = {f"{p['id']} · bienestar {p['res']['valor']['I']:.1f} ({fe.nivel(p['res']['valor']['I'])}) · {p['carrera']}": p
                    for p in sorted(sel, key=lambda p: p["res"]["valor"]["I"])}
        p = opciones[st.selectbox("Persona", list(opciones))]
        r = p["res"]
        cc = st.columns(4)
        for col_, b in zip(cc, ("A", "C", "Co", "I")):
            v = r["valor"][b]
            with col_:
                st.markdown(f"**{fe.NOMBRE_BLOQUE[b]}**")
                st.markdown(f"<span style='font-size:2.2rem;font-weight:700;color:{COL[fe.nivel(v)]}'>{v:.1f}</span> "
                            f"<span style='color:{COL[fe.nivel(v)]}'>{fe.nivel(v)}</span>", unsafe_allow_html=True)
                g = r["memb_bloques"][b] if b != "I" else r["fuerza"]["I"]
                rot = "pertenencia del valor" if b != "I" else "fuerza de salida"
                fig = go.Figure(go.Bar(x=["bajo", "medio", "alto"], y=[g["bajo"], g["medio"], g["alto"]],
                                       marker_color=[COL["bajo"], COL["medio"], COL["alto"]],
                                       text=[f"{g[k]:.2f}" for k in ("bajo", "medio", "alto")], textposition="outside"))
                st.plotly_chart(layout(fig, 190, title=dict(text=rot, font=dict(size=12)), yaxis=dict(range=[0, 1.25], visible=False)),
                                width="stretch", key=f"bar{b}")

        st.subheader("Recomendaciones")
        for rec in p["recs"]:
            (st.error if rec["interna"] else st.info)(f"{rec['msg']}  \n*{rec['src']}*")

        st.subheader("Respuestas y fuzzificación de cada variable")
        filas = []
        for v in datos.VARS:
            mm = r["memb"][v]
            filas.append({"Variable": NOMBRE_VAR[v], "Bloque": fe.NOMBRE_BLOQUE[fe.spec()["inputs"][v]["block"]], "Valor": round(p["x"][v], 2),
                          "Pertenencias": " · ".join(f"{etiqueta(v, k)} {g:.2f}" for k, g in mm.items() if not (v == "metodo" and k == "medio")),
                          "Conjunto dominante": etiqueta(v, max(mm, key=mm.get))})
        st.dataframe(pd.DataFrame(filas), hide_index=True, width="stretch")
        with st.expander("Respuestas originales de la encuesta"):
            st.dataframe(pd.DataFrame([{"Pregunta": k, "Respuesta": v} for k, v in p["crudo"].items()]).astype(str),
                         hide_index=True, width="stretch")

        st.subheader("Funciones de pertenencia con el valor de esta persona")
        g = st.columns(2)
        for i, v in enumerate(datos.VARS):
            g[i % 2].plotly_chart(grafico_conjuntos(v, p["x"][v]), width="stretch", key=f"mf{v}")

        st.subheader("Reglas activadas y salida de cada bloque")
        for b in ("A", "C", "Co", "I"):
            act = sorted([a for a in r["reglas"][b] if a["alfa"] > 0], key=lambda a: -a["alfa"])
            c1, c2 = st.columns([1.1, 1])
            with c1:
                st.markdown(f"**{fe.NOMBRE_BLOQUE[b]}** · {len(act)} de {len(r['reglas'][b])} reglas activas")
                st.dataframe(pd.DataFrame([{"Regla": a["id"], "α": round(a["alfa"], 2), "Regla en palabras": texto_regla(a),
                                            "Fuente": a["why"]} for a in act]),
                             hide_index=True, width="stretch",
                             column_config={"α": st.column_config.ProgressColumn("α", min_value=0, max_value=1, format="%.2f")})
            with c2:
                st.plotly_chart(grafico_salida(r, b), width="stretch", key=f"out{b}")

# ---------- Validación ----------
with tab4:
    st.caption("Las variables R1–R3 están en la encuesta pero no entran al modelo: solo se comparan con el bienestar. "
               "Se espera correlación negativa (más bienestar, menos problemas).")
    cols = st.columns(3)
    for col_, (crit, nombre) in zip(cols, (("R2 abandono", "Intención de abandono (R2)"),
                                           ("R1 desaprobados", "Cursos desaprobados (R1)"),
                                           ("R3 riesgo curso", "Riesgo percibido en el curso (R3)"))):
        d = dff[["Bienestar", crit]].dropna()
        rho = d["Bienestar"].rank().corr(d[crit].rank()) if len(d) > 3 else float("nan")
        col_.metric(nombre, f"ρ = {rho:+.2f}" if not math.isnan(rho) else "–", f"n = {len(d)}", delta_color="off")
        fig = go.Figure(go.Scatter(x=d["Bienestar"], y=d[crit], mode="markers", marker=dict(size=10, color="#3D3BB0", opacity=0.7)))
        col_.plotly_chart(layout(fig, 280, xaxis=dict(title="Bienestar", range=[0, 100]), yaxis=dict(title=crit)),
                          width="stretch", key=f"val{crit}")
    st.caption("ρ de Spearman. Con muestras pequeñas los intervalos de confianza son amplios: interpretar con cautela.")

# ---------- Modelo ----------
with tab5:
    st.markdown("**Funciones de pertenencia de las 10 variables** (unidades de la encuesta). "
                "Trapecios en los extremos (certeza), triángulos en el medio (transición).")
    g = st.columns(2)
    for i, v in enumerate(datos.VARS):
        g[i % 2].plotly_chart(grafico_conjuntos(v), width="stretch", key=f"mfm{v}")
    with st.expander("Las 71 reglas"):
        S = fe.spec()
        for b in ("A", "C", "Co", "I"):
            st.markdown(f"**{fe.NOMBRE_BLOQUE[b]}** ({len(S['rules'][b])} reglas)")
            st.dataframe(pd.DataFrame([{"Regla": r_["id"], "Regla en palabras": texto_regla(r_), "Fuente": r_.get("why", "")}
                                       for r_ in S["rules"][b]]), hide_index=True, width="stretch")
