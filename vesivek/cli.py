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
        description="Vesivek Ohjelma MVP v1 — osoite + kuvat → WFS-lukittu julkisivukaista (PNG + Excel).",
    )
    parser.add_argument("--version", action="version", version=f"vesivek {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("julkisivut", help="Hae WFS-runko ja listaa julkisivut pituuksineen")
    _add_site_args(p_list)

    p_run = sub.add_parser("mittaa", help="Mittaa yksi valittu julkisivu / kaista")
    _add_site_args(p_run)
    p_run.add_argument(
        "--kuvat",
        nargs="+",
        required=True,
        help="Kansioita ja/tai kuvatiedostoja (ei 6 kuvan rajaa)",
    )
    p_run.add_argument("--julkisivu", default="auto", help="etela|pohjoinen|ita|lansi|reuna-N|auto")
    p_run.add_argument("--mittatikku", type=float, default=DEFAULT_STICK_M, help="Mittatikun tunnettu pituus, m (oletus 1.00)")
    p_run.add_argument("--kaistan-leveys", type=float, default=None, help="Kaistan leveys metreinä (käyttäjän mitta, ei keksitä)")
    p_run.add_argument("--pinnat", type=Path, default=None, help="Valinnainen pinnat.json-osuustiedosto")
    p_run.add_argument("--out", type=Path, default=None, help="Tuloshakemiston juuri (oletus ./tulokset)")

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
        help="auto = live Helsinki/HSY, sitten stub; live = vain verkko; stub = esimerkki",
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
    for w in site.warnings:
        print(f"Huomio: {w}")
    print()
    print("Julkisivut (WFS-särmät, metrit geometriasta — ei keksitty):")
    for f in facades:
        if f.key.startswith("reuna-"):
            continue
        print(f"  {f.key:12}  {f.length_m:8.2f} m   {f.label_fi}   ({len(f.edges)} janaa)")
    print()
    print("Yksittäiset särmät:")
    for f in facades:
        if f.key.startswith("reuna-"):
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
    )
    print("1) Geokoodataan osoite ja haetaan WFS-runko (EPSG:3067)…")
    try:
        result = run_measurement(req)
    except Exception as exc:
        print(f"Virhe: {exc}", file=sys.stderr)
        return 1
    print(f"2) Runko: {result.site.source_name}  lukittu={result.site.verified}")
    print(f"3) Julkisivu: {result.facade.label_fi}  {result.facade.length_m:.2f} m ({CRS_TM35FIN})")
    print(f"4) Valokuvia: {len(result.photos)}  mittatikku: {'kyllä' if result.stick.found else 'ei'}")
    width = result.strip_width_m
    print(f"5) Kaistan leveys: {width:.2f} m ({result.strip_width_source})" if width else "5) Kaistan leveys: MITTAAMATTA")
    print("6) Pinnat:")
    for rec in result.surfaces:
        val = "—" if rec.value is None else f"{rec.value:.3f} {rec.unit}"
        print(f"   - {rec.label_fi:32} {val:16} [{rec.luotettavuus}]")
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
