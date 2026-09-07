# Vesivek Ohjelma — bot-kokeilu

Paikallinen CLI + kevyt web-UI **ihmismittauksen testaamiseen** (suomalainen rakentaminen).

**Ei virallinen tuote.**

Osoite + työmaakuvat → WFS-lukittu runko (EPSG:3067) + **yhden julkisivukaistan aluepolygonit** (PNG + Excel).

## Mitä muuttui (0.2)

v1 jakoi julkisivun pituuden “piirakaksi” (osuus × seinän pituus). Nyt **kaista on polygoni seinästä ulos** tontin/orton reunaan tai `--kaistan-leveys` -puskuriin.

| Ennen | Nyt |
| --- | --- |
| Pintaosuudet seinän pituudella | Pintaosuudet **leveyssuunnassa** (seinä → reuna) |
| m² ≈ pituus × leveys × osuus | m² = **kaistapolygonin ala**, vain kun leveys tunnetaan |
| PNG: rakennuksen ääriviiva | PNG: tontti + orto + **aluepolygonit** + valinnaiset MV-* mittaviivat |
| Luokat: asfaltti, laatta, sepeli, pensas… | FM-007: `seinänvierus`, `rajapuska`, `päätylaatta`, `asfaltti`, `sepeli`, `laatta` |
| Excel: yksi “Määrä”-sarake | Erilliset: **(a) WFS-pituus**, **(b) lineaariset m**, **(c) m²** |

Peitetyt alat (autot yms.) merkitään **EI VARMENNETTU** — neliöitä ei teeskennellä tarkemmiksi. Ilman leveyttä m² = **EI LASKETTU**. Metrejä ei keksitä.

## Ei tee

- Ei salaojaa, ei sadevesiputkia, ei täyttä kuivatussuunnitelmaa.
- Ei keksi kaistan leveyttä eikä neliöitä ilman mittatikkua, `--kaistan-leveys` tai WFS-tontin reunaa.

---

## Asennus

Python 3.11+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Mailatie 14, Vantaa (pohjoinen kaista)

Live HSY-rakennus + Vantaan tontti + orto. `pinnat.json` on valokuvien leveysosuus, **ei** FM-007-lukujen kopio.

```bash
vesivek julkisivut --osoite "Mailatie 14, Vantaa" --wfs live

vesivek mittaa \
  --osoite "Mailatie 14, Vantaa" \
  --julkisivu pohjoinen \
  --pinnat examples/mailatie-14/pinnat.json \
  --kuvat examples/mailatie-14 \
  --wfs live
```

Ilman `--kaistan-leveys` leveys tulee tontin reunasta (WFS-geometria). Autopeite → EI VARMENNETTU. Päätylaatta ilman mitattua palaa → EI LASKETTU.

Lisää ohje: `examples/mailatie-14/README.md`. Maastokuvat A–F voi pudottaa samaan kansioon.

FM-007-lukkoihin verrataan **suuntaa**, ei pakoteta lukuja (asfaltti ~223 m² EI VARMENNETTU, seinänvierus ~36, sepeli ~36, rajapuska ~29 m² + 53.86 m viiva, päätylaatta ARVIO ~2.2).

## Demo (Helsinki / offline)

```bash
vesivek mittaa \
  --osoite "Pohjoinen Hesperiankatu 3, Helsinki" \
  --kuvat examples/kuvat \
  --julkisivu etela \
  --mittatikku 1.00 \
  --kaistan-leveys 1.20
```

Offline:

```bash
vesivek mittaa \
  --osoite "Esimerkkitontti" \
  --kuvat examples/kuvat \
  --julkisivu etela \
  --wfs stub \
  --kaistan-leveys 1.20
```

Stub = `data/sample/*.geojson` (Pohjoinen Hesperiankatu 3). **Ei Mailatien metrejä.**

### Web-UI

```bash
vesivek web --host 127.0.0.1 --port 5050
```

### Tulokset (`tulokset/<osoite>-<aika>/`)

| Tiedosto | Sisältö |
| --- | --- |
| `julkisivukaista.png` | Orto + tontti + kaistan luokkaplpolygonit + WFS-särmä + MV-* |
| `mittaus.xlsx` | WFS-pituus / Lineaariset / Pinta-alat erikseen |
| `julkisivukaista.geojson` | EPSG:3067 |
| `huomiot.txt` | epävarmuudet |

---

## m²-sääntö

Pinta-ala lasketaan **vain** kun kaistan leveys tunnetaan:

1. `--kaistan-leveys` (käyttäjä), tai
2. tunnistettu mittatikku kuvissa, tai
3. WFS-tontin reuna (seinä → kiinteistöraja, ei arvaus).

Muuten Excelissä `ala_m2` = `EI LASKETTU`. Lineaarinen WFS-pituus säilyy.

---

## WFS

Oletusketju (`--wfs auto`):

1. **Helsingin avoin WFS** — rakennus + kiinteistö (Helsingin osoitteet)
2. **HSY** — `pks_rakennukset_paivittyva` (osoite-osuus `katu` + `osno1`, ei pelkkä lähin piste)
3. **Vantaa** — `kiinteisto:kiinteisto` täydentää tontin; `gis:rakennukset` varalla
4. **Stub** — `data/sample`

Orto: Vantaan WMS `taustakartta:ortoilmakuva` (EPSG:3067), Helsinki WMS varalla.

`--wfs live` epäonnistuu jos verkko estää — metrejä ei täytetä stubilla hiljaa.

---

## Valinnainen `pinnat.json`

Osuudet ovat **seinästä ulos** (`jaottelu: seinasta`):

```json
{
  "jaottelu": "seinasta",
  "peite": "autot",
  "osuudet": [
    { "tyyppi": "seinänvierus", "osuus": 0.15 },
    { "tyyppi": "asfaltti", "osuus": 0.62 },
    { "tyyppi": "sepeli", "osuus": 0.16 },
    { "tyyppi": "rajapuska", "osuus": 0.07 }
  ]
}
```

QC-mittaviivat: `--mittaviivat` (oletus) / `--no-mittaviivat`. Tunnisteet `MV-001`…

---

## Testit

```bash
pytest -q
```

---

## English summary

Bot experiment (not a product). One facade **strip polygon** from the WFS wall out to the plot edge or a measured buffer. Areas (m²) only when width is known. FM-007 class labels. Occluded surfaces stay **EI VARMENNETTU**. No drainage pipes.
