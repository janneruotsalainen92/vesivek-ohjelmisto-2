from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPolygon
from shapely.geometry import mapping, shape

from vesivek.models import MeasurementResult

COLORS = {
    "asfaltti": "#4a4a4a",
    "laatta": "#c5c2b8",
    "sepeli": "#c4a574",
    "nurmikko": "#7cb342",
    "pensas": "#2e7d32",
    "multa": "#6d4c41",
    "tuntematon": "#ef6c00",
    "puu": "#1b5e20",
}


def write_png(result: MeasurementResult, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(11.5, 8.5), dpi=140)

    plot = result.site.plot
    if plot and plot.get("geometry"):
        _draw_geom(ax, plot["geometry"], facecolor="#f4f1ea", edgecolor="#8a8178", lw=1.1, ls="--", z=1, alpha=0.7)

    _draw_geom(
        ax,
        result.site.building["geometry"],
        facecolor="#d9d4cc",
        edgecolor="#1f1f1f",
        lw=1.8,
        z=3,
        alpha=0.95,
    )

    for rec in result.surfaces:
        if rec.geometry and rec.kind == "area" and rec.tyyppi in COLORS:
            _draw_geom(
                ax,
                rec.geometry,
                facecolor=COLORS[rec.tyyppi],
                edgecolor="#222",
                lw=0.6,
                z=4,
                alpha=0.72,
                hatch="///" if rec.luotettavuus in {"epavarma", "arvio", "esimerkki"} else None,
            )

    for edge in result.facade.edges:
        ax.plot(
            [edge.start[0], edge.end[0]],
            [edge.start[1], edge.end[1]],
            color="#c62828",
            linewidth=3.2,
            solid_capstyle="round",
            zorder=6,
            label="Valittu julkisivu (WFS)",
        )

    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("E (m), EPSG:3067")
    ax.set_ylabel("N (m), EPSG:3067")
    ax.grid(True, linestyle=":", alpha=0.35)
    ax.ticklabel_format(useOffset=False, style="plain")

    title = "Vesivek Ohjelma v1 — mitattu runko + yksi julkisivukaista"
    ax.set_title(title, loc="left", fontsize=12, pad=12, fontweight="bold")

    badge = _badge_text(result)
    ax.text(
        0.01,
        0.99,
        badge,
        transform=ax.transAxes,
        va="top",
        ha="left",
        fontsize=8,
        family="DejaVu Sans",
        bbox={"boxstyle": "round,pad=0.4", "facecolor": "#fff8e1", "edgecolor": "#f9a825", "alpha": 0.95},
        zorder=10,
    )

    handles, labels = ax.get_legend_handles_labels()
    seen: set[str] = set()
    legend_items = []
    for rec in result.surfaces:
        if rec.tyyppi in COLORS and rec.tyyppi not in seen and rec.kind in {"area", "linear"}:
            seen.add(rec.tyyppi)
            val = "—" if rec.value is None else f"{rec.value:.2f} {rec.unit}"
            legend_items.append((COLORS[rec.tyyppi], f"{rec.label_fi}: {val} [{rec.luotettavuus}]"))
    for color, text in legend_items:
        handles.append(plt.Line2D([0], [0], color=color, lw=6))
        labels.append(text)
    if handles:
        ax.legend(handles, labels, loc="lower right", fontsize=7, framealpha=0.92)

    _scale_bar(ax)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def _badge_text(result: MeasurementResult) -> str:
    site = result.site
    lock = "WFS-lukittu" if site.verified else "ESIMERKKI — ei tämän osoitteen virallisia metrejä"
    addr = site.matched_address or site.address_query
    width = (
        f"kaistan leveys {result.strip_width_m:.2f} m ({result.strip_width_source})"
        if result.strip_width_m
        else "kaistan leveys MITTAAMATTA"
    )
    lines = [
        f"{addr}",
        f"{site.crs} · {lock}",
        f"Lähde: {site.source_name}",
        f"{result.facade.label_fi}: {result.facade.length_m:.2f} m",
        width,
        "Salaojaa / sadevesiputkia EI piirretä (v1).",
    ]
    if result.warnings:
        lines.append("Huomiot: " + result.warnings[0][:140])
    return "\n".join(lines)


def _draw_geom(ax, geom, *, facecolor, edgecolor, lw, z, alpha, ls="-", hatch=None) -> None:
    gj = geom if isinstance(geom, dict) else mapping(geom)
    if gj.get("type") == "Polygon":
        rings = [gj["coordinates"][0]]
    elif gj.get("type") == "MultiPolygon":
        rings = [p[0] for p in gj["coordinates"]]
    else:
        shp = shape(gj) if isinstance(gj, dict) else geom
        if shp.geom_type == "Polygon":
            rings = [list(shp.exterior.coords)]
        elif shp.geom_type == "MultiPolygon":
            rings = [list(g.exterior.coords) for g in shp.geoms]
        else:
            return
    for ring in rings:
        xs = [p[0] for p in ring]
        ys = [p[1] for p in ring]
        patch = MplPolygon(
            list(zip(xs, ys)),
            closed=True,
            facecolor=facecolor,
            edgecolor=edgecolor,
            linewidth=lw,
            linestyle=ls,
            alpha=alpha,
            hatch=hatch,
            zorder=z,
        )
        ax.add_patch(patch)
        ax.plot(xs, ys, color=edgecolor, lw=lw, ls=ls, zorder=z + 1)


def _scale_bar(ax) -> None:
    xmin, xmax = ax.get_xlim()
    ymin, ymax = ax.get_ylim()
    span = xmax - xmin
    if span <= 0:
        return
    length = 5.0 if span < 40 else 10.0 if span < 80 else 20.0
    x0 = xmin + span * 0.06
    y0 = ymin + (ymax - ymin) * 0.06
    ax.plot([x0, x0 + length], [y0, y0], color="black", lw=3)
    ax.text(x0 + length / 2, y0 + (ymax - ymin) * 0.02, f"{length:.0f} m", ha="center", va="bottom", fontsize=8)
