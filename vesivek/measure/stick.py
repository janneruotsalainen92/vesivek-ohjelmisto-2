from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from vesivek.config import DEFAULT_STICK_M
from vesivek.models import StickResult


def detect_stick(photos: list[Path], length_m: float = DEFAULT_STICK_M) -> StickResult:
    """Find a long high-chroma rod (yellow/red/orange mittatikku) if present."""
    length_m = float(length_m or DEFAULT_STICK_M)
    if length_m <= 0:
        raise ValueError("Mittatikun pituuden on oltava > 0 m.")

    best: tuple[float, Path, float] | None = None  # score, path, length_px
    for path in photos:
        px = _stick_length_px(path)
        if px is None:
            continue
        score = px
        if best is None or score > best[0]:
            best = (score, path, px)

    if best is None:
        return StickResult(
            found=False,
            length_m=length_m,
            length_px=None,
            pixels_per_m=None,
            image=None,
            huomio=(
                f"Mittatikkua ({length_m:.2f} m) ei tunnistettu kuvista. "
                "Kaistan leveyttä ei arvata — pinta-alat jäävät epävarmoiksi ilman --kaistan-leveys."
            ),
        )

    _, path, px = best
    ppm = px / length_m
    return StickResult(
        found=True,
        length_m=length_m,
        length_px=px,
        pixels_per_m=ppm,
        image=path,
        huomio=(
            f"Mittatikku tunnistettu kuvasta {path.name}: {px:.0f} px ≈ {length_m:.2f} m "
            f"({ppm:.1f} px/m). Mittakaava on valokuvakohtainen arvio."
        ),
    )


def estimate_strip_width_m(photos: list[Path], stick: StickResult) -> tuple[float | None, str]:
    """Rough perpendicular ground-band width from the photo that has the stick."""
    if not stick.found or not stick.pixels_per_m or stick.image is None:
        return None, "Leveys puuttuu (ei mittatikkua)."
    try:
        with Image.open(stick.image) as im:
            im = im.convert("RGB")
            arr = np.asarray(im, dtype=np.uint8)
    except OSError:
        return None, "Mittatikkukuvaa ei voitu lukea leveysarvioon."

    h = arr.shape[0]
    # Ground band: lower 35–70 % of the frame, typical for a facade-side snapshot.
    band_px = h * 0.28
    width_m = band_px / stick.pixels_per_m
    # Clamp to a plausible strip; still marked as photo estimate.
    width_m = float(min(max(width_m, 0.3), 8.0))
    return width_m, (
        f"Kaistan leveys {width_m:.2f} m on arvio mittatikun mittakaavasta "
        f"({stick.image.name}), ei WFS-lukittu mitta."
    )


def _stick_length_px(path: Path) -> float | None:
    try:
        with Image.open(path) as im:
            im = im.convert("RGB")
            im.thumbnail((1400, 1400))
            arr = np.asarray(im, dtype=np.uint8)
    except OSError:
        return None

    hsv_like = _rgb_hsv_sv(arr)
    h, s, v = hsv_like
    chroma = (s > 90) & (v > 70)
    warm = ((h < 45) | (h > 330) | ((h > 35) & (h < 75))) & chroma
    if int(warm.sum()) < 80:
        return None

    ys, xs = np.where(warm)
    if len(xs) < 80:
        return None
    # Principal-axis length of the warm mask.
    pts = np.stack([xs.astype(np.float64), ys.astype(np.float64)], axis=1)
    pts -= pts.mean(axis=0)
    cov = np.cov(pts, rowvar=False)
    if not np.isfinite(cov).all() or cov.shape != (2, 2):
        return None
    evals, evecs = np.linalg.eigh(cov)
    axis = evecs[:, int(np.argmax(evals))]
    proj = pts @ axis
    length = float(proj.max() - proj.min())
    aspect = length / max(float(np.sqrt(evals.min() * 12 + 1e-6)), 1.0)
    if length < 60 or aspect < 3.5:
        return None
    return length


def _rgb_hsv_sv(arr: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rgb = arr.astype(np.float32) / 255.0
    r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
    mx = np.max(rgb, axis=2)
    mn = np.min(rgb, axis=2)
    df = np.maximum(mx - mn, 1e-6)
    h = np.zeros_like(mx)
    rmax = mx == r
    gmax = mx == g
    bmax = mx == b
    h[rmax] = ((g[rmax] - b[rmax]) / df[rmax]) % 6
    h[gmax] = (b[gmax] - r[gmax]) / df[gmax] + 2
    h[bmax] = (r[bmax] - g[bmax]) / df[bmax] + 4
    h = (h * 60.0) % 360.0
    s = np.zeros_like(mx)
    s[mx > 1e-6] = (mx - mn)[mx > 1e-6] / mx[mx > 1e-6]
    return h, s * 255.0, mx * 255.0
