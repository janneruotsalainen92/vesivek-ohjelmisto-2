from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from vesivek.models import PhotoInfo


# Finnish FM-007 class keys (also used as tyyppi in Excel / PNG).
FM007_CLASSES = (
    "seinänvierus",
    "rajapuska",
    "päätylaatta",
    "asfaltti",
    "sepeli",
    "laatta",
)

# Wall → edge stack order for area bands.
WALL_TO_EDGE = (
    "seinänvierus",
    "laatta",
    "asfaltti",
    "sepeli",
    "nurmikko",
    "multa",
    "rajapuska",
    "tuntematon",
)

SURFACE_LABELS = {
    "seinänvierus": "Seinänvierus",
    "laatta": "Laatta",
    "päätylaatta": "Päätylaatta",
    "asfaltti": "Asfaltti",
    "sepeli": "Sepeli",
    "rajapuska": "Rajapuska",
    "nurmikko": "Nurmikko",
    "pensas": "Pensas / hedge",
    "multa": "Multa / paljas maa",
    "tuntematon": "Tuntematon / epävarma",
}

# Pixel class priority when several rules match: first wins in _classify_hsv assignment order.
_CLASSES = (
    "nurmikko",
    "pensas",
    "multa",
    "asfaltti",
    "laatta",
    "sepeli",
    "seinänvierus",
    "päätylaatta",
    "tuntematon",
)

LINEAR_TYPES = {"rajapuska", "pensas"}
AREA_TYPES = {
    "asfaltti",
    "laatta",
    "sepeli",
    "nurmikko",
    "multa",
    "seinänvierus",
    "päätylaatta",
    "tuntematon",
    "rajapuska",
}


def classify_photo(path: Path) -> PhotoInfo:
    notes: list[str] = []
    with Image.open(path) as im:
        im = im.convert("RGB")
        w, h = im.size
        if max(w, h) > 1600:
            im.thumbnail((1600, 1600))
            notes.append("pienennetty luokitusta varten")
        arr = np.asarray(im, dtype=np.uint8)

    hsv = _rgb_to_hsv(arr)
    ground = hsv[int(hsv.shape[0] * 0.30) :, :, :]
    cls = _classify_hsv(ground)
    counts = {name: float(np.count_nonzero(cls == i)) for i, name in enumerate(_CLASSES)}
    total = sum(counts.values()) or 1.0
    fractions = {name: counts[name] / total for name in _CLASSES}

    known = 1.0 - fractions["tuntematon"]
    top = max((k for k in fractions if k != "tuntematon"), key=lambda k: fractions[k])
    confidence = min(0.95, max(0.15, known * (0.35 + fractions[top])))
    if confidence < 0.4:
        notes.append("luokitus epävarma — värisävyt eivät erotu selvästi")
    notes.append(f"vallitseva arvio: {SURFACE_LABELS.get(top, top)} ({fractions[top]*100:.0f} % maakaistasta)")

    occ, occ_note = detect_occlusion_arr(arr)
    if occ:
        notes.append(occ_note)

    stem = path.stem.lower()
    if "paaty" in stem or "pääty" in stem or "paatylaatta" in stem:
        fractions["päätylaatta"] = fractions.get("päätylaatta", 0) + fractions.get("laatta", 0) * 0.5
        notes.append("päätykuva: laattahavainto merkitään päätylaataksi (ARVIO)")

    return PhotoInfo(
        path=path,
        width_px=w,
        height_px=h,
        fractions=fractions,
        confidence=confidence,
        notes=notes,
        occlusion=occ,
        occlusion_note=occ_note if occ else "",
    )


def merge_fractions(photos: list[PhotoInfo]) -> tuple[dict[str, float], float]:
    empty = {name: 0.0 for name in _CLASSES}
    empty["tuntematon"] = 1.0
    if not photos:
        return empty, 0.0
    weights = [max(0.05, p.confidence) for p in photos]
    wsum = sum(weights) or 1.0
    merged = {name: 0.0 for name in _CLASSES}
    for photo, weight in zip(photos, weights):
        for name, frac in photo.fractions.items():
            merged[name] = merged.get(name, 0.0) + frac * weight
    for name in list(merged):
        merged[name] /= wsum
    total = sum(merged.values()) or 1.0
    merged = {k: v / total for k, v in merged.items()}
    conf = float(np.mean([p.confidence for p in photos]))
    return to_fm007_fractions(merged), conf


def to_fm007_fractions(fractions: dict[str, float]) -> dict[str, float]:
    """Map photo HSV classes onto FM-007 labels. Does not invent metres."""
    out: dict[str, float] = {k: 0.0 for k in list(FM007_CLASSES) + ["nurmikko", "multa", "tuntematon"]}
    for name, val in fractions.items():
        if name == "pensas":
            out["rajapuska"] += val
        elif name in out:
            out[name] += val
        elif name == "tuntematon":
            out["tuntematon"] += val
        else:
            out["tuntematon"] += val
    # Typical strip: dark soil/wood against the wall → seinänvierus when asphalt is also present.
    if out.get("asfaltti", 0) > 0.08 and out.get("multa", 0) > 0.02:
        move = out["multa"] * 0.7
        out["seinänvierus"] += move
        out["multa"] -= move
    total = sum(out.values()) or 1.0
    return {k: v / total for k, v in out.items()}


def detect_occlusion_arr(arr: np.ndarray) -> tuple[bool, str]:
    """Heuristic for cars / large covers. Never used to invent m²."""
    h, w = arr.shape[:2]
    ground = arr[int(h * 0.28) :, :, :]
    rgb = ground.astype(np.float32)
    mx = np.max(rgb, axis=2)
    mn = np.min(rgb, axis=2)
    sat = (mx - mn) / np.maximum(mx, 1.0)
    # Pale vehicle bodies (white / light grey vans and SUVs).
    pale = (mx >= 175) & (sat < 0.22)
    frac = float(pale.mean())
    if frac >= 0.045:
        return True, f"EI VARMENNETTU (peite=autot, vaalea peitto {frac*100:.0f} % maakaistasta)"
    return False, ""


def photos_have_occlusion(photos: list[PhotoInfo]) -> tuple[bool, str]:
    notes = [p.occlusion_note for p in photos if p.occlusion]
    if notes:
        return True, notes[0]
    return False, ""


def count_trees(photos: list[PhotoInfo]) -> tuple[int | None, str]:
    """Heuristic blob count. Always marked as arvio — not a surveyed tree inventory."""
    if not photos:
        return None, "Puita ei laskettu (ei kuvia)."
    counts: list[int] = []
    for photo in photos:
        try:
            with Image.open(photo.path) as im:
                im = im.convert("RGB")
                im.thumbnail((220, 220))
                arr = np.asarray(im, dtype=np.uint8)
        except OSError:
            continue
        hsv = _rgb_to_hsv(arr)
        h, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
        green = (h >= 70) & (h <= 160) & (s >= 40) & (v >= 30) & (v <= 160)
        green[int(green.shape[0] * 0.55) :, :] = False
        n = _blob_count(green)
        counts.append(n)
    if not counts:
        return None, "Puulaskenta epäonnistui."
    med = int(round(float(np.median(counts))))
    return med, "Puut: visuaalinen arvio valokuvista, ei WFS-lukittu lukumäärä."


def _blob_count(mask: np.ndarray) -> int:
    vis = np.zeros(mask.shape, dtype=bool)
    h, w = mask.shape
    count = 0
    min_area = max(40, (h * w) // 800)
    for y in range(h):
        for x in range(w):
            if not mask[y, x] or vis[y, x]:
                continue
            stack = [(y, x)]
            vis[y, x] = True
            area = 0
            while stack:
                cy, cx = stack.pop()
                area += 1
                for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                    if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not vis[ny, nx]:
                        vis[ny, nx] = True
                        stack.append((ny, nx))
            if area >= min_area:
                count += 1
    return count


def _rgb_to_hsv(arr: np.ndarray) -> np.ndarray:
    rgb = arr.astype(np.float32) / 255.0
    r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
    mx = np.max(rgb, axis=2)
    mn = np.min(rgb, axis=2)
    df = mx - mn
    h = np.zeros_like(mx)
    mask = df > 1e-6
    rmax = mask & (mx == r)
    gmax = mask & (mx == g)
    bmax = mask & (mx == b)
    h[rmax] = ((g[rmax] - b[rmax]) / df[rmax]) % 6
    h[gmax] = (b[gmax] - r[gmax]) / df[gmax] + 2
    h[bmax] = (r[bmax] - g[bmax]) / df[bmax] + 4
    h = (h * 60.0) % 360.0
    s = np.zeros_like(mx)
    s[mx > 1e-6] = df[mx > 1e-6] / mx[mx > 1e-6]
    v = mx
    return np.stack([h, s * 255.0, v * 255.0], axis=2)


def _classify_hsv(hsv: np.ndarray) -> np.ndarray:
    h, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    out = np.full(h.shape, _CLASSES.index("tuntematon"), dtype=np.uint8)

    soil = (h >= 10) & (h <= 45) & (s >= 40) & (v >= 40) & (v <= 180)
    asphalt = (s < 35) & (v >= 35) & (v <= 130)
    slab = (s < 30) & (v > 145) & (v <= 230)
    gravel = (h >= 20) & (h <= 55) & (s >= 20) & (s < 80) & (v >= 80) & (v <= 190)
    green = (h >= 70) & (h <= 165) & (s >= 35) & (v >= 25)
    hedge = green & (v <= 110)
    grass = green & (v > 110)
    wood = (h >= 15) & (h <= 45) & (s >= 35) & (v >= 25) & (v <= 110)
    red_tile = ((h <= 18) | (h >= 345)) & (s >= 40) & (v >= 70) & (v <= 200)

    out[gravel] = _CLASSES.index("sepeli")
    out[asphalt] = _CLASSES.index("asfaltti")
    out[slab] = _CLASSES.index("laatta")
    out[soil] = _CLASSES.index("multa")
    out[wood] = _CLASSES.index("seinänvierus")
    out[grass] = _CLASSES.index("nurmikko")
    out[hedge] = _CLASSES.index("pensas")
    out[red_tile] = _CLASSES.index("päätylaatta")
    return out
