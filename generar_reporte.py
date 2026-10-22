#!/usr/bin/env python3
"""Reporte semanal del Portafolio Familiar Cañas en HTML estático (sin JavaScript).

Diseño: design system de Gardens Capital (negro, índigo, celeste; Archivo + Inter).
Entrada: datos.json con los rangos del Google Sheet tal como los devuelve get_values:
  {"reporte": Reporte!A9:B34, "posiciones": Posiciones!A5:S,
   "dashboard": Dashboard!B12:E38, "historial": Historial!A10:S,
   "comentario": "2-4 frases"}
Salida (en --out):
  index.html              página completa para GitHub Pages
  semanas/AAAA-MM-DD.html copia completa de la semana, para el archivo histórico
  correo.html             cuerpo HTML del correo corto con el link al reporte
Uso: python3 generar_reporte_html.py datos.json --out out
"""
import argparse, html, json, os, re

REPORTE_URL = "https://gardenscapitalc-sys.github.io/reporte-portafolio/"
SHEET_URL = "https://docs.google.com/spreadsheets/d/14j5TB0maSm-NzgNHmpWBjChqdz0DZ_d_dBAjmH-v3n8/edit"
E = html.escape

# ---------------------------------------------------------------- datos

def num(s):
    if s is None:
        return None
    s = str(s).strip()
    if not s or s.startswith("#") or s.lower().startswith(("cargando", "sin datos", "loading")):
        return None
    pct = s.endswith("%")
    neg = s.startswith("-") or s.startswith("(")
    t = re.sub(r"[^0-9,.]", "", s)
    if not t:
        return None
    try:
        v = float(t.replace(".", "").replace(",", "."))
    except ValueError:
        return None
    v = -v if neg else v
    return v / 100 if pct else v


def load(path):
    d = json.load(open(path, encoding="utf-8"))
    rep = {}
    for row in d["reporte"]:
        if row:
            rep[row[0].strip()] = row[1] if len(row) > 1 else ""
    pos = []
    for r in d["posiciones"]:
        r = list(r) + [""] * (19 - len(r))
        if r[0]:
            pos.append({"ticker": r[0], "nombre": r[1], "clase": r[2], "cuentas": r[5],
                        "valor": num(r[10]), "pg": num(r[11]), "pg_pct": num(r[12]), "peso": num(r[13]),
                        "vol": num(r[16]), "beta": num(r[17]), "sem": num(r[18])})
    rows = d["dashboard"]
    clases = [(r[0], num(r[1]), num(r[2])) for r in rows[1:6] if len(r) >= 3 and r[0]]
    cuentas, start = [], None
    for i, r in enumerate(rows):
        if r and r[0] == "Cuenta":
            start = i + 1
    if start is not None:
        cuentas = [(r[0], r[1], num(r[2]), num(r[3])) for r in rows[start:] if len(r) >= 4 and r[0]]
    hist = [{"fecha": r[0], "valor": num(r[1]) if len(r) > 1 else None, "capital": num(r[4]) if len(r) > 4 else None}
            for r in d.get("historial", []) if r and r[0]]
    return rep, pos, clases, cuentas, hist, d.get("comentario", "").strip()

# ---------------------------------------------------------------- formato

def usd(v, dec=0):
    if v is None:
        return "–"
    s = f"{abs(v):,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return ("−$" if v < 0 else "$") + s


def cop(v):
    return "–" if v is None else "COP " + f"{v:,.0f}".replace(",", ".")


def pct(v, dec=1, sign=True):
    if v is None:
        return "–"
    s = f"{v*100:+.{dec}f}%" if sign else f"{v*100:.{dec}f}%"
    return s.replace(".", ",").replace("-", "−")


def tone(v):
    return "" if v is None or abs(v) < 0.0005 else ("pos" if v > 0 else "neg")


def iso(fecha):
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", fecha or "")
    return "%s-%02d-%02d" % (m.group(3), int(m.group(2)), int(m.group(1))) if m else (fecha or "")

# ---------------------------------------------------------------- gráficas SVG

POS, NEG = "#2f7d55", "#b4473d"
INDIGO, CELESTE, NOCHE, AGUA, PLATA, TINTA_SUAVE = "#575da1", "#6cbddf", "#36415a", "#8ac6cf", "#bfc0c0", "#5b606b"
SERIE = [INDIGO, CELESTE, NOCHE, AGUA, PLATA, "#9a9fd0", "#2f6f8f"]


def svg_movers(items, w=620):
    """Barras divergentes: items = [(ticker, cambio)] ordenados de mayor a menor."""
    if not items:
        return ""
    row, top, lab = 30, 8, 64
    h = top * 2 + row * len(items)
    mpos = max([v for _, v in items] + [0])
    mneg = max([-v for _, v in items] + [0])
    tot = (mpos + mneg) or 1
    avail = w - lab - 120
    x0 = lab + 50 + avail * mneg / tot
    out = ['<svg viewBox="0 0 %d %d" role="img" aria-label="Cambio semanal por posición" class="chart">' % (w, h)]
    out.append('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="var(--linea-fuerte)" stroke-width="1"/>' % (x0, top - 4, x0, h - top + 4))
    for i, (t, v) in enumerate(items):
        y = top + i * row
        L = avail * abs(v) / tot
        x = x0 if v >= 0 else x0 - L
        c = POS if v >= 0 else NEG
        out.append('<text x="%d" y="%.1f" class="ax-l">%s</text>' % (lab - 10, y + row / 2 + 4, E(t)))
        out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%d" rx="3" fill="%s"/>' % (x, y + 7, max(L, 1.5), row - 14, c))
        tx, anchor = (x0 + L + 6, "start") if v >= 0 else (x0 - L - 6, "end")
        out.append('<text x="%.1f" y="%.1f" text-anchor="%s" class="ax-v" fill="%s">%s</text>' % (tx, y + row / 2 + 4, anchor, c, pct(v)))
    out.append("</svg>")
    return "".join(out)


def svg_vs(cats, port, spy, w=620, h=250):
    """Barras agrupadas portafolio vs S&P 500 (valores en fracción)."""
    vals = [v for v in port + spy if v is not None] + [0]
    lo, hi = min(vals), max(vals)
    pad = (hi - lo) * 0.18 or 0.01
    lo, hi = min(0, lo - pad * (lo < 0)), hi + pad
    top, bot, left = 24, 34, 8
    ph = h - top - bot
    y = lambda v: top + ph * (hi - v) / (hi - lo)
    out = ['<svg viewBox="0 0 %d %d" role="img" aria-label="Portafolio frente al S&amp;P 500" class="chart vs">' % (w, h)]
    out.append('<line x1="%d" x2="%d" y1="%.1f" y2="%.1f" stroke="var(--linea-fuerte)"/>' % (left, w - left, y(0), y(0)))
    gw = (w - 2 * left) / len(cats)
    bw = min(64, gw * 0.28)
    for i, c in enumerate(cats):
        cx = left + gw * i + gw / 2
        for j, (v, col) in enumerate(((port[i], INDIGO), (spy[i], PLATA))):
            if v is None:
                continue
            x = cx - bw - 4 + j * (bw + 8)
            y1, y2 = sorted((y(0), y(v)))
            out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="3" fill="%s"/>' % (x, y1, bw, max(y2 - y1, 1.5), col))
            ty = y(v) - 7 if v >= 0 else y(v) + 16
            out.append('<text x="%.1f" y="%.1f" text-anchor="middle" class="ax-v">%s</text>' % (x + bw / 2, ty, pct(v)))
        out.append('<text x="%.1f" y="%d" text-anchor="middle" class="ax-c">%s</text>' % (cx, h - 10, E(c)))
    out.append("</svg>")
    return "".join(out)


def stacked(items, total=None):
    """Barra 100% en HTML (accesible y nítida) + leyenda. items = [(nombre, valor, color, extra)]."""
    items = [it for it in items if it[1]]
    total = total or sum(it[1] for it in items) or 1
    bar = "".join('<span style="width:%.2f%%;background:%s" title="%s"></span>' % (100 * v / total, c, E(n)) for n, v, c, _ in items)
    leg = "".join('<li><i style="background:%s"></i><span class="lg-n">%s</span><span class="lg-x">%s</span>'
                  '<span class="lg-v num">%s</span><span class="lg-p num">%s</span></li>'
                  % (c, E(n), E(x), usd(v), pct(v / total, 1, False)) for n, v, c, x in items)
    return '<div class="stack">%s</div><ul class="legend">%s</ul>' % (bar, leg)


def svg_line(hp, w=980, h=280):
    vals = [p["valor"] for p in hp] + [p["capital"] or 0 for p in hp]
    lo, hi = min(vals), max(vals)
    pad = (hi - lo) * 0.15 or hi * 0.02
    lo, hi = lo - pad, hi + pad
    top, bot, left, right = 20, 30, 70, 16
    pw, ph = w - left - right, h - top - bot
    n = len(hp)
    X = lambda i: left + (pw * i / (n - 1) if n > 1 else pw / 2)
    Y = lambda v: top + ph * (hi - v) / (hi - lo)
    out = ['<svg viewBox="0 0 %d %d" role="img" aria-label="Evolución del valor y del capital aportado" class="chart">' % (w, h)]
    for k in range(5):
        v = lo + (hi - lo) * k / 4
        out.append('<line x1="%d" x2="%d" y1="%.1f" y2="%.1f" stroke="var(--linea)"/>' % (left, w - right, Y(v), Y(v)))
        out.append('<text x="%d" y="%.1f" text-anchor="end" class="ax-c">%s</text>' % (left - 8, Y(v) + 4, usd(round(v, -3))))
    cap = " ".join("%.1f,%.1f" % (X(i), Y(p["capital"] or 0)) for i, p in enumerate(hp))
    val = " ".join("%.1f,%.1f" % (X(i), Y(p["valor"])) for i, p in enumerate(hp))
    area = "%.1f,%.1f %s %.1f,%.1f" % (X(0), top + ph, val, X(n - 1), top + ph)
    out.append('<polygon points="%s" fill="%s" fill-opacity=".10"/>' % (area, INDIGO))
    out.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="2" stroke-dasharray="5 5"/>' % (cap, TINTA_SUAVE))
    out.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="2.5"/>' % (val, INDIGO))
    out.append('<circle cx="%.1f" cy="%.1f" r="4.5" fill="%s"/>' % (X(n - 1), Y(hp[-1]["valor"]), INDIGO))
    step = max(1, n // 8)
    for i, p in enumerate(hp):
        if i % step == 0 or i == n - 1:
            out.append('<text x="%.1f" y="%d" text-anchor="middle" class="ax-c">%s</text>' % (X(i), h - 8, E(p["fecha"][:5])))
    out.append("</svg>")
    return "".join(out)

# ---------------------------------------------------------------- página

CSS = """
:root{--negro:#0e0f12;--negro-2:#08090b;--grafito:#15161b;--tinta:#16171a;--tinta-suave:#5b606b;--blanco:#fff;--blanco-2:#f6f7f9;
--indigo:#575da1;--celeste:#6cbddf;--pos:#2f7d55;--neg:#b4473d;--pos-o:#6fd39e;--neg-o:#ff8f85;
--linea:rgba(20,23,26,.10);--linea-fuerte:rgba(20,23,26,.35);
--f-titulo:"Archivo","Lucidity Expand",system-ui,sans-serif;--f-texto:"Inter","Open Sauce",system-ui,sans-serif;color-scheme:light}
/* Layout: secciones a ancho completo que alternan negro y claro, contenido a 1080px */
body{background:var(--blanco);color:var(--tinta);font-family:var(--f-texto);font-size:15px;line-height:1.6}
.sec{overflow-x:clip;padding-block:64px;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}
.sec>.in{max-width:1080px;margin:0 auto;display:grid;gap:28px;min-width:0}
.alt{background:var(--blanco-2)}
.os{background:var(--negro);color:var(--blanco);--linea:rgba(255,255,255,.12);--linea-fuerte:rgba(255,255,255,.4)}
.os .sub,.os .nota{color:rgba(255,255,255,.72)}
.eyebrow{display:flex;align-items:center;gap:12px;font:700 .74rem/1.2 var(--f-texto);letter-spacing:.2em;text-transform:uppercase;color:var(--indigo)}
.eyebrow::before{content:"";width:26px;height:2px;background:var(--celeste)}
.os .eyebrow{color:var(--celeste)}
h1,h2,h3,.num-g{font-family:var(--f-titulo);letter-spacing:-.02em;line-height:1.06;margin:0;text-wrap:balance}
h1{font-size:clamp(2.2rem,5vw,3.4rem);font-weight:900;letter-spacing:-.03em}
h2{font-size:clamp(1.6rem,3.4vw,2.3rem);font-weight:800}
h3{font-size:1.1rem;font-weight:800}
p{margin:0;max-width:64ch}
.sub{color:var(--tinta-suave)}
.num{font-variant-numeric:tabular-nums}
.pos{color:var(--pos)}.neg{color:var(--neg)}
.os .pos{color:var(--pos-o)}.os .neg{color:var(--neg-o)}
.hero-top{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:flex-end;gap:24px}
.valor{font-family:var(--f-titulo);font-weight:900;font-size:clamp(2.6rem,7vw,4.6rem);letter-spacing:-.03em;line-height:1;font-variant-numeric:tabular-nums}
.kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));border-top:1px solid var(--linea)}
.kpi{padding:18px 18px 4px 0;display:grid;gap:4px;min-width:0}
.kpi+.kpi{padding-left:18px;border-left:1px solid var(--linea)}
.kpi .lb{font-size:.74rem;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:rgba(255,255,255,.6)}
.kpi .v{font-family:var(--f-titulo);font-weight:800;font-size:1.9rem;letter-spacing:-.02em;font-variant-numeric:tabular-nums}
.kpi .sp{font-size:.85rem;color:rgba(255,255,255,.65)}
.chips{display:flex;flex-wrap:wrap;gap:10px;padding:0;margin:0;list-style:none}
.chip{border:1px solid var(--linea-fuerte);border-radius:999px;padding:6px 14px;font-size:.85rem;display:flex;gap:8px;align-items:center}
.chip::before{content:"";width:7px;height:7px;border-radius:50%;background:var(--celeste)}
.chip.alerta::before{background:var(--neg)}
.cols2{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:24px;align-items:start}
.vs{max-width:760px}
.cols{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.25fr);gap:40px;align-items:start}
.card{background:var(--blanco);border:1px solid var(--linea);border-radius:14px;padding:24px 24px 18px;min-width:0}
.os .card{background:var(--grafito)}
.chart{width:100%;height:auto;display:block;overflow:visible}
.ax-l{font:600 12px var(--f-texto);fill:currentColor;text-anchor:end}
.ax-v{font:700 12px var(--f-titulo);fill:currentColor;font-variant-numeric:tabular-nums}
.ax-c{font:500 11px var(--f-texto);fill:var(--tinta-suave)}
.key{display:flex;gap:18px;font-size:.85rem;color:var(--tinta-suave);flex-wrap:wrap}
.key i{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:6px;vertical-align:-1px}
.tw{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:.92rem}
th{font-size:.72rem;letter-spacing:.14em;text-transform:uppercase;color:var(--tinta-suave);text-align:left;font-weight:700;padding:8px 10px;border-bottom:1px solid var(--linea-fuerte)}
td{padding:10px;border-bottom:1px solid var(--linea);vertical-align:middle}
td.r,th.r{text-align:right}
td.t{font-family:var(--f-titulo);font-weight:800}
tr.caja td{border-top:2px solid var(--linea-fuerte);border-bottom:0;background:rgba(108,189,223,.08)}
.peso{display:flex;align-items:center;gap:10px;justify-content:flex-end}
.peso b{display:block;height:6px;border-radius:3px;background:var(--indigo)}
.stack{display:flex;height:22px;border-radius:7px;overflow:hidden;gap:2px;background:var(--linea)}
.stack span{display:block;min-width:2px}
.legend{list-style:none;padding:0;margin:14px 0 0;display:grid;gap:8px}
.legend li{display:grid;grid-template-columns:14px minmax(0,1fr) auto auto;gap:10px;align-items:center;font-size:.92rem}
.legend i{width:12px;height:12px;border-radius:3px}
.lg-x{display:none}.lg-v{color:var(--tinta-suave)}.lg-p{font-weight:700;min-width:52px;text-align:right}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:16px}
.tile{border:1px solid var(--linea);border-radius:14px;padding:20px;display:grid;gap:6px;background:var(--grafito)}
.tile .lb{font-size:.72rem;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:rgba(255,255,255,.6)}
.tile .v{font-family:var(--f-titulo);font-weight:800;font-size:1.7rem;font-variant-numeric:tabular-nums}
.tile .d{font-size:.85rem;color:rgba(255,255,255,.7)}
.meter{height:6px;border-radius:3px;background:rgba(255,255,255,.12);overflow:hidden}
.meter b{display:block;height:100%;background:var(--celeste)}
.nota{font-size:.82rem;color:var(--tinta-suave);max-width:80ch}
.pie{background:var(--negro-2);color:rgba(255,255,255,.75)}
.pie a{color:var(--celeste)}
.archivo{display:flex;flex-wrap:wrap;gap:8px 18px;padding:0;margin:0;list-style:none;font-size:.9rem}
@media (max-width:820px){.cols,.cols2{grid-template-columns:minmax(0,1fr)}.kpis{grid-template-columns:repeat(2,minmax(0,1fr))}
.kpi:nth-child(3){padding-left:0;border-left:0}.sec{padding-block:48px}}
@media (max-width:460px){.kpis{grid-template-columns:minmax(0,1fr)}.kpi+.kpi{padding-left:0;border-left:0;border-top:1px solid var(--linea)}}
"""


def build(rep, pos, clases, cuentas, hist, comentario):
    g = lambda k: rep.get(k, "")
    fecha = g("Fecha del reporte")
    valor, vcop = num(g("Valor total USD")), num(g("Valor total COP"))
    capital, ganancia = num(g("Capital aportado neto")), num(g("Ganancia total USD"))
    r_crea, r_ytd = num(g("Rentabilidad desde creación")), num(g("Rentabilidad YTD"))
    sem_foto, sem_usd = num(g("Cambio desde la foto anterior %")), num(g("Cambio desde la foto anterior USD"))
    sem = sem_foto if sem_foto is not None else num(g("Cambio de la semana (posiciones actuales)"))
    spy_sem, spy_crea, spy_ytd = num(g("S&P 500 última semana")), num(g("S&P 500 desde la creación")), num(g("S&P 500 YTD"))
    vol, beta = num(g("Volatilidad anual")), num(g("Beta vs S&P 500"))
    efectivo, alerta_ef = num(g("% en efectivo")), g("Alerta de efectivo")
    top5, mayor, mayor_peso = num(g("Peso de las 5 mayores posiciones")), g("Mayor posición"), num(g("Peso de la mayor posición"))
    caidas = g("Posiciones con caída fuerte vs costo") or "Ninguna"

    CAJA = ("Efectivo", "Efectivo remunerado")
    caja = [p for p in pos if p["clase"] in CAJA]
    caja_val = sum(p["valor"] or 0 for p in caja)
    caja_pct = sum(p["peso"] or 0 for p in caja)
    inv = [p for p in pos if p["clase"] not in CAJA and p["sem"] is not None]
    sube = sorted([p for p in inv if p["sem"] > 0], key=lambda p: -p["sem"])[:5]
    baja = sorted([p for p in inv if p["sem"] < 0], key=lambda p: p["sem"])[:5]
    top10 = [p for p in pos if p["clase"] not in CAJA][:10]

    frases = []
    if sem is not None:
        f = "En la semana el portafolio se movió %s" % pct(sem)
        if sem_usd is not None:
            f += " (%s)" % usd(sem_usd)
        if spy_sem is not None:
            f += ", frente a %s del S&P 500" % pct(spy_sem)
        frases.append(f + ".")
    frases.append("Vale %s y lleva una ganancia de %s (%s) sobre el capital aportado." % (usd(valor), usd(ganancia), pct(r_crea)))
    resumen = " ".join(frases)

    chips = []
    if sube:
        chips.append(('', "Mayor alza: %s %s" % (sube[0]["ticker"], pct(sube[0]["sem"]))))
    if baja:
        chips.append(('alerta', "Mayor caída: %s %s" % (baja[0]["ticker"], pct(baja[0]["sem"]))))
    if mayor:
        chips.append(('', "Mayor posición: %s %s" % (mayor, pct(mayor_peso, 1, False))))
    chips.append(('' if alerta_ef == "Dentro del rango" else 'alerta', "Efectivo %s (%s) · %s" % (usd(caja_val), pct(caja_pct, 1, False), alerta_ef.lower())))

    def kpi(lb, v, sp, t):
        return '<div class="kpi"><span class="lb">%s</span><span class="v %s">%s</span><span class="sp">%s</span></div>' % (E(lb), t, E(v), E(sp))

    def mov_rows(lst):
        return "".join('<tr><td class="t">%s</td><td>%s</td><td class="r num %s"><strong>%s</strong></td><td class="r num">%s</td></tr>'
                       % (E(p["ticker"]), E(p["nombre"]), tone(p["sem"]), pct(p["sem"]), usd(p["valor"])) for p in lst)

    mx = max([p["peso"] or 0 for p in top10] + [0.0001])
    top_rows = "".join(
        '<tr><td class="t">%s</td><td>%s<div class="nota">%s</div></td><td class="r num">%s</td>'
        '<td class="r"><div class="peso"><b style="width:%.0fpx"></b><span class="num">%s</span></div></td>'
        '<td class="r num %s">%s</td><td class="r num %s">%s</td></tr>'
        % (E(p["ticker"]), E(p["nombre"]), E(p["cuentas"]), usd(p["valor"]), 4 + 76 * (p["peso"] or 0) / mx, pct(p["peso"], 1, False),
           tone(p["pg_pct"]), pct(p["pg_pct"]), tone(p["sem"]), pct(p["sem"])) for p in top10)

    top_rows += ('<tr class="caja"><td class="t">Efectivo</td><td>Efectivo total<div class="nota">USD, USDT, SGOV y BIL (remunerado y no remunerado)</div></td>'
                 '<td class="r num">%s</td><td class="r num"><strong>%s</strong></td><td class="r num">–</td><td class="r num">–</td></tr>' % (usd(caja_val), pct(caja_pct, 1, False)))
    movers = sorted(sube + baja, key=lambda p: -p["sem"])
    hp = [h for h in hist if h["valor"] is not None]

    S = []
    S.append('<title>Reporte Portafolio Cañas</title><meta name="claude:viewport-fit-sides" content="cover">')
    S.append('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@600;800;900&family=Inter:wght@400;500;600;700&display=swap">')
    S.append("<style>%s</style>" % CSS)
    # Portada
    S.append('<section class="sec os"><div class="in">'
             '<div class="eyebrow">Trust Kapital · Portafolio familiar</div>'
             '<div class="hero-top"><div><h1>Reporte semanal.</h1><p class="sub" style="margin-top:10px">Semana al %s · cifras en USD</p></div>'
             '<div style="text-align:right"><div class="valor">%s</div><div class="sub num">%s</div></div></div>'
             '<div class="kpis">%s%s%s%s</div></div></section>'
             % (E(fecha), usd(valor), cop(vcop),
                kpi("Semana", pct(sem), "S&P 500 " + pct(spy_sem), tone(sem)),
                kpi("Desde la creación", pct(r_crea), "S&P 500 " + pct(spy_crea), tone(r_crea)),
                kpi("Año corrido", pct(r_ytd), "S&P 500 " + pct(spy_ytd), tone(r_ytd)),
                kpi("Ganancia total", usd(ganancia), "Capital aportado " + usd(capital), tone(ganancia))))
    # Resumen
    S.append('<section class="sec"><div class="in"><div class="eyebrow">Resumen</div><h2>Cómo fue la semana.</h2>'
             '<p style="font-size:1.08rem">%s</p>%s<ul class="chips">%s</ul></div></section>'
             % (E(resumen), ('<p class="sub" style="font-size:1.02rem">%s</p>' % E(comentario)) if comentario else "",
                "".join('<li class="chip %s">%s</li>' % (c, E(t)) for c, t in chips)))
    # Movimientos
    if movers:
        S.append('<section class="sec alt"><div class="in"><div class="eyebrow">Movimientos</div><h2>Lo que más se movió.</h2>'
                 '<div class="cols"><div class="tw"><table><tr><th>Ticker</th><th>Nombre</th><th class="r">Semana</th><th class="r">Valor</th></tr>%s%s</table></div>'
                 '<div class="card">%s</div></div>'
                 '<p class="nota">Cambio de precio en los últimos cinco días de mercado. No incluye el efectivo.</p></div></section>'
                 % (mov_rows(sube), mov_rows(baja), svg_movers([(p["ticker"], p["sem"]) for p in movers])))
    # vs S&P
    S.append('<section class="sec"><div class="in"><div class="eyebrow">Comparación</div><h2>Frente al S&amp;P 500.</h2>'
             '<div class="card"><div class="key"><span><i style="background:%s"></i>Portafolio</span><span><i style="background:%s"></i>S&amp;P 500</span></div>%s</div>'
             '<p class="nota">La rentabilidad del portafolio se mide sobre el capital aportado. El S&amp;P 500 se mide desde la fecha de creación del portafolio y desde el 1 de enero.</p></div></section>'
             % (INDIGO, PLATA, svg_vs(["Semana", "Desde la creación", "Año corrido"], [sem, r_crea, r_ytd], [spy_sem, spy_crea, spy_ytd])))
    # Distribución
    S.append('<section class="sec alt"><div class="in"><div class="eyebrow">Distribución</div><h2>Cómo está repartido.</h2>'
             '<div class="cols2"><div class="card"><h3>Por clase de activo</h3><div style="margin-top:16px">%s</div></div>'
             '<div class="card"><h3>Por cuenta</h3><div style="margin-top:16px">%s</div></div></div></div></section>'
             % (stacked([(c[0], c[1], SERIE[i % len(SERIE)], "") for i, c in enumerate(clases)]),
                stacked([(c[0], c[2], SERIE[i % len(SERIE)], c[1]) for i, c in enumerate(cuentas)])))
    # Evolución
    if len(hp) >= 2:
        evo = ('<div class="card"><div class="key"><span><i style="background:%s"></i>Valor del portafolio</span>'
               '<span><i style="background:%s"></i>Capital aportado</span></div>%s</div>' % (INDIGO, TINTA_SUAVE, svg_line(hp)))
    else:
        evo = '<p class="sub">La gráfica de evolución empieza a llenarse con la segunda foto semanal.</p>'
    S.append('<section class="sec"><div class="in"><div class="eyebrow">Evolución</div><h2>Valor frente a capital aportado.</h2>%s</div></section>' % evo)
    # Top 10
    S.append('<section class="sec alt"><div class="in"><div class="eyebrow">Posiciones</div><h2>Las 10 más grandes.</h2><p class="sub">Sin contar el efectivo, que va totalizado al final.</p>'
             '<div class="tw"><table><tr><th>Ticker</th><th>Nombre y cuentas</th><th class="r">Valor</th><th class="r">Peso</th><th class="r">P/G</th><th class="r">Semana</th></tr>%s</table></div></div></section>'
             % top_rows)
    # Riesgo
    def tile(lb, v, d, m=None):
        meter = '<div class="meter"><b style="width:%.0f%%"></b></div>' % (min(100, max(0, m * 100))) if m is not None else ""
        return '<div class="tile"><span class="lb">%s</span><span class="v">%s</span>%s<span class="d">%s</span></div>' % (E(lb), E(v), meter, E(d))
    beta_txt = ("%.2f" % beta).replace(".", ",") if beta is not None else "–"
    S.append('<section class="sec os"><div class="in"><div class="eyebrow">Riesgo</div><h2>Riesgo y concentración.</h2><div class="tiles">%s%s%s%s</div>'
             '<div><h3 style="margin-bottom:12px">Posiciones con caída fuerte frente a su costo</h3><p class="%s">%s</p></div>'
             '<p class="nota">Volatilidad y beta calculadas con precios diarios de los últimos 12 meses y los pesos actuales. El efectivo incluye SGOV, BIL y USDT.</p></div></section>'
             % (tile("Volatilidad anual", pct(vol, 1, False), "Cuánto se mueve el portafolio en un año típico", min(1, (vol or 0) / 0.6)),
                tile("Beta vs S&P 500", beta_txt, "1,00 = se mueve igual que el mercado", min(1, (beta or 0) / 2)),
                tile("5 mayores posiciones", pct(top5, 1, False), "Mayor: %s (%s)" % (mayor, pct(mayor_peso, 1, False)), top5),
                tile("Efectivo total", usd(caja_val), "%s del portafolio. USD, USDT, SGOV y BIL. %s." % (pct(caja_pct, 1, False), alerta_ef), caja_pct),
                "neg" if caidas != "Ninguna" else "sub", E(caidas)))
    # Pie
    archivo = "".join('<li><a href="semanas/%s.html">%s</a></li>' % (iso(h["fecha"]), E(h["fecha"])) for h in reversed(hist))
    S.append('<section class="sec pie"><div class="in" style="gap:16px">'
             '<p><a href="%s">Abrir el Google Sheet del portafolio</a> para ver el detalle de cuentas y transacciones.</p>'
             '%s<p class="nota" style="color:rgba(255,255,255,.55)">Generado automáticamente con precios de Google Finance. Trust Kapital · Gardens Capital.</p></div></section>'
             % (SHEET_URL, ('<div><div class="eyebrow" style="margin-bottom:10px">Reportes anteriores</div><ul class="archivo">%s</ul></div>' % archivo) if archivo else ""))
    datos_correo = dict(fecha=fecha, valor=valor, vcop=vcop, sem=sem, spy_sem=spy_sem, r_crea=r_crea, spy_crea=spy_crea,
                        r_ytd=r_ytd, ganancia=ganancia, caja_val=caja_val, caja_pct=caja_pct, resumen=resumen, comentario=comentario,
                        sube=sube[0] if sube else None, baja=baja[0] if baja else None, caidas=caidas)
    return "".join(S), resumen, datos_correo


def correo(c):
    """Correo corto. Gmail borra los fondos con 'background:', por eso se usan
    tablas con bgcolor y background-color, y el link al reporte va primero."""
    F = "font-family:Arial,Helvetica,sans-serif;"
    def boton(txt):
        return ('<table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>'
                '<td bgcolor="#575da1" style="background-color:#575da1;border-radius:7px;padding:14px 24px">'
                '<a href="%s" style="%scolor:#ffffff;text-decoration:none;font-size:16px;font-weight:bold;display:inline-block">%s</a>'
                '</td></tr></table>') % (REPORTE_URL, F, E(txt))
    def kpi(lb, v, sub, t):
        col = {"pos": "#2f7d55", "neg": "#b4473d"}.get(t, "#16171a")
        return ('<td width="50%%" valign="top" style="padding:14px 20px;border-top:1px solid #e3e5ea">'
                '<div style="%sfont-size:11px;font-weight:bold;letter-spacing:2px;text-transform:uppercase;color:#5b606b">%s</div>'
                '<div style="%sfont-size:24px;font-weight:bold;color:%s;margin-top:4px">%s</div>'
                '<div style="%sfont-size:13px;color:#5b606b;margin-top:2px">%s</div></td>') % (F, E(lb), F, col, E(v), F, E(sub))
    mov = []
    if c["sube"]:
        mov.append("Mayor alza: %s %s" % (c["sube"]["ticker"], pct(c["sube"]["sem"])))
    if c["baja"]:
        mov.append("Mayor caída: %s %s" % (c["baja"]["ticker"], pct(c["baja"]["sem"])))
    return (
        '<table role="presentation" width="100%%" cellpadding="0" cellspacing="0" border="0" bgcolor="#f6f7f9" style="background-color:#f6f7f9"><tr><td align="center" style="padding:20px 10px">'
        '<table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" bgcolor="#ffffff" style="background-color:#ffffff;max-width:600px;width:100%%;border:1px solid #e3e5ea">'
        # 1. Link al reporte, lo primero
        '<tr><td style="padding:20px 24px 22px">'
        '<div style="%sfont-size:15px;color:#16171a;margin-bottom:14px">Ya está listo el reporte semanal del portafolio.</div>%s'
        '<div style="%sfont-size:12px;color:#5b606b;margin-top:10px">Si el botón no abre, usa este enlace: <a href="%s" style="color:#575da1">%s</a></div>'
        '</td></tr>'
        # 2. Encabezado oscuro con el valor
        '<tr><td bgcolor="#0e0f12" style="background-color:#0e0f12;padding:24px;margin-top:16px">'
        '<div style="%sfont-size:11px;font-weight:bold;letter-spacing:3px;text-transform:uppercase;color:#6cbddf">Trust Kapital · Portafolio familiar</div>'
        '<div style="%sfont-size:13px;color:#c9ccd3;margin-top:8px">Semana al %s · cifras en USD</div>'
        '<div style="%sfont-size:38px;font-weight:bold;color:#ffffff;margin-top:10px">%s</div>'
        '<div style="%sfont-size:13px;color:#c9ccd3">%s</div></td></tr>'
        # 3. Indicadores
        '<tr><td><table role="presentation" width="100%%" cellpadding="0" cellspacing="0" border="0"><tr>%s%s</tr><tr>%s%s</tr></table></td></tr>'
        # 4. Resumen
        '<tr><td style="padding:12px 24px 0;%sfont-size:15px;line-height:1.6;color:#16171a">%s</td></tr>'
        '<tr><td style="padding:8px 24px 0;%sfont-size:14px;line-height:1.6;color:#5b606b">%s</td></tr>'
        '<tr><td style="padding:20px 24px 24px">%s'
        '<div style="%sfont-size:13px;color:#5b606b;margin-top:16px">Detalle de cuentas y transacciones: <a href="%s" style="color:#575da1">Google Sheet del portafolio</a></div></td></tr>'
        '</table>'
        '<div style="%sfont-size:11px;color:#8a8f99;margin-top:12px">Generado automáticamente con precios de Google Finance. Trust Kapital · Gardens Capital.</div>'
        '</td></tr></table>'
    ) % (F, boton("Abrir el reporte completo"), F, REPORTE_URL, REPORTE_URL,
         F, F, E(c["fecha"]), F, usd(c["valor"]), F, cop(c["vcop"]),
         kpi("Semana", pct(c["sem"]), "S&P 500 " + pct(c["spy_sem"]), tone(c["sem"])),
         kpi("Desde la creación", pct(c["r_crea"]), "S&P 500 " + pct(c["spy_crea"]), tone(c["r_crea"])),
         kpi("Año corrido", pct(c["r_ytd"]), "Ganancia total " + usd(c["ganancia"]), tone(c["r_ytd"])),
         kpi("Efectivo total", usd(c["caja_val"]), pct(c["caja_pct"], 1, False) + " del portafolio", ""),
         F, E(c["resumen"]), F, E(" · ".join(mov)), boton("Ver reporte de la semana"), F, SHEET_URL, F)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("datos")
    ap.add_argument("--out", default="out")
    a = ap.parse_args()
    rep, pos, clases, cuentas, hist, com = load(a.datos)
    page, resumen, dc = build(rep, pos, clases, cuentas, hist, com)
    open(os.path.join(a.out, "correo.html"), "w", encoding="utf-8").write(correo(dc))
    os.makedirs(os.path.join(a.out, "semanas"), exist_ok=True)
    semana = iso(rep.get("Fecha del reporte", ""))
    head = ('<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
            '<meta name="robots" content="noindex,nofollow"></head><body style="margin:0">')
    open(os.path.join(a.out, "index.html"), "w", encoding="utf-8").write(head + page + "</body></html>")
    full = head + page.replace('href="semanas/', 'href="') + "</body></html>"
    open(os.path.join(a.out, "semanas", semana + ".html"), "w", encoding="utf-8").write(full)
    print("OK", semana, len(page))
    print("RESUMEN:", resumen)


if __name__ == "__main__":
    main()
