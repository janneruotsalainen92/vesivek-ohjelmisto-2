# Vesivek Ohjelma — MVP v1

Paikallinen CLI + kevyt web-UI **ihmismittauksen testaamiseen** (Vesivek Salaojat / suomalainen rakentaminen).

**Osoite + työmaakuvat → WFS-lukittu runko (EPSG:3067) + yhden julkisivukaistan pinta-alat (PNG + Excel).**

## v1 tekee

- Hakee avoimen kunnallisen / HSY-tyyppisen **WFS-rakennuksen ja tontin** (TM35FIN, `EPSG:3067`).
- **Lukitsee seinän / julkisivun pituuden** WFS-geometriaan. Metrejä ei keksitä kuvista.
- Ihmisen valitsema **yksi julkisivu / kaista** (pohjoinen / itä / etelä / länsi tai yksittäinen särmä).
- Lukee **kaikki valokuvat** kansioista (ei 6 kuvan rajaa).
- Valinnainen **mittatikku / mittakeppi** (oletuspituus **1.00 m**) mittakaavaksi, jos tikku näkyy kuvissa.
- Luokittelee kaistan pintoja: asfaltti, laatta, sepeli, nurmikko, pensas, multa… (arvio kuvista).
- Lineaariset piirteet (esim. pensas) **metreinä**; puut **kappaleina**.
- Tulostaa **PNG-overlayn**, **Excelin (.xlsx)** ja **GeoJSONin**.
- Merkitsee **epävarmat / varmistamattomat** arvot selvästi.

## v1 ei tee

- Ei salaojaa, ei sadevesiputkia.
- Ei täyttä kuivatus- / hulevesisuunnitelmaa.
- Ei mittaa koko tonttia eikä useaa julkisivua yhdellä ajolla.
- Ei keksi kaistan leveyttä eikä neliöitä, jos leveyttä ei ole mitattu (mittatikku tai `--kaistan-leveys`).

---

## Asennus (paikallisesti)

Python 3.11+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Demo (README-polku)

Esimerkkikuvat: `examples/kuvat/` (työmaakuva) ja `examples/kuvat_mittatikku/` (synteettinen 1 m tikku).

### 1) Live-WFS + kuvakansio (suositeltu)

Helsingin avoin WFS toimii ilman avainta.

```bash
vesivek julkisivut --osoite "Pohjoinen Hesperiankatu 3, Helsinki"

vesivek mittaa \
  --osoite "Pohjoinen Hesperiankatu 3, Helsinki" \
  --kuvat examples/kuvat \
  --julkisivu etela \
  --mittatikku 1.00
```

Jos haluat neliöt (m²), anna mitattu kaistan leveys — sitä ei arvata:

```bash
vesivek mittaa \
  --osoite "Pohjoinen Hesperiankatu 3, Helsinki" \
  --kuvat examples/kuvat \
  --julkisivu etela \
  --mittatikku 1.00 \
  --kaistan-leveys 1.20
```

### 2) Offline / stub (verkko tai WFS jumissa)

```bash
vesivek mittaa \
  --osoite "Esimerkkitontti" \
  --kuvat examples/kuvat \
  --julkisivu etela \
  --wfs stub \
  --kaistan-leveys 1.20
```

Stub käyttää `data/sample/*.geojson` (oikea WFS-ote: Pohjoinen Hesperiankatu 3 / tontti 91-14-462-17, EPSG:3067). **Metrit ovat tämän esimerkkikohteen geometriaa**, eivät satunnaisen syötetyn osoitteen mittoja.

### 3) Web-UI

```bash
vesivek web --host 127.0.0.1 --port 5050
```

Avaa <http://127.0.0.1:5050> — suomenkieliset kentät: osoite → valitse julkisivu → lataa kuvat → PNG + Excel.

### Tulokset

Kirjoitetaan hakemistoon `tulokset/<osoite>-<aika>/`:

| Tiedosto | Sisältö |
| --- | --- |
| `julkisivukaista.png` | WFS-runko + valitun julkisivun nimetyt pinnat |
| `mittaus.xlsx` | m / m² / kpl, luotettavuus, lähde, huomiot |
| `julkisivukaista.geojson` | sama geometria EPSG:3067 |
| `huomiot.txt` | epävarmuudet |

---

## Mitä lukitaan, mitä merkitään epävarmaksi

| Suure | Lähde | Luotettavuus |
| --- | --- | --- |
| Rakennuksen / tontin runko | Avoin WFS | `wfs` jos live-osuma |
| Julkisivun pituus (m) | WFS-särmä EPSG:3067 | `wfs` / `esimerkki` |
| Pintaosuudet (asfaltti…) | Valokuvat tai `pinnat.json` | `arvio` / `kayttaja` |
| Kaistan leveys (m) | `--kaistan-leveys` tai tunnistettu 1 m tikku | `kayttaja` / `mittatikku` |
| Pinta-ala (m²) | WFS-pituus × leveys | vain jos leveys on annettu/tunnistettu |
| Puut (kpl) | Kuvahaku | aina `arvio` |

**Leveyttä ei ole oletuksena.** Ilman sitä Excelissä m² = `EI LASKETTU` (punainen), mutta WFS-pituus ja lineaariset osuudet jäävät.

---

## WFS-liitäntä (pluggable)

Oletusketju (`--wfs auto`):

1. **Helsingin avoin WFS** — `https://kartta.hel.fi/ws/geoserver/avoindata/wfs`  
   Tasot: `avoindata:Rakennukset_alue`, `avoindata:Kiinteisto_alue`  
   Ei API-avainta. CQL `DWITHIN` / `INTERSECTS`, `srsName=EPSG:3067`.
2. **HSY avoin WFS** — `https://kartta.hsy.fi/geoserver/wfs`  
   Taso: `pks_rakennukset_paivittyva` (pääkaupunkiseutu).
3. **Stub** — `data/sample/rakennus_3067.geojson` + `tontti_3067.geojson`.

Osoite geokoodataan Nominatimilla (User-Agent asetettu) ja muunnetaan `EPSG:3067` (`pyproj`).

### Oma WFS-ote

```bash
vesivek mittaa --osoite "Oma kohde" --kuvat examples/kuvat --geojson /polku/ote.geojson --julkisivu etela
```

Tiedoston tulee olla **EPSG:3067** (easting, northing metreinä). GeoJSON merkitään ei-varmennetuksi, kunnes se on virallinen WFS-vienti.

### Uusi hakija koodissa

Toteuta `fetch_site(easting, northing, address) -> SiteFrame | None` (`vesivek/wfs/protocol.py`) ja rekisteröi se `vesivek/wfs/chain.py` live-listaan. Älä palauta keksittyä geometriaa “varmennettuna”.

`--wfs live` epäonnistuu, jos verkko tai avaimet estävät haun — metrejä ei täytetä stubilla hiljaa.

---

## Valinnainen `pinnat.json`

Jos automaattinen väriarvio ei riitä testissä, anna osuudet itse (`data/sample/pinnat.example.json`):

```bash
vesivek mittaa \
  --osoite "Pohjoinen Hesperiankatu 3, Helsinki" \
  --kuvat examples/kuvat \
  --julkisivu etela \
  --pinnat data/sample/pinnat.example.json
```

---

## Testit

```bash
pytest -q
```

---

## English summary

v1 is a **single-facade / strip** measurement tool. Building edges come from Finnish open WFS in **EPSG:3067**. Photos classify surfaces; they do **not** invent wall metres. Areas (m²) appear only when strip width is known (1 m stick in photos or `--kaistan-leveys`). Unverified values are labelled. No drainage pipes, no full stormwater plan.
