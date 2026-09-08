from __future__ import annotations

from io import BytesIO
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Polygon as MplPolygon
from PIL import Image
from shapely.geometry import mapping, shape

from vesivek.models import MeasurementResult

COLORS = {
    "asfaltti": "#4a4a4a",
    "laatta": "#c5c2b8",
    "sepeli": "#e0c36a",
    "nurmikko": "#7cb342",
    "pensas": "#2e7d32",
    "rajapuska": "#1b5e20",
    "seinänvierus": "#6d4c41",
    "päätylaatta": "#c62828",
    "multa": "#5d4037",
    "tuntematon": "#ef6c00",
    "puu": "#1b5e20",
    "kaista": "#90caf9",
}


def write_png(result: MeasurementResult, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(12.2, 9.0), dpi=140)

    if result.ortho_bytes and result.ortho_bbox:
        try:
            im = Image.open(BytesIO(result.ortho_bytes)).convert("RGB")
            arr = np.asarray(im)
            minx, miny, maxx, maxy = result.ortho_bbox
            ax.imshow(arr, extent=(minx, maxx, miny, maxy), origin="upper", zorder=0)
        except Exception:
            pass

    plot = result.site.plot
    if plot and plot.get("geometry"):
        _draw_geom(ax, plot["geometry"], facecolor="#f4f1ea", edgecolor="#1565c0", lw=1.3, ls="--", z=1, alpha=0.18)

    if result.strip and result.strip.geometry:
        _draw_geom(
            ax,
            result.strip.geometry,
            facecolor="#bbdefb",
            edgecolor="#0d47a1",
            lw=1.0,
            z=2,
            alpha=0.18,
            ls="-",
        )

    _draw_geom(
        ax,
        result.site.building["geometry"],
        facecolor="#d7ccc8",
        edgecolor="#1f1f1f",
        lw=1.8,
        z=3,
        alpha=0.92,
    )

    for rec in result.surfaces:
        if rec.geometry and rec.kind == "area" and rec.tyyppi in COLORS:
            hatch = None
            ls = "-"
            if rec.lock_tila in {"pre_lock", "ei_varmennettu", "arvio", "ei_laskettu"} or rec.luotettavuus in {
                "epavarma",
                "arvio",
                "esimerkki",
                "ei_varmennettu",
                "pre_lock",
            } or rec.value is None:
                hatch = "///"
                ls = "--"
            _draw_geom(
                ax,
                rec.geometry,
                facecolor=COLORS[rec.tyyppi],
                edgecolor="#222",
                lw=0.7,
                z=4,
                alpha=0.62,
                hatch=hatch,
                ls=ls,
            )

    for edge in result.facade.edges:
        ax.plot(
            [edge.start[0], edge.end[0]],
            [edge.start[1], edge.end[1]],
            color="#c62828",
            linewidth=3.0,
            solid_capstyle="round",
            zorder=6,
            label="Valittu julkisivu (WFS)",
        )

    if result.mittaviivat:
        for tick in result.qc_ticks:
            color = (
                "#1565c0"
                if tick.kind == "seina-raja"
                else "#6a1b9a"
                if tick.kind == "tyokaista"
                else "#455a64"
            )
            ax.plot(
                [tick.start[0], tick.end[0]],
                [tick.start[1], tick.end[1]],
                color=color,
                linewidth=0.7 if tick.kind == "tikku-1m" else 1.15,
                zorder=7,
            )
            if tick.kind in {"seina-raja", "tyokaista"}:
                mx = (tick.start[0] + tick.end[0]) / 2
                my = (tick.start[1] + tick.end[1]) / 2
                ax.text(mx, my, tick.id, fontsize=5.5, color=color, zorder=8)

    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("E (m), EPSG:3067")
    ax.set_ylabel("N (m), EPSG:3067")
    ax.grid(True, linestyle=":", alpha=0.28)
    ax.ticklabel_format(useOffset=False, style="plain")

    ax.set_title(
        "Vesivek Ohjelma bot-kokeilu — kaista (seinä → reuna) + FM-007-pinnat",
        loc="left",
        fontsize=11,
        pad=12,
        fontweight="bold",
    )

    ax.text(
        0.01,
        0.99,
        _badge_text(result),
        transform=ax.transAxes,
        va="top",
        ha="left",
        fontsize=7.5,
        family="DejaVu Sans",
        bbox={"boxstyle": "round,pad=0.4", "facecolor": "#fff8e1", "edgecolor": "#f9a825", "alpha": 0.93},
        zorder=10,
    )

    handles, labels = ax.get_legend_handles_labels()
    seen: set[str] = set()
    legend_items = []
    for rec in result.surfaces:
        if rec.tyyppi in COLORS and rec.tyyppi not in seen and rec.kind in {"area", "linear"}:
            seen.add(rec.tyyppi)
            if rec.kind == "area":
                val = "EI LASKETTU" if rec.value is None else f"{rec.value:.2f} m²"
            else:
                val = "—" if rec.value is None else f"{rec.value:.2f} {rec.unit}"
            extra = (
                " EI VARMENNETTU"
                if rec.luotettavuus == "ei_varmennettu"
                else f" [{rec.lock_tila}]"
            )
            legend_items.append((COLORS[rec.tyyppi], f"{rec.label_fi}: {val}{extra}"))
    for color, text in legend_items:
        handles.append(plt.Line2D([0], [0], color=color, lw=6))
        labels.append(text)
    if handles:
        ax.legend(handles, labels, loc="lower right", fontsize=6.5, framealpha=0.92)

    _north_arrow(ax)
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
        else "kaistan leveys MITTAAMATTA → m² = EI LASKETTU"
    )
    clip = result.strip.clip if result.strip else "—"
    lines = [
        f"{addr}",
        f"{site.crs} · {lock}",
        f"Lähde: {site.source_name}",
        f"{result.facade.label_fi}: {result.facade.length_m:.2f} m",
        width,
        f"clip={clip} · tontti={'kyllä' if site.plot else 'ei'} · orto={'kyllä' if result.ortho_bytes else 'ei'} · vaihe={result.tyovaihe}",
        "Salaojaa / sadevesiputkia EI piirretä.",
        f"Dual: {result.strip.dual_status if result.strip else '—'}",
    ]
    if result.occlusion or result.occlusion_note:
        lines.append("EI VARMENNETTU: " + (result.occlusion_note or "peite"))
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


def _north_arrow(ax) -> None:
    xmin, xmax = ax.get_xlim()
    ymin, ymax = ax.get_ylim()
    x = xmax - (xmax - xmin) * 0.06
    y = ymax - (ymax - ymin) * 0.10
    ax.annotate(
        "N",
        xy=(x, y),
        xytext=(x, y - (ymax - ymin) * 0.08),
        ha="center",
        arrowprops={"arrowstyle": "-|>", "color": "black", "lw": 1.4},
        fontsize=9,
        fontweight="bold",
        zorder=12,
    )
