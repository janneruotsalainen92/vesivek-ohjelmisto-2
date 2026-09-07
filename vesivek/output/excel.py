from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from vesivek.models import MeasurementResult

HEADER_FILL = PatternFill("solid", fgColor="E85D04")
HEADER_FONT = Font(color="FFFFFF", bold=True)
WARN_FILL = PatternFill("solid", fgColor="FFF3CD")
LOCK_FILL = PatternFill("solid", fgColor="D1FAE5")
UNSURE_FILL = PatternFill("solid", fgColor="FECACA")


def write_excel(result: MeasurementResult, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()

    _summary(wb.active, result)
    _surfaces(wb.create_sheet("Pinnat"), result)
    _photos(wb.create_sheet("Valokuvat"), result)
    _wfs(wb.create_sheet("WFS"), result)

    wb.save(path)
    return path


def _style_header(ws, headers: list[str]) -> None:
    ws.append(headers)
    for col, _ in enumerate(headers, start=1):
        cell = ws.cell(1, col)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(wrap_text=True)
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}1"


def _autosize(ws, widths: list[int]) -> None:
    for i, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = width


def _summary(ws, result: MeasurementResult) -> None:
    ws.title = "Yhteenveto"
    ws["A1"] = "Vesivek Ohjelma — MVP v1"
    ws["A1"].font = Font(bold=True, size=16, color="E85D04")
    ws["A2"] = "Yksi julkisivu / kaista. Ei salaojaa, ei sadevesiputkia, ei täyttä kuivatussuunnitelmaa."

    rows = [
        ("Osoite (syöte)", result.site.address_query),
        ("WFS-osuma", result.site.matched_address or "—"),
        ("CRS", result.site.crs),
        ("WFS-lähde", result.site.source_name),
        ("WFS-lukittu", "kyllä" if result.site.verified else "EI — esimerkkigeometria / paikallinen tiedosto"),
        ("Kohde-id", result.site.feature_id or "—"),
        ("Julkisivu", result.facade.label_fi),
        ("Julkisivun pituus (m)", round(result.facade.length_m, 3)),
        ("Kaistan leveys (m)", result.strip_width_m if result.strip_width_m is not None else "MITTAAMATTA"),
        ("Leveyden lähde", result.strip_width_source),
        ("Mittatikku", result.stick.huomio),
        ("Valokuvia", len(result.photos)),
        ("PNG", str(result.png_path) if result.png_path else "—"),
        ("GeoJSON", str(result.geojson_path) if result.geojson_path else "—"),
    ]
    ws.append([])
    for i, (k, v) in enumerate(rows, start=4):
        ws.cell(i, 1, k).font = Font(bold=True)
        ws.cell(i, 2, v)
        if k == "WFS-lukittu":
            ws.cell(i, 2).fill = LOCK_FILL if result.site.verified else UNSURE_FILL

    r = 4 + len(rows) + 2
    ws.cell(r, 1, "Huomiot / epävarmuudet").font = Font(bold=True)
    for note in result.warnings + result.site.warnings:
        r += 1
        ws.cell(r, 1, note)
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=4)
        ws.cell(r, 1).fill = WARN_FILL
        ws.cell(r, 1).alignment = Alignment(wrap_text=True)

    r += 2
    ws.cell(r, 1, "Sääntö: metrejä ei keksitä. WFS-särmä on ainoa lukittu pituus. Leveys ja m² vaativat mittatikun tai käyttäjän leveyden.")
    _autosize(ws, [28, 90, 24, 24])


def _surfaces(ws, result: MeasurementResult) -> None:
    _style_header(
        ws,
        ["Kohde", "Tyyppi", "Määrä", "Yksikkö", "Luotettavuus", "Lähde", "Osuus", "Huomio"],
    )
    for rec in result.surfaces:
        ws.append(
            [
                rec.label_fi,
                rec.kind,
                rec.value if rec.value is not None else "EI LASKETTU",
                rec.unit,
                rec.luotettavuus,
                rec.lahde,
                round(rec.share, 4) if rec.share else "",
                rec.huomio,
            ]
        )
        last = ws.max_row
        if rec.luotettavuus in {"epavarma", "esimerkki"} or rec.value is None:
            ws.cell(last, 3).fill = UNSURE_FILL
            ws.cell(last, 5).fill = UNSURE_FILL
        elif rec.luotettavuus == "wfs":
            ws.cell(last, 5).fill = LOCK_FILL
        elif rec.luotettavuus in {"arvio", "mittatikku", "kayttaja"}:
            ws.cell(last, 5).fill = WARN_FILL
        ws.cell(last, 8).alignment = Alignment(wrap_text=True)
    _autosize(ws, [36, 12, 14, 10, 16, 32, 10, 80])


def _photos(ws, result: MeasurementResult) -> None:
    _style_header(ws, ["Tiedosto", "Px", "Luottamus", "Vallitseva", "Huomiot"])
    if not result.photos:
        ws.append(["(ei kuvia)", "", "", "", "Pintaosuuksia ei arvioitu."])
    for photo in result.photos:
        top = max(photo.fractions, key=photo.fractions.get)
        ws.append(
            [
                photo.path.name,
                f"{photo.width_px}×{photo.height_px}",
                round(photo.confidence, 3),
                f"{top} {photo.fractions[top]*100:.0f} %",
                "; ".join(photo.notes),
            ]
        )
    _autosize(ws, [40, 14, 12, 22, 80])


def _wfs(ws, result: MeasurementResult) -> None:
    _style_header(ws, ["Kenttä", "Arvo"])
    site = result.site
    rows = [
        ("Lähde", site.source_name),
        ("URL / kysely", site.source_url or "—"),
        ("CRS", site.crs),
        ("Verified", site.verified),
        ("Feature id", site.feature_id or "—"),
        ("E", round(site.easting, 3)),
        ("N", round(site.northing, 3)),
        ("Julkisivun särmiä", len(result.facade.edges)),
        ("Julkisivun pituus m", round(result.facade.length_m, 3)),
    ]
    props = (site.building.get("properties") or {})
    for key, val in list(props.items())[:20]:
        rows.append((f"rakennus.{key}", val))
    if site.plot:
        pprops = site.plot.get("properties") or {}
        for key, val in list(pprops.items())[:12]:
            rows.append((f"tontti.{key}", val))
    for k, v in rows:
        ws.append([k, v])
    _autosize(ws, [28, 100])
