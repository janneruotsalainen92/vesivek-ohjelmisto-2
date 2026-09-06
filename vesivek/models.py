from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SiteFrame:
    crs: str
    source_name: str
    source_url: str | None
    verified: bool
    building: dict[str, Any]
    plot: dict[str, Any] | None
    address_query: str
    matched_address: str | None
    easting: float
    northing: float
    feature_id: str | None
    warnings: list[str] = field(default_factory=list)


@dataclass
class Edge:
    start: tuple[float, float]
    end: tuple[float, float]
    length_m: float
    outward: tuple[float, float]
    compass: str
    index: int


@dataclass
class Facade:
    key: str
    label_fi: str
    compass: str
    length_m: float
    edges: list[Edge]
    verified: bool
    source: str


@dataclass
class PhotoInfo:
    path: Path
    width_px: int
    height_px: int
    fractions: dict[str, float]
    confidence: float
    notes: list[str]


@dataclass
class StickResult:
    found: bool
    length_m: float
    length_px: float | None
    pixels_per_m: float | None
    image: Path | None
    huomio: str


@dataclass
class SurfaceRecord:
    tyyppi: str
    label_fi: str
    kind: str  # area | linear | count
    value: float | None
    unit: str
    luotettavuus: str  # wfs | mittatikku | kayttaja | arvio | epavarma
    lahde: str
    huomio: str
    share: float = 0.0
    geometry: dict[str, Any] | None = None


@dataclass
class MeasurementResult:
    site: SiteFrame
    facade: Facade
    surfaces: list[SurfaceRecord]
    photos: list[PhotoInfo]
    stick: StickResult
    strip_width_m: float | None
    strip_width_source: str
    warnings: list[str]
    output_dir: Path
    png_path: Path | None = None
    xlsx_path: Path | None = None
    geojson_path: Path | None = None
