"""Valokuva-chain locked rules — inherited by strip / Excel / PNG (not a parallel doctrine).

Bot-kokeilu only. No pipes / salaoja / sadevesi.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from vesivek import CRS_TM35FIN

# --- Neliötapa ---
AREA_CRS = CRS_TM35FIN  # m² pinned to WFS wall stick in this CRS only
DUAL_SOURCE_TOLERANCE = 0.10  # ±10 %; no averaging if exceeded

# --- Confidence labels (Excel / PNG) ---
LUOTETTAVUUS_WFS = "wfs"
LUOTETTAVUUS_PRE_LOCK = "pre_lock"
LUOTETTAVUUS_ARVIO = "arvio"
LUOTETTAVUUS_EI_VARMENNETTU = "ei_varmennettu"
LUOTETTAVUUS_EI_LASKETTU = "epavarma"

LOCK_LUKITTU = "lukittu"
LOCK_PRE = "pre_lock"
LOCK_EI_VARMENNETTU = "ei_varmennettu"
LOCK_ARVIO = "arvio"
LOCK_EI_LASKETTU = "ei_laskettu"

# Occlusion / peite kinds (never invent precise m² under cover)
PEITE_KINDS = ("autot", "ruukut", "pyorat", "varjo")

# Clutter is NOT a surface (työjärjestys 0)
CLUTTER_NOT_SURFACES = frozenset(
    {
        "ruukku",
        "ruukut",
        "tuoli",
        "poyta",
        "roskis",
        "pyora",
        "pyorat",
        "auto",
        "autot",
        "lyhty",
        "kastelukannu",
    }
)

# Classes that get work-surface mittaviivat (tier 2). Not grass / single bush / occlusion fills.
WORK_SURFACE_TICK_CLASSES = {
    "asfaltti": "MV-ASF",
    "laatta": "MV-LAATTA",
    "terassi": "MV-TERASSI",
    "katos": "MV-KATOS",
    "seinänvierus": "MV-SEINA",
    "sepeli": "MV-SEPELI",
    "rajapuska": "MV-RAJA",
    "päätylaatta": "MV-PAATY",
}

SKIP_TICK_CLASSES = frozenset({"nurmikko", "multa", "tuntematon", "pensas", "puu"})

# Continuity: bands run the full facade unless a hard break.
HARD_BREAKS = ("nurkka", "tontin_reuna", "selva_materiaalivaihdos")

# FM työjärjestys 0→3 (recognition-relevant parts only)
TYOJARJESTYS = (
    (
        0,
        "Kuvat + orto/WFS. Asfaltti ensisijaisesti ortosta. Ei rojua pintoina.",
    ),
    (
        1,
        "WFS + kuvien rakennukset. Mittaviivat (seinä→raja + työkaistat). Digitointi napsahtaa WFS:ään.",
    ),
    (
        2,
        "Yksi osio/julkisivu kerrallaan. Seinänvieruslaatta ARVIO. PRE-LOCK ennen lukkoa.",
    ),
    (
        3,
        "Lista ↔ suunnitelma. Dual >10 % → raportoi A/B, ei keskiarvoa. Leikkaa osioon.",
    ),
)

# Coded vs still TODO — Excel and README must list both.
CODED_LOCKS: tuple[tuple[str, str], ...] = (
    ("peite/EI VARMENNETTU", "Autot, ruukut, pyörät, varjo-peite → ei_varmennettu; m² ei teeskennellä tarkaksi."),
    ("ARVIO", "Päätylaatta ja kappalelaskenta (puut) merkitään ARVIO."),
    ("PRE-LOCK", "Luokka-m² ja yhden lähteen kaista pysyvät pre_lock. HSV-osuudet eivät ole lukittuja metrejä."),
    ("jatkuvuus", "Kaistakaistat jatkuvat julkisivun suuntaan; katkaisu vain nurkka / tontin reuna / selvä materiaali."),
    ("neliötapa-portti", "m² vain kun kaista on pinottu WFS-särmään EPSG:3067 ja leveys tunnetaan."),
    ("dual ±10 %", "Kaksi lähdettä (tontti vs puskuri/tikku) ±10 % = dual_ok; >10 % raportoi A ja B, ei keskiarvoa."),
    ("yksi lähde", "Photo-only tai yksi lähde → dashed / pre_lock tai EI VARMENNETTU."),
    ("kuva > tyhjä kartta", "Valokuvan luokka piirretään (katkoviiva) sen sijaan että se jätettäisiin pois."),
    ("MV-* tasot", "Rakennus: MV-### seinä→raja + 1 m. Työkaista: MV-ASF/LAATTA/TERASSI/KATOS + FM-007 SEINA/SEPELI/RAJA/PAATY."),
    ("MV skip", "Ei viivoja nurmikolle, yksittäiselle pensaalle eikä peitefillille."),
    ("WFS-snap", "Digitointi ja mittaviivat lähtevät WFS-julkisivusärmästä."),
    ("työjärjestys 0–3", "Vaihe koodataan tyovaihe-kenttään (0 kuvat/WFS … 3 dual-tarkistus)."),
    ("Excel a/b/c", "WFS-pituus, lineaariset m ja m² erillään; m² tyhjä = EI LASKETTU."),
)

TODO_LOCKS: tuple[tuple[str, str], ...] = (
    ("asfaltti ortosta", "Orto haetaan taustaksi; asfaltin automaattiluokitus ortopikseleistä ei ole koodattu."),
    ("drone", "Ei drone-aineistoa tässä bot-kokeilussa."),
    ("ihmislukko", "PRE-LOCK → lukittu vaatii ihmisen kuittauksen; automaattilukkoa ei ole."),
    ("epäsäännölliset polygonit", "Luokat ovat leveyskaistoja, ei käsin digitoidun FM-007-reunan kopiota."),
    ("varjo vs peite", "Varjo-heuristiikka on karkea; erottelu varjosta ja peitteestä on TODO."),
    ("pyörä/ruukku-CV", "Ruukku/pyörä tunnistus on karkea / pinnat.json-peite; ei täyttä CV-mallia."),
    ("lista↔suunnitelma UI", "Vaihe 3 vertaa dual-aloja; ei erillistä suunnitelmaeditoria."),
)


@dataclass(frozen=True)
class DualVerdict:
    status: str  # none | one_source | agree | disagree
    area_a: float | None
    area_b: float | None
    rel_diff: float | None
    note: str

    @property
    def agree(self) -> bool:
        return self.status == "agree"

    @property
    def n_sources(self) -> int:
        return int(self.area_a is not None) + int(self.area_b is not None)


def dual_source_verdict(area_a: float | None, area_b: float | None) -> DualVerdict:
    """Compare two m² sources. Never average when they differ by more than ±10 %."""
    a = area_a if area_a and area_a > 0 else None
    b = area_b if area_b and area_b > 0 else None
    if a is None and b is None:
        return DualVerdict("none", None, None, None, "Ei neliölähdettä — EI LASKETTU.")
    if a is None or b is None:
        src = "A (tontti/WFS)" if a is not None else "B (puskuri/tikku)"
        val = a if a is not None else b
        return DualVerdict(
            "one_source",
            a,
            b,
            None,
            f"Yksi neliölähde ({src} = {val:.2f} m²) → dashed / PRE-LOCK, ei varmennettu dualina.",
        )
    rel = abs(a - b) / max(a, b)
    if rel <= DUAL_SOURCE_TOLERANCE:
        return DualVerdict(
            "agree",
            a,
            b,
            rel,
            f"Kaksi lähdettä ±{DUAL_SOURCE_TOLERANCE*100:.0f} % (A={a:.2f}, B={b:.2f}, Δ={rel*100:.1f} %). Ei keskiarvoa — käytetään WFS-tontin alaa.",
        )
    return DualVerdict(
        "disagree",
        a,
        b,
        rel,
        f"Dual >{DUAL_SOURCE_TOLERANCE*100:.0f} % (A={a:.2f} m² tontti, B={b:.2f} m² puskuri/tikku, Δ={rel*100:.1f} %). Raportoi molemmat, ei keskiarvoa.",
    )


def area_confidence(
    *,
    peite: str | None,
    has_width: bool,
    dual: DualVerdict,
    tyyppi: str,
    from_photo_shares: bool,
    is_count: bool = False,
) -> tuple[str, str]:
    """Return (luotettavuus, lock_tila). Photo-HSV shares never lock metres."""
    if is_count or tyyppi == "päätylaatta":
        if peite:
            return LUOTETTAVUUS_EI_VARMENNETTU, LOCK_EI_VARMENNETTU
        return LUOTETTAVUUS_ARVIO, LOCK_ARVIO
    if peite:
        return LUOTETTAVUUS_EI_VARMENNETTU, LOCK_EI_VARMENNETTU
    if not has_width:
        return LUOTETTAVUUS_EI_LASKETTU, LOCK_EI_LASKETTU
    if from_photo_shares:
        return LUOTETTAVUUS_PRE_LOCK, LOCK_PRE
    if dual.n_sources < 2:
        return LUOTETTAVUUS_PRE_LOCK, LOCK_PRE
    if dual.status == "disagree":
        return LUOTETTAVUUS_PRE_LOCK, LOCK_PRE
    return LUOTETTAVUUS_PRE_LOCK, LOCK_PRE


def strip_total_lock(*, peite: str | None, dual: DualVerdict, wfs_verified: bool) -> tuple[str, str]:
    if peite:
        return LUOTETTAVUUS_EI_VARMENNETTU, LOCK_EI_VARMENNETTU
    if dual.status == "agree" and wfs_verified:
        return LUOTETTAVUUS_WFS, LOCK_LUKITTU
    if dual.n_sources >= 1:
        return LUOTETTAVUUS_PRE_LOCK, LOCK_PRE
    return LUOTETTAVUUS_EI_LASKETTU, LOCK_EI_LASKETTU


def is_clutter(tyyppi: str) -> bool:
    return (tyyppi or "").lower() in CLUTTER_NOT_SURFACES


def mv_work_prefix(tyyppi: str) -> str | None:
    if tyyppi in SKIP_TICK_CLASSES:
        return None
    return WORK_SURFACE_TICK_CLASSES.get(tyyppi)


def tyovaihe(
    *,
    has_wfs: bool,
    has_photos_or_ortho: bool,
    has_ticks: bool,
    dual: DualVerdict | None,
    one_facade: bool,
) -> int:
    """Highest completed workflow stage 0–3."""
    stage = -1
    if has_wfs or has_photos_or_ortho:
        stage = 0
    if has_wfs and has_ticks:
        stage = 1
    if stage >= 1 and one_facade:
        stage = 2
    if stage >= 2 and dual is not None and dual.n_sources >= 1:
        stage = 3
    return max(stage, 0)


def coded_lock_rows() -> list[tuple[str, str, str]]:
    rows = [("KOODATTU", k, v) for k, v in CODED_LOCKS]
    rows.extend(("TODO", k, v) for k, v in TODO_LOCKS)
    return rows


def dashed_style(lock_tila: str) -> bool:
    return lock_tila in {LOCK_PRE, LOCK_EI_VARMENNETTU, LOCK_ARVIO, LOCK_EI_LASKETTU}


def assert_unique_mv_ids(ids: list[str]) -> None:
    if len(ids) != len(set(ids)):
        dup = sorted({i for i in ids if ids.count(i) > 1})
        raise ValueError(f"MV-tunnisteet eivät ole uniikkeja: {dup}")
