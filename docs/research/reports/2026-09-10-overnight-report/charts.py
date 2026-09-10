"""SVG chart primitives. Every value is passed in; nothing is hardcoded here."""
from __future__ import annotations

INK = "#1a1a1a"; MUTED = "#6b6b6b"; GRID = "#e2e2e2"
SERIES = ["#2f5d8a", "#c2703d", "#5c8a5c", "#8a5c7a", "#8a8a3d"]


def _esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def grouped_bars(groups, series, values, *, ymax=None, width=760, height=300,
                 pad_l=54, pad_b=52, pad_t=16, fmt="{:.2f}", legend_cols=4):
    """groups: x labels. series: series names. values: {series: [v per group]}."""
    vals = [v for s in series for v in values.get(s, []) if v is not None]
    ymax = ymax or (max(vals) * 1.18 if vals else 1.0)
    legend_rows = -(-len(series) // legend_cols)
    height += (legend_rows - 1) * 18
    plot_w = width - pad_l - 16
    plot_h = height - pad_t - pad_b - (legend_rows * 18)
    gw = plot_w / max(len(groups), 1)
    bw = gw / (len(series) + 0.6)
    out = [f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" '
           f'font-family="Georgia,serif" font-size="10">']
    for i in range(5):
        y = pad_t + plot_h * i / 4
        v = ymax * (1 - i / 4)
        out.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{pad_l+plot_w}" y2="{y:.1f}" stroke="{GRID}"/>')
        out.append(f'<text x="{pad_l-6}" y="{y+3:.1f}" text-anchor="end" fill="{MUTED}">{v:.2f}</text>')
    for gi, g in enumerate(groups):
        gx = pad_l + gi * gw
        for si, s in enumerate(series):
            v = (values.get(s) or [None] * len(groups))[gi]
            if v is None:
                continue
            h = plot_h * (v / ymax) if ymax else 0
            x = gx + 0.3 * bw + si * bw
            y = pad_t + plot_h - h
            out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw*0.9:.1f}" height="{max(h,0.4):.1f}" '
                       f'fill="{SERIES[si % len(SERIES)]}"/>')
            if len(groups) * len(series) <= 30:
                out.append(f'<text x="{x+bw*0.45:.1f}" y="{y-3:.1f}" text-anchor="middle" '
                           f'fill="{MUTED}" font-size="8">{fmt.format(v)}</text>')
        out.append(f'<text x="{gx+gw/2:.1f}" y="{pad_t+plot_h+15:.1f}" text-anchor="middle" '
                   f'fill="{INK}">{_esc(g)}</text>')
    ly = pad_t + plot_h + 32
    for si, s in enumerate(series):
        col, row = si % legend_cols, si // legend_cols
        lx = pad_l + col * (plot_w / legend_cols)
        out.append(f'<rect x="{lx}" y="{ly+row*18-8}" width="9" height="9" fill="{SERIES[si%len(SERIES)]}"/>')
        out.append(f'<text x="{lx+13}" y="{ly+row*18}" fill="{INK}">{_esc(s)}</text>')
    out.append("</svg>")
    return "\n".join(out)


def slope(groups, left, right, *, left_name, right_name, width=760, height=300, fmt="{:.2f}"):
    """Paired before/after, one line per group. Shows the size of a reframing."""
    vals = [v for v in list(left) + list(right) if v is not None]
    ymax = max(vals) * 1.15 if vals else 1.0
    pad_l, pad_t, pad_b = 54, 20, 46
    plot_h = height - pad_t - pad_b
    xl, xr = pad_l + 90, width - 150
    out = [f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" '
           f'font-family="Georgia,serif" font-size="10">']
    for i in range(5):
        y = pad_t + plot_h * i / 4
        out.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{width-16}" y2="{y:.1f}" stroke="{GRID}"/>')
        out.append(f'<text x="{pad_l-6}" y="{y+3:.1f}" text-anchor="end" fill="{MUTED}">'
                   f'{ymax*(1-i/4):.2f}</text>')
    # Nudge labels apart when two lines land within a line-height of each other,
    # so a tie does not render as one unreadable smudge.
    def _declutter(ys):
        order = sorted(range(len(ys)), key=lambda i: ys[i] if ys[i] is not None else 1e9)
        out = list(ys)
        last = None
        for i in order:
            if out[i] is None:
                continue
            if last is not None and out[i] - last < 11:
                out[i] = last + 11
            last = out[i]
        return out

    raw_a = [pad_t + plot_h * (1 - v / ymax) if v is not None else None for v in left]
    raw_b = [pad_t + plot_h * (1 - v / ymax) if v is not None else None for v in right]
    lab_a, lab_b = _declutter(raw_a), _declutter(raw_b)

    for i, g in enumerate(groups):
        a, b = left[i], right[i]
        if a is None or b is None:
            continue
        ya, yb = raw_a[i], raw_b[i]
        c = SERIES[i % len(SERIES)]
        out.append(f'<line x1="{xl}" y1="{ya:.1f}" x2="{xr}" y2="{yb:.1f}" stroke="{c}" stroke-width="2"/>')
        out.append(f'<circle cx="{xl}" cy="{ya:.1f}" r="3.5" fill="{c}"/>')
        out.append(f'<circle cx="{xr}" cy="{yb:.1f}" r="3.5" fill="{c}"/>')
        out.append(f'<text x="{xl-8}" y="{lab_a[i]+3:.1f}" text-anchor="end" fill="{c}">'
                   f'{_esc(g)} {fmt.format(a)}</text>')
        out.append(f'<text x="{xr+8}" y="{lab_b[i]+3:.1f}" fill="{c}">{fmt.format(b)}</text>')
    out.append(f'<text x="{xl}" y="{height-16}" text-anchor="middle" fill="{INK}">{_esc(left_name)}</text>')
    out.append(f'<text x="{xr}" y="{height-16}" text-anchor="middle" fill="{INK}">{_esc(right_name)}</text>')
    out.append("</svg>")
    return "\n".join(out)


def stacked(rows, series, *, width=760, height=190, fmt="{:.0f}"):
    """rows: [(label, {series: value})] — horizontal 100% stacked bars."""
    pad_l, pad_t, bar_h, gap = 130, 14, 30, 18
    height = pad_t + len(rows) * (bar_h + gap) + 34
    plot_w = width - pad_l - 20
    out = [f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" '
           f'font-family="Georgia,serif" font-size="10">']
    for ri, (label, cells) in enumerate(rows):
        total = sum(v for v in cells.values() if v) or 1
        y = pad_t + ri * (bar_h + gap)
        x = pad_l
        out.append(f'<text x="{pad_l-8}" y="{y+bar_h/2+4}" text-anchor="end" fill="{INK}">{_esc(label)}</text>')
        for si, s in enumerate(series):
            v = cells.get(s) or 0
            w = plot_w * v / total
            if w <= 0:
                continue
            out.append(f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="{bar_h}" '
                       f'fill="{SERIES[si%len(SERIES)]}"/>')
            if w > 26:
                out.append(f'<text x="{x+w/2:.1f}" y="{y+bar_h/2+4}" text-anchor="middle" '
                           f'fill="#fff" font-size="9">{fmt.format(v)}</text>')
            x += w
    ly = pad_t + len(rows) * (bar_h + gap) + 12
    for si, s in enumerate(series):
        lx = pad_l + si * (plot_w / max(len(series), 1))
        out.append(f'<rect x="{lx}" y="{ly-8}" width="9" height="9" fill="{SERIES[si%len(SERIES)]}"/>')
        out.append(f'<text x="{lx+13}" y="{ly}" fill="{INK}">{_esc(s)}</text>')
    out.append("</svg>")
    return "\n".join(out)
