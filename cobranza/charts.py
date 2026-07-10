"""Motor de gráficas propio (§9): barras HTML/CSS e SVG inline. Sin librerías
de gráficas por CDN. Devuelven HTML que se renderiza con st.markdown."""
from __future__ import annotations

import html

from .theme import CANAL_COLOR, INK70, LINE, GRAY

FILL = {"Llamada": "fill-llamada", "IVR": "fill-ivr", "SMS": "fill-sms", "Espontaneo": "fill-espontaneo"}


def fill_class(canal: str) -> str:
    return FILL.get(canal, "fill-espontaneo")


def channel_tag(canal: str) -> str:
    color = CANAL_COLOR.get(canal, GRAY)
    label = "Espontáneo" if canal == "Espontaneo" else canal
    return f'<span class="tag"><span class="dot" style="background:{color}"></span>{html.escape(label)}</span>'


def bar_list(items: list[dict], max_value: float | None = None) -> str:
    """items = [{label, value, fill, right}]. Devuelve HTML de bar-rows."""
    top = max_value if max_value else max([1.0] + [i["value"] for i in items])
    rows = []
    for it in items:
        w = max(1.5, (it["value"] / top) * 100) if top else 1.5
        rows.append(
            f'<div class="bar-row"><div style="color:{INK70};font-size:.85rem">{html.escape(str(it["label"]))}</div>'
            f'<div class="bar-track"><div class="bar-fill {it.get("fill", "fill-espontaneo")}" style="width:{w:.1f}%"></div></div>'
            f'<div class="num" style="font-size:.85rem;font-weight:500;text-align:right;white-space:nowrap">{html.escape(str(it["right"]))}</div></div>'
        )
    return '<div class="panel">' + "".join(rows) + "</div>"


def column_chart(data: list[dict], height: int = 220, fmt=lambda n: str(int(n))) -> str:
    """Columnas SVG por día. data = [{label, value, highlight?, muted?}]."""
    if not data:
        return '<div style="color:#5A6472;font-size:.85rem">Sin datos.</div>'
    w = max(560, len(data) * 26)
    pad_t, pad_b, pad_l, pad_r = 12, 40, 8, 8
    mx = max([1.0] + [d["value"] for d in data])
    inner_h = height - pad_t - pad_b
    bw = (w - pad_l - pad_r) / len(data)
    step = max(1, len(data) // 12)
    parts = [f'<svg width="{w}" height="{height}" role="img">']
    for i, d in enumerate(data):
        h = (d["value"] / mx) * inner_h
        x = pad_l + i * bw
        y = pad_t + inner_h - h
        color = "#12A99A" if d.get("highlight") else "#c9cfd8" if d.get("muted") else "#B77E17"
        op = "0.6" if d.get("muted") else "1"
        parts.append(f'<rect x="{x + 2:.1f}" y="{y:.1f}" width="{max(2, bw - 4):.1f}" height="{h:.1f}" fill="{color}" rx="2" opacity="{op}"/>')
        if i % step == 0:
            cx = x + bw / 2
            parts.append(f'<text x="{cx:.1f}" y="{height - 22}" text-anchor="middle" font-size="9" fill="#5A6472" transform="rotate(-40 {cx:.1f} {height - 22})">{html.escape(str(d["label"])[5:])}</text>')
    parts.append(f'<text x="{pad_l}" y="{height - 6}" font-size="10" fill="#8A94A3">máx {html.escape(fmt(mx))}</text></svg>')
    return f'<div style="overflow-x:auto">' + "".join(parts) + "</div>"


def line_chart(labels: list[str], series: list[dict], height: int = 240, fmt=lambda n: str(int(n))) -> str:
    """Líneas multi-serie SVG. series = [{nombre, color, puntos}]."""
    if not labels:
        return '<div style="color:#5A6472;font-size:.85rem">Sin campañas para comparar.</div>'
    w = max(520, len(labels) * 120)
    pad_t, pad_b, pad_l, pad_r = 16, 34, 48, 16
    inner_w = w - pad_l - pad_r
    inner_h = height - pad_t - pad_b
    allv = [v for s in series for v in s["puntos"]]
    mx = max([1.0] + allv)
    mn = min([0.0] + allv)
    n = len(labels)

    def X(i):
        return pad_l + (inner_w / 2 if n == 1 else (i / (n - 1)) * inner_w)

    def Y(v):
        return pad_t + inner_h - ((v - mn) / (mx - mn or 1)) * inner_h

    parts = [f'<svg width="{w}" height="{height}" role="img">']
    for f in (0, 0.5, 1):
        val = mn + (mx - mn) * f
        yy = Y(val)
        parts.append(f'<line x1="{pad_l}" y1="{yy:.1f}" x2="{w - pad_r}" y2="{yy:.1f}" stroke="{LINE}" stroke-width="1"/>')
        parts.append(f'<text x="4" y="{yy + 3:.1f}" font-size="9" fill="#8A94A3">{html.escape(fmt(val))}</text>')
    for s in series:
        d = " ".join(f'{"M" if i == 0 else "L"} {X(i):.1f} {Y(v):.1f}' for i, v in enumerate(s["puntos"]))
        parts.append(f'<path d="{d}" fill="none" stroke="{s["color"]}" stroke-width="2"/>')
        for i, v in enumerate(s["puntos"]):
            parts.append(f'<circle cx="{X(i):.1f}" cy="{Y(v):.1f}" r="3" fill="{s["color"]}"/>')
    for i, l in enumerate(labels):
        parts.append(f'<text x="{X(i):.1f}" y="{height - 12}" text-anchor="middle" font-size="10" fill="#5A6472">{html.escape(str(l))}</text>')
    parts.append("</svg>")
    legend = "".join(
        f'<span class="tag"><span class="dot" style="background:{s["color"]}"></span>{html.escape(s["nombre"])}</span>'
        for s in series
    )
    return f'<div style="overflow-x:auto">' + "".join(parts) + f'</div><div style="display:flex;gap:12px;margin-top:8px">{legend}</div>'


def quadrant_chart(agentes: list[dict], sel: str | None = None) -> str:
    """Cuadrante contacto × cumplimiento (SVG). agentes = dicts de metrics."""
    if not agentes:
        return ""
    w, h, pad = 460, 320, 34
    contactos = sorted(a["tasa_contacto"] for a in agentes)
    cumpl = sorted(a["pct_cumplimiento"] for a in agentes)

    def med(xs):
        n = len(xs)
        return 0 if not n else (xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2)

    med_c, med_k = med(contactos), med(cumpl)
    max_c = max([0.001] + [a["tasa_contacto"] for a in agentes])
    max_k = max([0.001] + [a["pct_cumplimiento"] for a in agentes])
    color = {"MENTOR": "#12A99A", "COACHING_CIERRE": "#B77E17", "SUBIR_VOLUMEN": "#2b5c9a", "PLAN_MEJORA": "#D6486A"}

    def X(v):
        return pad + (v / max_c) * (w - pad * 2)

    def Y(v):
        return h - pad - (v / max_k) * (h - pad * 2)

    p = [f'<svg width="{w}" height="{h}" role="img">']
    p.append(f'<line x1="{X(med_c):.0f}" y1="{pad}" x2="{X(med_c):.0f}" y2="{h - pad}" stroke="{LINE}" stroke-dasharray="4 4"/>')
    p.append(f'<line x1="{pad}" y1="{Y(med_k):.0f}" x2="{w - pad}" y2="{Y(med_k):.0f}" stroke="{LINE}" stroke-dasharray="4 4"/>')
    p.append(f'<text x="{w - pad}" y="{pad - 6}" text-anchor="end" font-size="9" fill="#12A99A">Mentor ↗</text>')
    p.append(f'<text x="{pad}" y="{h - pad + 14}" font-size="9" fill="#D6486A">Plan de mejora ↙</text>')
    p.append(f'<text x="{pad}" y="{pad - 6}" font-size="9" fill="#2b5c9a">Subir volumen ↖</text>')
    p.append(f'<text x="{w - pad}" y="{h - pad + 14}" text-anchor="end" font-size="9" fill="#B77E17">Coaching de cierre ↘</text>')
    for a in agentes:
        r = 7 if a["agente_id"] == sel else 5
        stroke = "#16202E" if a["agente_id"] == sel else "white"
        p.append(f'<circle cx="{X(a["tasa_contacto"]):.1f}" cy="{Y(a["pct_cumplimiento"]):.1f}" r="{r}" fill="{color.get(a["clasificacion"], GRAY)}" stroke="{stroke}" stroke-width="1"><title>{html.escape(str(a["nombre"]))}</title></circle>')
    p.append(f'<text x="{w / 2:.0f}" y="{h - 4}" text-anchor="middle" font-size="10" fill="#5A6472">Tasa de contacto →</text>')
    p.append(f'<text x="12" y="{h / 2:.0f}" font-size="10" fill="#5A6472" transform="rotate(-90 12 {h / 2:.0f})">Cumplimiento →</text></svg>')
    return f'<div style="overflow-x:auto" class="panel">' + "".join(p) + "</div>"
