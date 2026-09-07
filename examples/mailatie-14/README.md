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
