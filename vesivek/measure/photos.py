from __future__ import annotations

from pathlib import Path

from vesivek.config import IMAGE_SUFFIXES, MAX_PHOTOS_WARN


def collect_photos(paths: list[Path]) -> tuple[list[Path], list[str]]:
    """Collect all images from files and folders. No 6-image cap."""
    found: list[Path] = []
    warnings: list[str] = []
    for raw in paths:
        path = Path(raw).expanduser()
        if not path.exists():
            warnings.append(f"Polkua ei ole: {path}")
            continue
        if path.is_file():
            if path.suffix.lower() in IMAGE_SUFFIXES:
                found.append(path.resolve())
            else:
                warnings.append(f"Ei kuva: {path.name}")
            continue
        for child in sorted(path.rglob("*")):
            if child.is_file() and child.suffix.lower() in IMAGE_SUFFIXES:
                found.append(child.resolve())

    # Stable unique order
    unique: list[Path] = []
    seen: set[Path] = set()
    for item in found:
        if item not in seen:
            unique.append(item)
            seen.add(item)

    if not unique:
        warnings.append("Valokuvia ei löytynyt — pintaosuudet merkitään epävarmoiksi.")
    if len(unique) > MAX_PHOTOS_WARN:
        warnings.append(
            f"Kuvia on {len(unique)} kpl (ei ylärajaa). Ajo voi kestää; tämä on vain huomio, ei katkaisu."
        )
    return unique, warnings
