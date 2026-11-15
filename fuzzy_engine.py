"""Motor Mamdani jerárquico v10 (mismo algoritmo que fis.py, fis_jerarquico.m y el simulador web).

AND = mínimo, implicación = mínimo, agregación = máximo, defuzzificación por centroide
sobre y = 0, 0.1, ..., 100. Si ninguna regla de un bloque se activa, el bloque vale 50.
"""
import json
from functools import lru_cache
from pathlib import Path

import numpy as np

SPEC_PATH = Path(__file__).with_name("fis_v10_spec.json")
Y = np.round(np.arange(0, 100.0001, 0.1), 1)
BLOQUES = ("A", "C", "Co")
NOMBRE_BLOQUE = {"A": "Académico", "C": "Cognitivo", "Co": "Conductual", "I": "Bienestar integral"}


@lru_cache(maxsize=1)
def spec():
    return json.loads(SPEC_PATH.read_text(encoding="utf-8"))


def _shape(x, s):
    if s[0] == "trap":
        _, a, b, c, d = s
        if x <= a or x >= d:
            return 0.0
        if b <= x <= c:
            return 1.0
        return (x - a) / (b - a) if x < b else (d - x) / (d - c)
    _, a, b, c = s
    if x <= a or x >= c:
        return 0.0
    return (x - a) / (b - a) if x < b else (c - x) / (c - b)


def mu(x, shapes):
    """Grado de pertenencia de x a un conjunto (unión de sus formas)."""
    return max(_shape(x, s) for s in shapes)


def fuzzify(x, sets):
    return {nivel: mu(x, formas) for nivel, formas in sets.items()}


@lru_cache(maxsize=1)
def _curvas_salida():
    out = spec()["out_mf"]
    return {nivel: np.array([mu(y, f) for y in Y]) for nivel, f in out.items()}


def inferir(memb, reglas):
    """Devuelve (valor, activaciones, fuerza por consecuente, curva agregada)."""
    curvas = _curvas_salida()
    agg = np.zeros_like(Y)
    acts = []
    fuerza = {"bajo": 0.0, "medio": 0.0, "alto": 0.0}
    for r in reglas:
        a = min(memb[v][l] for v, l in r["if"].items())
        acts.append({"id": r["id"], "alfa": a, "then": r["then"], "if": r["if"], "why": r.get("why", "")})
        if a > 0:
            agg = np.maximum(agg, np.minimum(a, curvas[r["then"]]))
            fuerza[r["then"]] = max(fuerza[r["then"]], a)
    s = agg.sum()
    valor = float((Y * agg).sum() / s) if s > 0 else 50.0
    return valor, acts, fuerza, agg


def evaluar(x):
    """x: dict con las 10 variables en unidades de la encuesta.

    Devuelve un dict con: valores de cada bloque y del bienestar, pertenencias de cada
    variable, pertenencias de cada bloque (re-fuzzificación), fuerza de salida por nivel,
    reglas activadas y la curva agregada de cada nivel."""
    S = spec()
    memb = {v: fuzzify(x[v], S["inputs"][v]["sets"]) for v in S["inputs"]}
    res = {"valor": {}, "fuerza": {}, "reglas": {}, "curva": {}, "memb": memb}
    for b in BLOQUES:
        v, acts, fz, cur = inferir(memb, S["rules"][b])
        res["valor"][b], res["reglas"][b], res["fuerza"][b], res["curva"][b] = v, acts, fz, cur
    res["memb_bloques"] = {b: fuzzify(res["valor"][b], S["block_mf"]) for b in BLOQUES}
    v, acts, fz, cur = inferir(res["memb_bloques"], S["rules"]["I"])
    res["valor"]["I"], res["reglas"]["I"], res["fuerza"]["I"], res["curva"]["I"] = v, acts, fz, cur
    return res


def nivel(valor):
    return "bajo" if valor < 35 else ("medio" if valor < 65 else "alto")


def recomendaciones(x, res):
    """Mismas condiciones que la encuesta del estudiante, más la alerta interna."""
    r = res["valor"]
    B = r["I"]
    out = []

    def add(rid, msg, src, interna=False):
        out.append({"id": rid, "msg": msg, "src": src, "interna": interna})

    if r["A"] >= 65 and r["Co"] < 35:
        add("rec_cond", "Académicamente va bien, pero su descanso y su ánimo están bajos.", "Benítez-Agudelo et al. 2025")
    if x["sueno"] < 6:
        add("rec_sueno_bajo", "Duerme menos de 6 horas: apuntar a 7–9 horas con horario regular.", "Hirshkowitz et al. 2015; Creswell et al. 2023")
    if x["sueno"] >= 10:
        add("rec_sueno_alto", "Duerme 10 horas o más: si aun así se siente cansado, derivar a Bienestar.", "Vedaa et al. 2019")
    if x["emocion"] <= 2.5:
        add("rec_emo", "Se ha sentido agobiado: ofrecer apoyo de Bienestar Estudiantil (manejo del estrés, mindfulness).", "Regehr et al. 2013")
    if x["asistencia"] < 75:
        add("rec_asis", "Asistencia por debajo del 75 %.", "Credé et al. 2010; Tomal et al. 2026")
    if x["horas"] >= 5 and x["notas"] < 12:
        add("rec_horas_nota", "Dedica bastante tiempo pero no se refleja en la nota: revisar técnicas de estudio.", "Theobald 2021")
    if x["metodo"] < 0.5:
        add("rec_metodo", "Sin método de estudio: horario semanal y metas por curso.", "Theobald 2021; Broadbent et al. 2015")
    if all(35 <= r[b] < 65 for b in BLOQUES) and r["C"] >= 55:
        add("rec_metodo_casi", "Cerca de un buen nivel: un método de estudio es lo que más suele sumar.", "Theobald 2021")
    if x["entendimiento"] <= 2.5:
        add("rec_ent", "Le cuesta entender los temas: tutoría o grupo de estudio.", "Zhang et al. 2024")
    if x["interes"] <= 2.5:
        add("rec_int", "Poco interés: conectar el curso con sus metas; conversar con su tutor.", "Howard et al. 2021")
    if x["participacion"] <= 2:
        add("rec_part", "Participa poco en clase.", "Lei et al. 2018")
    if B < 35:
        add("rec_alerta", "ALERTA INTERNA: bienestar bajo. Ofrecer mentoría o derivar a tutoría (no se muestra al estudiante).",
            "Alonso García et al. 2024; Sinval et al. 2024", interna=True)
    if not out and B >= 65:
        add("rec_ok", "Va bien en las tres dimensiones.", "—")
    return out
