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
    plot_source: str | None = None
    ortho_source: str | None = None


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
    occlusion: bool = False
    occlusion_note: str = ""


@dataclass
class StickResult:
    found: bool
    length_m: float
    length_px: float | None
    pixels_per_m: float | None
    image: Path | None
    huomio: str


@dataclass
class QcTick:
    id: str
    kind: str  # seina-raja | tikku-1m | pinta | tyokaista
    start: tuple[float, float]
    end: tuple[float, float]
    length_m: float
    huomio: str = ""
    tyyppi: str = ""
    tier: int = 1


@dataclass
class StripInfo:
    """Outward wall→edge strip (kaista), not an along-wall pie."""

    geometry: dict[str, Any] | None
    width_m: float | None
    width_source: str
    mean_width_m: float | None
    max_width_m: float | None
    clip: str  # tontti | puskuri | puuttuu
    area_m2: float | None
    huomio: str = ""
    area_m2_plot: float | None = None
    area_m2_buffer: float | None = None
    dual_status: str = "none"
    dual_note: str = ""
    work_edges: list = field(default_factory=list)


@dataclass
class SurfaceRecord:
    tyyppi: str
    label_fi: str
    kind: str  # area | linear | count | wfs
    value: float | None
    unit: str
    luotettavuus: str  # wfs | mittatikku | kayttaja | tontti | arvio | epavarma | ei_varmennettu
    lahde: str
    huomio: str
    share: float = 0.0
    geometry: dict[str, Any] | None = None
    pituus_m: float | None = None
    ala_m2: float | None = None
    peite: str | None = None
    lock_tila: str = "pre_lock"
    ala_m2_b: float | None = None
    lahde_b: str | None = None


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
    strip: StripInfo | None = None
    qc_ticks: list[QcTick] = field(default_factory=list)
    occlusion: bool = False
    occlusion_note: str = ""
    ortho_bytes: bytes | None = None
    ortho_bbox: tuple[float, float, float, float] | None = None
    mittaviivat: bool = False
    tyovaihe: int = 0
    dual_note: str = ""
