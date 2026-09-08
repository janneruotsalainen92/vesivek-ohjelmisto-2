# Mailatie 14, Vantaa — harjoitus (pohjoinen kaista)

Ei virallinen tuote. Esimerkki FM-007-tyylisestä **seinä → reuna** -kaistasta.

## Ajo (live HSY + Vantaa tontti + orto)

```bash
vesivek julkisivut --osoite "Mailatie 14, Vantaa" --wfs live

vesivek mittaa \
  --osoite "Mailatie 14, Vantaa" \
  --julkisivu pohjoinen \
  --pinnat examples/mailatie-14/pinnat.json \
  --wfs live \
  --kuvat examples/mailatie-14
```

- WFS-pohjoisseinä on HSY-geometriaa (harjoituksessa ~53.86 m).
- Kaista leikataan Vantaan `kiinteisto:kiinteisto` -tonttiin (ei arvattua leveyttä).
- `pinnat.json` jakaa kaistan **leveyssuunnassa** valokuvien perusteella. Lukuja ei ole kopioitu FM-007-lukoista.
- Peite `autot` → pinta-alat **EI VARMENNETTU**.
- Päätylaatta ilman mitattua palaa → **EI LASKETTU** / ARVIO.

Jos live-WFS estyy:

```bash
vesivek mittaa --osoite "Mailatie 14, Vantaa" --julkisivu pohjoinen \
  --pinnat examples/mailatie-14/pinnat.json --wfs stub --kaistan-leveys 6.0
```

Stub käyttää `data/sample/` Helsinki-geometriaa — **ei Mailatien metrejä**.

## Kuvat

Pudota maastokuvat `A.jpg` … `F.jpg` ja `E-paaty.jpg` tähän kansioon (`examples/mailatie-14/`), jos haluat HSV-luokituksen `pinnat.json`:n sijaan.

## Live-ajo vs FM-007 (suunta, ei kopio)

HSY + Vantaan tontti, pohjoinen, `pinnat.json` (peite=autot). Kaista yhteensä **320.51 m²**, keskimääräinen leveys **5.84 m** (tontin geometria).

| Luokka | Tämä ajo | FM-007 lukko | Huomio |
| --- | ---: | ---: | --- |
| WFS N-seinä | 53.86 m | 53.86 m | sama, lukittu |
| Kaista yht. | 320.51 m² | ~326.5 m² | tonttileikkaus |
| asfaltti | 200.68 m² EI VARMENNETTU | ~223.14 EI VARMENNETTU | sama suunta |
| seinänvierus | 48.55 m² EI VARMENNETTU | ~36.48 | leveämpi osuus kuvista |
| sepeli | 51.79 m² EI VARMENNETTU | ~35.97 | leveämpi osuus kuvista |
| rajapuska | 19.50 m² + 53.86 m viiva | ~28.67 + 53.86 m | viiva täsmää |
| päätylaatta | EI LASKETTU / ARVIO | ARVIO ~2.24 | palaa ei mitattu |

Lukuja ei ole pakotettu FM-007:ään. Autot → EI VARMENNETTU. Tulosteet: `tulokset/mailatie-14-vantaa-*/`.
