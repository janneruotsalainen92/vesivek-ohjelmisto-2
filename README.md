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

## Valokuva-lukot (perintö, ei rinnakkainen oppi)

Ketjun lukot on koodattu `vesivek/valokuva.py`:stä. Strip, Excel ja PNG **perivät** ne.

### Koodattu

| Lukko | Toteutus |
| --- | --- |
| Peite / EI VARMENNETTU | Autot, ruukut, pyörät, varjo → `ei_varmennettu`. m² ei teeskennellä tarkaksi. |
| ARVIO | Päätylaatta ja kpl-laskenta. |
| PRE-LOCK | Luokka-m² ja yhden lähteen kaista. HSV-osuudet **eivät** ole lukittuja metrejä. |
| Jatkuvuus | Kaistat julkisivun suuntaan; katkaisu vain nurkka / tontin reuna / selvä materiaali. |
| Neliötapa | m² vain WFS-särmään EPSG:3067 pinottuna, kun leveys tunnetaan. |
| Dual ±10 % | Tontti (A) vs puskuri/tikku (B). Sovittu → dual_ok. Ero >10 % → raportoi A **ja** B, **ei keskiarvoa**. |
| Yksi lähde | Photo-only / yksi lähde → dashed / PRE-LOCK. |
| Kuva > tyhjä kartta | Valokuvan luokka piirretään katkoviivalla, ei jätetä pois. |
| MV-* tasot | 1: `MV-###` seinä→raja + 1 m. 2: `MV-ASF-*`, `MV-LAATTA-*`, `MV-TERASSI-*`, `MV-KATOS-*`, `MV-SEINA-*`, `MV-SEPELI-*`, `MV-RAJA-*`, `MV-PAATY-*`. Ei nurmikkoa / pensasta / peitefilliä. |
| WFS-snap | Viivat lähtevät WFS-julkisivusärmästä. QC-kerros; `--no-mittaviivat` piilottaa. |
| Työjärjestys 0→3 | `tyovaihe` kenttä + Excel-välilehti Valokuva-lukot. |
| Excel a/b/c | WFS-pituus, lineaariset m, m² erillään. |

### TODO (ei tässä bot-kokeilussa)

- Asfaltin automaattiluokitus **ortopikseleistä** (orto on vain tausta)
- Drone
- Ihmisen kuittaus PRE-LOCK → lukittu
- Epäsäännölliset FM-007-polygonit (nyt leveyskaistat)
- Varjo vs peite -erottelu, täysi ruukku/pyörä-CV
- Lista↔suunnitelma -editori

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

QC-mittaviivat: `--mittaviivat` (oletus, QC-kerros) / `--no-mittaviivat` (piilota esityksestä). Tunnisteet `MV-###` (rakennus) ja `MV-ASF-*` / `MV-SEINA-*` … (työkaista).

---

## Testit

```bash
pytest -q
```

---

## English summary

Bot experiment (not a product). One facade **strip polygon** from the WFS wall out to the plot edge or a measured buffer. Areas (m²) only when width is known and pinned to EPSG:3067. Class splits stay **PRE-LOCK**; occluded surfaces **EI VARMENNETTU**. Dual sources >10% report A and B, no average. No drainage pipes.
