from __future__ import annotations

import argparse
import sys
from pathlib import Path

from vesivek import CRS_TM35FIN, __version__
from vesivek.config import DEFAULT_STICK_M
from vesivek.pipeline import RunRequest, list_site_facades, run_measurement
from vesivek.wfs.chain import list_fetchers


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="vesivek",
        description=(
            "Vesivek Ohjelma bot-kokeilu — osoite + kuvat → WFS-lukittu julkisivukaista "
            "(seinä → reuna -polygoni, PNG + Excel). Ei virallinen tuote."
        ),
    )
    parser.add_argument("--version", action="version", version=f"vesivek {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("julkisivut", help="Hae WFS-runko ja listaa julkisivut pituuksineen")
    _add_site_args(p_list)

    p_run = sub.add_parser("mittaa", help="Mittaa yksi valittu julkisivu / kaista")
    _add_site_args(p_run)
    p_run.add_argument(
        "--kuvat",
        nargs="*",
        default=[],
        help="Kansioita ja/tai kuvatiedostoja (ei 6 kuvan rajaa). Voi jättää tyhjäksi jos --pinnat.",
    )
    p_run.add_argument("--julkisivu", default="auto", help="etela|pohjoinen|ita|lansi|reuna-N|auto")
    p_run.add_argument("--mittatikku", type=float, default=DEFAULT_STICK_M, help="Mittatikun tunnettu pituus, m (oletus 1.00)")
    p_run.add_argument(
        "--kaistan-leveys",
        type=float,
        default=None,
        help="Kaistan leveys metreinä (käyttäjän mitta). Ilman tätä/tikkua/tonttia m² = EI LASKETTU.",
    )
    p_run.add_argument("--pinnat", type=Path, default=None, help="Valinnainen pinnat.json (osuudet seinästä ulos)")
    p_run.add_argument("--out", type=Path, default=None, help="Tuloshakemiston juuri (oletus ./tulokset)")
    p_run.add_argument(
        "--mittaviivat",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Piirrä QC-mittaviivat MV-* (oletus päällä; --no-mittaviivat poistaa)",
    )
    p_run.add_argument(
        "--ortho",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Hae avoin ortoilmakuva PNG-taustaksi (oletus päällä; --no-ortho poistaa)",
    )

    p_web = sub.add_parser("web", help="Käynnistä kevyt paikallinen käyttöliittymä")
    p_web.add_argument("--host", default="127.0.0.1")
    p_web.add_argument("--port", type=int, default=5050)

    args = parser.parse_args(argv)
    if args.cmd == "julkisivut":
        return _cmd_julkisivut(args)
    if args.cmd == "mittaa":
        return _cmd_mittaa(args)
    if args.cmd == "web":
        from vesivek.web import serve

        serve(host=args.host, port=args.port)
        return 0
    parser.error("tuntematon komento")
    return 2


def _add_site_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--osoite", required=True, help="Suomalainen katuosoite")
    p.add_argument(
        "--wfs",
        choices=("auto", "live", "stub"),
        default="auto",
        help="auto = live Helsinki/HSY/Vantaa, sitten stub; live = vain verkko; stub = esimerkki",
    )
    p.add_argument("--geojson", type=Path, default=None, help="Oma WFS-ote / GeoJSON EPSG:3067")


def _cmd_julkisivut(args: argparse.Namespace) -> int:
    try:
        site, facades = list_site_facades(args.osoite, wfs_mode=args.wfs, geojson=args.geojson)
    except Exception as exc:
        print(f"Virhe: {exc}", file=sys.stderr)
        return 1
    print(f"Osoite: {site.address_query}")
    print(f"Osuma:  {site.matched_address or '—'}")
    print(f"CRS:    {site.crs}  lukittu={site.verified}")
    print(f"Lähde:  {site.source_name}")
    print(f"Id:     {site.feature_id or '—'}")
    print(f"Tontti: {'kyllä' if site.plot else 'ei'}" + (f" ({site.plot_source})" if site.plot_source else ""))
    for w in site.warnings:
        print(f"Huomio: {w}")
    print()
    print("Julkisivut (WFS-särmät, metrit geometriasta — ei keksitty):")
    for f in facades:
        if f.key.startswith("reuna-"):
            continue
        print(f"  {f.key:12}  {f.length_m:8.2f} m   {f.label_fi}   ({len(f.edges)} janaa)")
    print()
    print("Yksittäiset särmät (≥ 1 m; lyhyemmät porrastukset sisältyvät sivun summaan):")
    for f in facades:
        if f.key.startswith("reuna-") and f.length_m >= 1.0:
            print(f"  {f.key:12}  {f.length_m:8.2f} m   {f.compass}")
    return 0


def _cmd_mittaa(args: argparse.Namespace) -> int:
    req = RunRequest(
        osoite=args.osoite,
        kuvat=[Path(p) for p in args.kuvat],
        julkisivu=args.julkisivu,
        mittatikku_m=args.mittatikku,
        kaistan_leveys_m=args.kaistan_leveys,
        wfs_mode=args.wfs,
        geojson=args.geojson,
        pinnat=args.pinnat,
        output_dir=args.out,
        mittaviivat=args.mittaviivat,
        ortho=args.ortho,
    )
    print("1) Geokoodataan osoite ja haetaan WFS-runko + tontti (EPSG:3067)…")
    try:
        result = run_measurement(req)
    except Exception as exc:
        print(f"Virhe: {exc}", file=sys.stderr)
        return 1
    print(f"2) Runko: {result.site.source_name}  lukittu={result.site.verified}  tontti={'kyllä' if result.site.plot else 'ei'}")
    print(f"3) Julkisivu: {result.facade.label_fi}  {result.facade.length_m:.2f} m ({CRS_TM35FIN})")
    print(f"4) Valokuvia: {len(result.photos)}  mittatikku: {'kyllä' if result.stick.found else 'ei'}")
    width = result.strip_width_m
    print(f"5) Kaistan leveys: {width:.2f} m ({result.strip_width_source})" if width else "5) Kaistan leveys: MITTAAMATTA")
    if result.strip:
        ala = "EI LASKETTU" if result.strip.area_m2 is None else f"{result.strip.area_m2:.2f} m²"
        print(f"   clip={result.strip.clip}  kaista yhteensä: {ala}")
    print("6) Pinnat (m ja m² erillään):")
    for rec in result.surfaces:
        if rec.kind == "area":
            val = "EI LASKETTU" if rec.value is None else f"{rec.value:.2f} m²"
        else:
            val = "—" if rec.value is None else f"{rec.value:.3f} {rec.unit}"
        extra = f" peite={rec.peite}" if rec.peite else ""
        print(f"   - {rec.label_fi:36} {val:16} [{rec.luotettavuus}]{extra}")
    print()
    print(f"PNG:     {result.png_path}")
    print(f"Excel:   {result.xlsx_path}")
    print(f"GeoJSON: {result.geojson_path}")
    if result.warnings:
        print("\nHuomiot:")
        for w in result.warnings:
            print(f"  • {w}")
    return 0


def print_plugin_help() -> None:
    print("WFS-hakijat:")
    for name in list_fetchers():
        print(f"  - {name}")
