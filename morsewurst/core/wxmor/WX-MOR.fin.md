# WX-MOR

**Määritysversio:** 0.9
**Tekijä:** Kasperi Koski
**Kieli:** suomi  
**Tarkoitus:** kompakti sääsanoma morseen, radioon, tekstiviesteihin, tai ihmisten väliseen nopeaan sääviestintään

- [WX-MOR](#wx-mor)
  - [1. Johdanto](#1-johdanto)
    - [1.1. Tarkoitus](#11-tarkoitus)
    - [1.2. Perusperiaatteet](#12-perusperiaatteet)
    - [1.3. Oletusyksiköt](#13-oletusyksiköt)
  - [2. Sanoman yleisrakenne](#2-sanoman-yleisrakenne)
    - [2.1. Perusjärjestys](#21-perusjärjestys)
    - [2.2. Kenttien merkitys](#22-kenttien-merkitys)
    - [2.3. Minimimuoto](#23-minimimuoto)
    - [2.4. Suositeltu ydinsanoma](#24-suositeltu-ydinsanoma)
    - [2.5. Laajennettu sanoma](#25-laajennettu-sanoma)
    - [2.6. Kenttien järjestys ja joustavuus](#26-kenttien-järjestys-ja-joustavuus)
  - [3. Kentät](#3-kentät)
    - [3.1. Paikka `LOC`](#31-paikka-loc)
      - [3.1.1. Yleinen paikkakoodi](#311-yleinen-paikkakoodi)
      - [3.1.2. Tarkka lentoasema tai sääasema](#312-tarkka-lentoasema-tai-sääasema)
      - [3.1.3. Paikallisesti sovittu koodi](#313-paikallisesti-sovittu-koodi)
    - [3.2. Aika `TIME`](#32-aika-time)
      - [3.2.1. Ensisijainen aikamuoto](#321-ensisijainen-aikamuoto)
      - [3.2.2. Päivämäärällä laajennettu aikamuoto](#322-päivämäärällä-laajennettu-aikamuoto)
      - [3.2.3. Paikallinen aika](#323-paikallinen-aika)
    - [3.3. Lämpötila `TEMP`](#33-lämpötila-temp)
      - [3.3.1. Perusmuoto](#331-perusmuoto)
      - [3.3.2. Säännöt](#332-säännöt)
      - [3.3.3. Esimerkit](#333-esimerkit)
    - [3.4. Kastepiste `D`](#34-kastepiste-d)
      - [3.4.1. Perusmuoto](#341-perusmuoto)
      - [3.4.2. Säännöt](#342-säännöt)
      - [3.4.3. Esimerkit](#343-esimerkit)
    - [3.5. Sääilmiö ja säätila `WXSTATE`](#35-sääilmiö-ja-säätila-wxstate)
      - [3.5.1. Yleisperiaate](#351-yleisperiaate)
      - [3.5.2. Perusavainsanat](#352-perusavainsanat)
      - [3.5.3. Voimakkuusetuliitteet](#353-voimakkuusetuliitteet)
      - [3.5.4. Useat sääilmiöt](#354-useat-sääilmiöt)
      - [3.5.5. WXSTATE-koodien suositeltu järjestys](#355-wxstate-koodien-suositeltu-järjestys)
      - [3.5.6. NIL](#356-nil)
      - [3.5.7. Kompaktit sääaliaset](#357-kompaktit-sääaliaset)
        - [3.5.7.1. Käyttötarkoitus](#3571-käyttötarkoitus)
        - [3.5.7.2. Aliaslista](#3572-aliaslista)
        - [3.5.7.3. Kompaktit voimakkuusesimerkit](#3573-kompaktit-voimakkuusesimerkit)
        - [3.5.7.4. Suositus](#3574-suositus)
    - [3.6. Tuuli `WIND`](#36-tuuli-wind)
      - [3.6.1. Perusperiaate](#361-perusperiaate)
      - [3.6.2. Suunta ja nopeus](#362-suunta-ja-nopeus)
      - [3.6.3. Puuskat](#363-puuskat)
      - [3.6.4. Pelkkä nopeus](#364-pelkkä-nopeus)
      - [3.6.5. Vaihteleva tuuli](#365-vaihteleva-tuuli)
      - [3.6.6. Tyyni](#366-tyyni)
      - [3.6.7. Yksiköt](#367-yksiköt)
      - [3.6.8. Tarkka astesuunta](#368-tarkka-astesuunta)
      - [3.6.9. Virheelliset muodot](#369-virheelliset-muodot)
      - [3.6.10. Muodostussääntö](#3610-muodostussääntö)
    - [3.7. Pilvisyys `CLOUD`](#37-pilvisyys-cloud)
      - [3.7.1. Peruskoodit](#371-peruskoodit)
      - [3.7.2. Pilvikorkeus](#372-pilvikorkeus)
    - [3.8. Näkyvyys `VIS`](#38-näkyvyys-vis)
    - [3.9. Ilmanpaine `Q`](#39-ilmanpaine-q)
      - [3.9.1. Perusmuoto](#391-perusmuoto)
      - [3.9.2. Esimerkit](#392-esimerkit)
      - [3.9.3. Paineen kehitys](#393-paineen-kehitys)
    - [3.10. UV-indeksi `UV`](#310-uv-indeksi-uv)
      - [3.10.1. Perusmuoto](#3101-perusmuoto)
      - [3.10.2. Esimerkit](#3102-esimerkit)
    - [3.11. Suhteellinen kosteus `RH`](#311-suhteellinen-kosteus-rh)
      - [3.11.1. Perusmuoto](#3111-perusmuoto)
      - [3.11.2. Esimerkit](#3112-esimerkit)
    - [3.12. Sademäärä `RR`](#312-sademäärä-rr)
      - [3.12.1. Perusmuoto](#3121-perusmuoto)
      - [3.12.2. Esimerkit](#3122-esimerkit)
    - [3.13. Lumensyvyys `SD`](#313-lumensyvyys-sd)
    - [3.14. Tuore lumi `NS`](#314-tuore-lumi-ns)
    - [3.15. Vapaamuotoiset lisätiedot](#315-vapaamuotoiset-lisätiedot)
  - [4. Kenttien tunnistaminen](#4-kenttien-tunnistaminen)
  - [5. Sanoman muodostussäännöt](#5-sanoman-muodostussäännöt)
  - [6. Käyttöprofiilit](#6-käyttöprofiilit)
    - [6.1. Minimiprofiili](#61-minimiprofiili)
    - [6.2. Perusprofiili](#62-perusprofiili)
    - [6.3. Laaja profiili](#63-laaja-profiili)
    - [6.4. Kompakti profiili](#64-kompakti-profiili)
  - [7. Esimerkkisanomat](#7-esimerkkisanomat)
    - [7.1. Yksinkertainen sade](#71-yksinkertainen-sade)
    - [7.2. Kuiva ja pilvinen sää](#72-kuiva-ja-pilvinen-sää)
    - [7.3. Selkeä pakkassää](#73-selkeä-pakkassää)
    - [7.4. Lumisade](#74-lumisade)
    - [7.5. Voimakas lumisade ja puuskat](#75-voimakas-lumisade-ja-puuskat)
    - [7.6. Lumipyry](#76-lumipyry)
    - [7.7. Sumuinen nollakeli](#77-sumuinen-nollakeli)
    - [7.8. Liukkausvaroitus](#78-liukkausvaroitus)
    - [7.9. Hyvä näkyvyys](#79-hyvä-näkyvyys)
    - [7.10. Lumitiedot mukana](#710-lumitiedot-mukana)
    - [7.11. Kompakti sadeviesti](#711-kompakti-sadeviesti)
    - [7.12. Kompakti talviviesti](#712-kompakti-talviviesti)
    - [7.13. Korkea UV-indeksi](#713-korkea-uv-indeksi)
  - [8. Virheiden välttäminen](#8-virheiden-välttäminen)
    - [8.1. Älä käytä plus- tai miinusmerkkejä](#81-älä-käytä-plus--tai-miinusmerkkejä)
    - [8.2. Älä käytä kauttaviivaa lämpötilalle ja kastepisteelle](#82-älä-käytä-kauttaviivaa-lämpötilalle-ja-kastepisteelle)
    - [8.3. Älä käytä prosenttimerkkiä kosteudessa](#83-älä-käytä-prosenttimerkkiä-kosteudessa)
    - [8.4. Älä yhdistä lämpötilaa ja kastepistettä samaan kenttään](#84-älä-yhdistä-lämpötilaa-ja-kastepistettä-samaan-kenttään)
    - [8.5. Älä jätä WX-tunnistetta pois](#85-älä-jätä-wx-tunnistetta-pois)
  - [9. Pikasanasto](#9-pikasanasto)



---
## 1. Johdanto

### 1.1. Tarkoitus

WX-MOR on tiivis sääsanomamuoto, joka on suunniteltu erityisesti morsekäyttöön, mutta jota voidaan käyttää myös muussa lyhyessä tekstipohjaisessa sääviestinnässä.

WX-MORin tavoitteet:

- olla mahdollisimman universaali
- olla morseystävällinen
- olla ihmisluettava
- olla helposti opeteltava
- hyödyntää METAR-tyyppistä ajattelua
- toimia myös hyvin lyhyenä viestinä
- olla laajennettavissa ilman, että perusmuoto rikkoutuu

WX-MOR ei ole virallinen ilmailusääsanoma eikä korvaa METARia, TAFia, SYNOPia tai viranomaisen säävaroituksia.

---



### 1.2. Perusperiaatteet

1. Sanoma alkaa aina tunnisteella `WX`.
2. Tärkein tieto sijoitetaan alkuun.
3. Kenttiä voidaan jättää pois ilman paikkamerkkejä.
4. Kentät erotetaan yhdellä välilyönnillä.
5. Kaikki kirjoitetaan isoilla kirjaimilla.
6. Vain kirjaimet `A-Z`, numerot `0-9` ja välilyönti ovat sallittuja.
7. Erikoismerkkejä ei käytetä.
8. Plusmerkkiä ei käytetä.
9. Miinus ilmaistaan kirjaimella `M`.
10. Tuntematonta tietoa ei arvata.

Sallittu merkkijoukko:

```text
ABCDEFGHIJKLMNOPQRSTUVWXYZ 0123456789 SPACE
```

---

### 1.3. Oletusyksiköt

WX-MOR käyttää seuraavia oletusyksiköitä:

| Suure                | Oletusyksikkö                    |
| :------------------- | :------------------------------- |
| lämpötila            | celsius                          |
| kastepiste           | celsius                          |
| tuuli                | metriä sekunnissa                |
| näkyvyys             | metri                            |
| ilmanpaine           | hehtopascal                      |
| UV-indeksi           | UV-indeksiluku                   |
| sademäärä            | millimetri                       |
| suhteellinen kosteus | prosentti ilman prosenttimerkkiä |
| lumensyvyys          | senttimetri                      |
| tuore lumi           | senttimetri                      |
| aika                 | UTC                              |

---

## 2. Sanoman yleisrakenne

### 2.1. Perusjärjestys

Sanomassa käytetään seuraavaa perusjärjestystä:

```text
WX LOC TIME TEMP D WXSTATE WIND CLOUD VIS Q UV RH RR SD NS EXTRA
```

### 2.2. Kenttien merkitys

| Kenttä    | Merkitys                  |
| --------- | ------------------------- |
| `WX`      | sääsanoman tunniste       |
| `LOC`     | paikka                    |
| `TIME`    | havaintoaika              |
| `TEMP`    | lämpötila (T)             |
| `D`       | kastepiste                |
| `WXSTATE` | sääilmiö tai säätila      |
| `WIND`    | tuuli                     |
| `CLOUD`   | pilvisyys                 |
| `VIS`     | näkyvyys                  |
| `Q`       | ilmanpaine                |
| `UV`      | UV-indeksi                |
| `RH`      | suhteellinen kosteus      |
| `RR`      | sademäärä                 |
| `SD`      | lumensyvyys               |
| `NS`      | tuore lumi                |
| `EXTRA`   | vapaamuotoiset lisätiedot |

### 2.3. Minimimuoto

```text
WX LOC TIME TEMP WXSTATE
```

Esimerkki:

```text
WX HEL 1420Z T6 RAIN
```

### 2.4. Suositeltu ydinsanoma

```text
WX LOC TIME TEMP D WXSTATE WIND CLOUD Q
```

Esimerkki:

```text
WX HEL 1420Z T6 D4 RAIN SW4 OVC Q1008
```

UV-indeksi voidaan lisätä ydinsanoman loppuun ilmanpaineen jälkeen, jos tieto on saatavilla ja olennainen.

Esimerkki:

```text
WX HEL 1420Z T18 D9 NIL SW4 SCT Q1018 UV5
```

### 2.5. Laajennettu sanoma

```text
WX LOC TIME TEMP D WXSTATE WIND CLOUD VIS Q UV RH RR SD NS EXTRA
```

Esimerkki:

```text
WX HEL 1420Z T6 D4 RAIN SW4 SCT025 BKN050 V8000 Q1008 UV1 RH86 RR2
```

### 2.6. Kenttien järjestys ja joustavuus

WX-MORin suositeltu kenttäjärjestys on:

```text
WX LOC TIME TEMP D WXSTATE WIND CLOUD VIS Q UV RH RR SD NS EXTRA
```

Suositeltu järjestys on valittu sen mukaan, mitä ihminen yleensä haluaa tietää ensimmäisenä:

1. mikä viesti on kyseessä
2. missä sää havaitaan
3. milloin havainto on tehty
4. kuinka lämmin tai kylmä on
5. mikä kastepiste on
6. sataako tai onko muuta merkittävää säätä
7. kuinka tuulista on
8. millainen pilvisyys on
9. kuinka hyvä näkyvyys on
10. mikä ilmanpaine on
11. mikä UV-indeksi on, jos tieto on saatavilla ja olennainen
12. mitä täydentäviä tietoja on saatavilla

Kenttiä saa jättää pois. Tyhjiä paikkamerkkejä ei käytetä.

Koska useimmat kentät ovat tunnisteellisia, sanoma voidaan tarvittaessa ymmärtää myös silloin, kun osa kentistä on eri järjestyksessä. Yhteentoimivuuden vuoksi kentät kirjoitetaan suositellussa järjestyksessä.

---

## 3. Kentät

### 3.1. Paikka `LOC`

#### 3.1.1. Yleinen paikkakoodi

Paikkakoodina käytetään ensisijaisesti kolmikirjaimista koodia.

Jos paikalla on tunnettu IATA-koodi, sitä suositellaan käytettäväksi yleisenä paikkakoodina.

Esimerkkejä:

| Koodi | Paikka    |
| ----- | --------- |
| `HEL` | Helsinki  |
| `TKU` | Turku     |
| `TMP` | Tampere   |
| `OUL` | Oulu      |
| `RVN` | Rovaniemi |

#### 3.1.2. Tarkka lentoasema tai sääasema

Jos halutaan viitata tarkasti lentoasemaan tai viralliseen säähavaintoasemaan, voidaan käyttää nelikirjaimista ICAO-koodia.

Esimerkkejä:

| Koodi  | Paikka           |
| ------ | ---------------- |
| `EFHK` | Helsinki-Vantaa  |
| `EFTU` | Turku            |
| `EFTP` | Tampere-Pirkkala |
| `EFOU` | Oulu             |

#### 3.1.3. Paikallisesti sovittu koodi

Jos sopivaa virallista tai vakiintunutta koodia ei ole, voidaan käyttää paikallisesti sovittua 3–6 merkin koodia.

Esimerkkejä:

```text
KRUU
MAUNU
PATA
SALO
```

Saman paikan tulee käyttää aina samaa koodia.

---

### 3.2. Aika `TIME`

#### 3.2.1. Ensisijainen aikamuoto

Aika ilmoitetaan ensisijaisesti UTC-aikana muodossa:

```text
HHMMZ
```

Esimerkkejä:

| Koodi   | Merkitys  |
| ------- | --------- |
| `0915Z` | 09.15 UTC |
| `1420Z` | 14.20 UTC |
| `2305Z` | 23.05 UTC |

#### 3.2.2. Päivämäärällä laajennettu aikamuoto

Jos päivämäärä on olennainen, käytetään muotoa:

```text
DDHHMMZ
```

Esimerkki:

| Koodi     | Merkitys                          |
| --------- | --------------------------------- |
| `010005Z` | kuukauden 1. päivä klo 00.05 UTC  |
| `071230Z` | kuukauden 7. päivä klo 12.30 UTC  |
| `152359Z` | kuukauden 15. päivä klo 23.59 UTC |
| `201045Z` | kuukauden 20. päivä klo 10.45 UTC |
| `301815Z` | kuukauden 30. päivä klo 18.15 UTC |

#### 3.2.3. Paikallinen aika

Paikallista aikaa ei käytetä.

---

### 3.3. Lämpötila `TEMP`

#### 3.3.1. Perusmuoto

Lämpötila merkitään tunnisteella `T`.

```text
Tn
TMn
```

#### 3.3.2. Säännöt

* `T` tarkoittaa ilman lämpötilaa.
* Plusmerkkiä ei käytetä.
* Miinus ilmaistaan kirjaimella `M`.
* Lämpötila ilmoitetaan kokonaisina Celsius-asteina.
* Desimaaleja ei käytetä.

#### 3.3.3. Esimerkit

| Koodi  | Merkitys |
| ------ | -------- |
| `T6`   | +6 °C    |
| `T0`   | 0 °C     |
| `TM3`  | -3 °C    |
| `TM18` | -18 °C   |

### 3.4. Kastepiste `D`

#### 3.4.1. Perusmuoto

Kastepiste merkitään tunnisteella `D`.

```text
Dn
DMn
```

#### 3.4.2. Säännöt

* `D` tarkoittaa kastepistettä.
* Kastepiste kirjoitetaan soveltuvilta osin samalla tavalla kuin lämpötila.
* Kastepiste sijoitetaan välittömästi lämpötilan jälkeen omana kenttänään.
* Kastepiste erotetaan lämpötilasta välilyönnillä.
* Plusmerkkiä ei käytetä.
* Miinus ilmaistaan kirjaimella `M`.
* Kastepiste ilmoitetaan kokonaisina Celsius-asteina.
* Desimaaleja ei käytetä.

#### 3.4.3. Esimerkit

| Koodi  | Merkitys          |
| ------ | ----------------- |
| `D2`   | kastepiste +2 °C  |
| `D0`   | kastepiste 0 °C   |
| `DM4`  | kastepiste -4 °C  |
| `DM12` | kastepiste -12 °C |

---

### 3.5. Sääilmiö ja säätila `WXSTATE`

#### 3.5.1. Yleisperiaate

Sääilmiöt ilmaistaan ensisijaisesti ihmisluettavilla englanninkielisillä avainsanoilla.

Tämä tekee sanomasta kansainvälisesti helpommin ymmärrettävän kuin täysin koodattu METAR-tyyppinen muoto.

WXSTATE-kenttä sisältää sekä varsinaiset sääilmiöt että sääolosuhteet ja varoitustyyppiset. Erillistä varoituskenttää ei käytetä.

WXSTATE-kenttä voidaan jättää pois, jos sanomassa käytetään koodia `VOK`.

#### 3.5.2. Perusavainsanat

| Koodi     | Merkitys                         |
| --------- | -------------------------------- |
| `NIL`     | ei merkittävää sääilmiötä        |
| `RAIN`    | sade                             |
| `DRIZZLE` | tihku                            |
| `SNOW`    | lumi                             |
| `SLEET`   | räntä                            |
| `HAIL`    | rakeet                           |
| `SHOWER`  | kuuro                            |
| `THUNDER` | ukkonen                          |
| `FOG`     | sumu                             |
| `MIST`    | utu                              |
| `HAZE`    | auer tai sameus                  |
| `ICE`     | jäätävä olosuhde tai jäätyminen  |
| `SLIP`    | liukkaus                         |
| `BLIZZ`   | lumipyry                         |
| `FROST`   | huurre tai pakkanen maanpinnalla |
| `DRIFT`   | kinostava lumi                   |
| `FLOOD`   | tulva tai tulvariski             |
| `HEAT`    | helle tai kuumuus                |
| `COLD`    | erittäin kylmä sää               |
| `STORM`   | myrsky                           |
| `GALE`    | kova tuuli                       |

#### 3.5.3. Voimakkuusetuliitteet

Sääilmiön voimakkuutta voidaan tarkentaa etuliitteellä, jos halutaan korostaa poikkeuksellisen heikkoa tai voimakasta ilmiötä.

| Etuliite | Merkitys |
| -------- | -------- |
| `L`      | heikko   |
| `H`      | voimakas |

Jos etuliitettä ei käytetä, sääilmiö ilmaistaan neutraalisti ilman tarkkaa voimakkuusluokitusta.

WX-MORissa voimakkuusetuliitteitä `L` ja `H` saa käyttää vain alla lueteltujen WXSTATE-koodien kanssa.

| Koodi      | Merkitys                 |
| ---------- | ------------------------ |
| `LTHUNDER` | heikko ukkonen           |
| `HTHUNDER` | voimakas ukkonen         |
| `LSHOWER`  | heikko kuuro             |
| `HSHOWER`  | voimakas kuuro           |
| `LDRIZZLE` | heikko tihku             |
| `HDRIZZLE` | voimakas tihku           |
| `LRAIN`    | heikko sade              |
| `HRAIN`    | voimakas sade            |
| `LSLEET`   | heikko räntäsade         |
| `HSLEET`   | voimakas räntäsade       |
| `LSNOW`    | heikko lumisade          |
| `HSNOW`    | voimakas lumisade        |
| `LHAIL`    | heikko raesade           |
| `HHAIL`    | voimakas raesade         |
| `LBLIZZ`   | heikko lumipyry          |
| `HBLIZZ`   | voimakas lumipyry        |
| `LFOG`     | heikko sumu              |
| `HFOG`     | erittäin tiheä sumu      |
| `LMIST`    | heikko utu               |
| `HMIST`    | voimakas utu             |
| `LHAZE`    | heikko auer tai sameus   |
| `HHAZE`    | voimakas auer tai sameus |
| `LGALE`    | heikko kova tuuli        |
| `HGALE`    | erittäin kova tuuli      |
| `LSTORM`   | heikko myrsky            |
| `HSTORM`   | voimakas myrsky          |

Kaikki WXSTATE-koodit eivät tue voimakkuusetuliitteitä.

Voimakkuusetuliitteitä käytetään ensisijaisesti sateisiin, kuuroihin, ukkoseen, tuuleen ja näkyvyysilmiöihin.

Seuraavat koodit ovat luonteeltaan binaarisia tai tilakuvaavia, eikä niihin käytetä voimakkuusetuliitteitä:

`SLIP`, `FROST`, `COLD`, `HEAT`, `FLOOD`, `DRIFT`, `ICE`


#### 3.5.4. Useat sääilmiöt

Useita sääilmiöitä voidaan ilmoittaa peräkkäin.

Esimerkkejä:

```text
RAIN FOG
SNOW BLIZZ
THUNDER HRAIN
SLEET ICE
SNOW SLIP
```

#### 3.5.5. WXSTATE-koodien suositeltu järjestys

Jos WXSTATE-kentässä käytetään useita sääilmiöitä, ne kirjoitetaan seuraavassa järjestyksessä:

| Järjestys | Ryhmä                            | Koodit                                              |
| :-------: | -------------------------------- | --------------------------------------------------- |
|     1     | Ei merkittävää sääilmiötä        | `NIL`                                               |
|     2     | Ukkonen ja kuurotyyppi           | `THUNDER`, `SHOWER`                                 |
|     3     | Sade ja olomuoto                 | `DRIZZLE`, `RAIN`, `SLEET`, `SNOW`, `HAIL`, `BLIZZ` |
|     4     | Näkyvyysilmiöt                   | `FOG`, `MIST`, `HAZE`                               |
|     5     | Jää, liukkaus ja talviolosuhteet | `ICE`, `SLIP`, `FROST`, `DRIFT`                     |
|     6     | Tuuli- ja vaaraolosuhteet        | `GALE`, `STORM`, `FLOOD`, `HEAT`, `COLD`            |
|     7     | Tuntematon ilmiö                 | `UNKNOWN`                                           |

Järjestys on suositus sanomien yhtenäisyyden ja luettavuuden parantamiseksi. Se ei muuta koodien merkitystä.

Jos käytetään voimakkuusetuliitteitä, etuliitteellinen koodi sijoitetaan samaan ryhmään kuin sen peruskoodi. Esimerkiksi `HRAIN` sijoittuu samaan kohtaan kuin `RAIN` ja `HFOG` samaan kohtaan kuin `FOG`.

#### 3.5.6. NIL

`NIL` tarkoittaa, että merkittävää sääilmiötä ei ole.

`NIL` ei tarkoita automaattisesti:

* selkeää taivasta
* tyyntä säätä
* hyvää näkyvyyttä
* korkeaa ilmanpainetta

Esimerkki:

```text
WX HEL 1200Z T8 NIL BKN W3 Q1017
```

---

#### 3.5.7. Kompaktit sääaliaset

##### 3.5.7.1. Käyttötarkoitus

WX-MORin oletusprofiili käyttää ihmisluettavia sääsanoja kuten `RAIN` ja `SNOW`.

Kompaktissa esitystavassa voidaan käyttää METAR-tyylisiä aliaksia.

##### 3.5.7.2. Aliaslista

| Oletuskoodi | Kompakti muoto |
| ----------- | -------------- |
| `RAIN`      | `RA`           |
| `DRIZZLE`   | `DZ`           |
| `SNOW`      | `SN`           |
| `SLEET`     | `SL`           |
| `HAIL`      | `GR`           |
| `SHOWER`    | `SH`           |
| `THUNDER`   | `TS`           |
| `FOG`       | `FG`           |
| `MIST`      | `BR`           |
| `HAZE`      | `HZ`           |
| `ICE`       | `ICE`          |
| `SLIP`      | `SLP`          |
| `BLIZZ`     | `BLZ`          |
| `FROST`     | `FRS`          |
| `DRIFT`     | `DRS`          |
| `GALE`      | `GAL`          |
| `STORM`     | `STM`          |
| `FLOOD`     | `FLD`          |
| `HEAT`      | `HOT`          |
| `COLD`      | `CLD`          |

##### 3.5.7.3. Kompaktit voimakkuusesimerkit

| Ihmisluettava  | Kompakti muoto |
| -------------- | -------------- |
| `LRAIN`        | `LRA`          |
| `HRAIN`        | `HRA`          |
| `LDRIZZLE`     | `LDZ`          |
| `HDRIZZLE`     | `HDZ`          |
| `LSNOW`        | `LSN`          |
| `HSNOW`        | `HSN`          |
| `LSLEET`       | `LSL`          |
| `HSLEET`       | `HSL`          |
| `LHAIL`        | `LGR`          |
| `HHAIL`        | `HGR`          |
| `LBLIZZ`       | `LBLZ`         |
| `HBLIZZ`       | `HBLZ`         |
| `LFOG`         | `LFG`          |
| `HFOG`         | `HFG`          |
| `LMIST`        | `LBR`          |
| `HMIST`        | `HBR`          |
| `LHAZE`        | `LHZ`          |
| `HHAZE`        | `HHZ`          |
| `LGALE`        | `LGAL`         |
| `HGALE`        | `HGAL`         |
| `LSTORM`       | `LSTM`         |
| `HSTORM`       | `HSTM`         |
| `THUNDER RAIN` | `TSRA`         |
| `SHOWER RAIN`  | `SHRA`         |
| `SHOWER SNOW`  | `SHSN`         |

##### 3.5.7.4. Suositus

Kompaktissa muodossa voimakkuusetuliite `L` tai `H` liitetään kompaktin sääkoodin eteen. Yleiseen käyttöön suositellaan ihmisluettavia koodeja.

```text
RAIN
SNOW
FOG
ICE
SLIP
```

Kompaktissa esitystavassa voidaan käyttää kompakteja koodeja.

```text
RA
SN
FG
ICE
SLP
```

---

### 3.6. Tuuli `WIND`

#### 3.6.1. Perusperiaate

Tuuli ilmoitetaan ilman erillistä tunnistetta.

Tuulen oletusyksikkö on metriä sekunnissa. Yksikköä ei tarvitse ilmoittaa.

Tuuli esitetään muodossa:

```text
DIRss
DIRssGmm
ss
ssGmm
```

Missä:

* `DIR` = tuulen suunta kompassisuuntana: `N`, `NE`, `E`, `SE`, `S`, `SW`, `W`, `NW` tai `VRB`
* `ss` = keskituulen nopeus (0–99)
* `Gmm` = puuskan suurin nopeus (0–99)

#### 3.6.2. Suunta ja nopeus

Jos tuulen suunta tunnetaan, käytetään kompassisuuntaa.

```text
DIRss
DIRssGmm
```

Missä:

* `DIR` = tuulen suunta
* `ss` = keskituulen nopeus
* `Gmm` = puuskan suurin nopeus (jos ilmoitetaan)

Esimerkkejä:

| Koodi | Merkitys           |
| ----- | ------------------ |
| `N4`  | pohjoistuuli 4 m/s |
| `NE5` | koillistuuli 5 m/s |
| `S6`  | etelätuuli 6 m/s   |
| `W10` | länsituuli 10 m/s  |

#### 3.6.3. Puuskat

Puuskat ilmaistaan kirjaimella `G`, joka liitetään keskituulen nopeuden perään.

```text
DIRssGmm
ssGmm
```

Missä:

* `G` = puuskatunniste
* `mm` = puuskan suurin nopeus

Puuska-arvo on aina suurempi tai yhtä suuri kuin keskituulen nopeus.

Puuskat ilmoitetaan vain, jos ne ovat merkityksellisiä.

Esimerkit:

| Koodi    | Merkitys                           |
| -------- | ---------------------------------- |
| `SW5G10` | lounaistuuli 5 m/s, puuskat 10 m/s |
| `NW8G14` | luoteistuuli 8 m/s, puuskat 14 m/s |
| `6G12`   | tuuli 6 m/s, puuskat 12 m/s        |

#### 3.6.4. Pelkkä nopeus

Jos suuntaa ei tiedetä tai sitä ei haluta ilmoittaa:

```text
ss
ssGmm
```

Esimerkkejä:

| Koodi  | Merkitys                    |
| ------ | --------------------------- |
| `4`    | tuuli 4 m/s                 |
| `10`   | tuuli 10 m/s                |
| `6G12` | tuuli 6 m/s, puuskat 12 m/s |

#### 3.6.5. Vaihteleva tuuli

Jos tuulen suunta on vaihteleva, käytetään koodia `VRB`.

```text
VRB3
VRB5G9
```

#### 3.6.6. Tyyni

Tyyni ilmaistaan koodilla:

```text
CALM
```

Esimerkki:

```text
WX HEL 0900Z T2 NIL CALM SKC Q1020
```

#### 3.6.7. Yksiköt

Tuulen nopeus ilmoitetaan aina metreinä sekunnissa (m/s).

Yksikköä ei kirjoiteta tuulikenttään.

Väärin:

```text
SW5MPS
NW15KT
```

Oikein:

```text id="dhudqw"
SW5
NW8
```

Jos lähdetieto on muissa yksiköissä, se muunnetaan metreiksi sekunnissa ennen WX-MOR-sanoman muodostamista.

Tuulen nopeus voidaan tarvittaessa ilmoittaa alkuperäisessä yksikössä `EXTRA`-kentässä vapaamuotoisesti, esimerkiksi:

```text
WND15KT
WNDKTG21KT
```


#### 3.6.8. Tarkka astesuunta

WX-MORin tuulikentässä ei käytetä astemuotoista tuulensuuntaa.

Jos tarkka astesuunta on tarpeen säilyttää, se voidaan ilmoittaa `EXTRA`-kentässä sanoman lopussa.

Esimerkki:

```text
WX HEL 1420Z T6 D4 RAIN SW5 OVC Q1008 WD230
```


#### 3.6.9. Virheelliset muodot

Tuulikenttää ei saa kirjoittaa asteina tai ilman selkeää rakennetta.

Väärin:

```text
2305
SW
VRB
5MPS
15KT
```

Oikein:

```text
SW5
SW5G10
4
6G11
VRB3
VRB5G9
```

#### 3.6.10. Muodostussääntö

Jos tuulitieto ilmoitetaan, tuulikentässä on aina annettava vähintään tuulen nopeus.

```text
ss
```

Jos tuulen suunta tunnetaan, se lisätään nopeuden eteen:

```text
DIRss
```

Jos puuskat tunnetaan ja ovat merkityksellisiä, ne lisätään nopeuden perään:

```text
DIRssGmm
ssGmm
```

Missä:

* `DIR` = tuulen suunta (valinnainen)
* `ss` = tuulen nopeus (pakollinen, jos tuulikenttä käytetään)
* `Gmm` = puuskan suurin nopeus (valinnainen)


---

### 3.7. Pilvisyys `CLOUD`

Pilvisyyskenttiä voidaan ilmoittaa yksi tai useampia. Jos pilvikerroksia ilmoitetaan useampia, ne kirjoitetaan peräkkäin välilyönneillä erotettuina matalimmasta korkeimpaan.

Pilvisyyttä ei tarvitse ilmoittaa, jos sanomassa käytetään koodia `VOK`. Muulloin pilvisyys on valinnainen.

#### 3.7.1. Peruskoodit

Pilvisyydessä käytetään METARista tuttuja lyhenteitä.

| Koodi | Merkitys                                |
| ----- | --------------------------------------- |
| `SKC` | selkeää                                 |
| `FEW` | vähän pilviä                            |
| `SCT` | hajanaisia pilviä tai puolipilvistä     |
| `BKN` | runsaasti pilviä                        |
| `OVC` | täysin pilvistä                         |
| `VV`  | pystynäkyvyys, taivaan rakenne ei erotu |

#### 3.7.2. Pilvikorkeus

Pilvikorkeus voidaan lisätä pilvikoodiin METAR-tyylisesti kolminumeroisena lukuna.

Luku tarkoittaa satoja jalkoja.

| Koodi    | Merkitys                          |
| -------- | --------------------------------- |
| `FEW025` | vähän pilviä, alaraja 2500 ft     |
| `BKN012` | runsaasti pilviä, alaraja 1200 ft |
| `OVC006` | pilvistä, alaraja 600 ft          |

Pilvikorkeutta ei tarvitse ilmoittaa.

Esimerkkejä

```text
SKC
FEW025
SCT014 BKN021
FEW020 SCT050 BKN090
SCT014 BKN021 BKN030
```

---

### 3.8. Näkyvyys `VIS`

Näkyvyys ilmaistaan metreinä tunnisteella `V`.

```text
Vn
```

Arvo `n` tarkoittaa näkyvyyttä metreinä. Etunollia ei käytetä.

Jos näkyvyys on 9999 metriä tai parempi, käytetään koodia:

```text
VOK
```

`VOK` tarkoittaa hyvää näkyvyyttä. Perusmuodossa se tarkoittaa, että näkyvyys on 9999 metriä tai parempi.

`VOK` voidaan antaa, kun kaikki seuraavat ehdot täyttyvät:

- näkyvyys on vähintään 10 km
- merkittäviä sääilmiöitä kuten sadetta, lunta tai sumua ei esiinny
- merkittäviä matalia pilviä ei esiinny

Kun kaikki yllä mainitut ehdot täyttyvät, tilanne voidaan esittää pelkällä koodilla `VOK`, eikä sääilmiötä tai pilvisyyttä tarvitse ilmoittaa erillisinä kenttinä.

| Koodi   | Merkitys        |
| ------- | --------------- |
| `V500`  | näkyvyys 500 m  |
| `V1000` | näkyvyys 1000 m |
| `V3000` | näkyvyys 3000 m |
| `V8000` | näkyvyys 8000 m |
| `VOK`   | hyvä näkyvyys   |


---

### 3.9. Ilmanpaine `Q`

#### 3.9.1. Perusmuoto

Ilmanpaine ilmaistaan tunnisteella `Q`.

```text
Qnnnn
```

Arvo annetaan hehtopascaleina (hPa) kiinteästi nelinumeroisena lukuna. Alle 1000 hPa arvoissa käytetään etunollaa.

#### 3.9.2. Esimerkit

| Koodi   | Merkitys |
| ------- | -------- |
| `Q1013` | 1013 hPa |
| `Q0998` | 998 hPa  |
| `Q1026` | 1026 hPa |

#### 3.9.3. Paineen kehitys

Ilmanpaineen kehitys voidaan ilmaista lisäkoodilla, joka kirjoitetaan ilmanpaineen jälkeen välilyönnillä erotettuna.

| Koodi | Merkitys     |
| ----- | ------------ |
| `QR`  | paine nousee |
| `QF`  | paine laskee |
| `QS`  | paine vakaa  |

Esimerkki:

```text
Q1004 QF
Q0989 QR
Q1012 QS
```

---

### 3.10. UV-indeksi `UV`

#### 3.10.1. Perusmuoto

UV-indeksi ilmaistaan tunnisteella `UV`.

```text
UVn
```

Arvo `n` on UV-indeksin kokonaislukuarvo. Desimaaleja ei käytetä.

#### 3.10.2. Esimerkit

| Koodi | Merkitys     |
| ----- | ------------ |
| `UV0` | UV-indeksi 0 |
| `UV2` | UV-indeksi 2 |
| `UV5` | UV-indeksi 5 |
| `UV8` | UV-indeksi 8 |

---

### 3.11. Suhteellinen kosteus `RH`

#### 3.11.1. Perusmuoto

Suhteellinen kosteus ilmaistaan tunnisteella `RH`.

```text
RHn
```

#### 3.11.2. Esimerkit

| Koodi  | Merkitys                  |
| ------ | ------------------------- |
| `RH76` | suhteellinen kosteus 76 % |
| `RH92` | suhteellinen kosteus 92 % |

---

### 3.12. Sademäärä `RR`

#### 3.12.1. Perusmuoto

Sademäärä ilmaistaan tunnisteella `RR`.

```text
RRn
```

Arvo annetaan millimetreinä ja se vastaa kertymää viimeisen 1 tunnin aikana.

Sademäärä sisältää kaiken sulaneen sateen (vesi, lumi, räntä).

#### 3.12.2. Esimerkit

| Koodi  | Merkitys      |
| ------ | ------------- |
| `RR1`  | 1 mm sadetta  |
| `RR5`  | 5 mm sadetta  |
| `RR12` | 12 mm sadetta |

---

### 3.13. Lumensyvyys `SD`

Lumensyvyys ilmaistaan tunnisteella `SD`.

```text
SDn
```

Arvo annetaan senttimetreinä ja se kuvaa maassa olevan lumen kokonaismäärää havaintohetkellä.

| Koodi  | Merkitys          |
| ------ | ----------------- |
| `SD5`  | lumensyvyys 5 cm  |
| `SD18` | lumensyvyys 18 cm |
| `SD42` | lumensyvyys 42 cm |


### 3.14. Tuore lumi `NS`

Tuore lumi ilmaistaan tunnisteella `NS`.

```text
NSn
```

Arvo annetaan senttimetreinä ja se kuvaa uuden lumen kertymää viimeisen 6 tunnin aikana.

| Koodi  | Merkitys                                    |
| ------ | ------------------------------------------- |
| `NS1`  | 1 cm uutta lunta viimeisen 6 tunnin aikana  |
| `NS4`  | 4 cm uutta lunta viimeisen 6 tunnin aikana  |
| `NS12` | 12 cm uutta lunta viimeisen 6 tunnin aikana |


---


### 3.15. Vapaamuotoiset lisätiedot

EXTRA-kenttään sijoitetaan sellainen sääsanomaan liittyvä tieto, jota ei ole määritelty muissa kentissä tai koodeissa.

Kenttää käytetään täydentävään ja tarkentavaan informaatioon, joka on tilanteen kannalta merkityksellistä, mutta ei kuulu varsinaiseen perusformaattiin.

EXTRA-kentässä voidaan ilmoittaa esimerkiksi:

- tuulen suunta asteina (`WD230`)
- alkuperäinen tuulen nopeus ja yksikkö (`WND15KT`, `WNDKTG21KT`)
- paikallisia havaintoja (`ROADICE`, `SEAFOG`)
- muita yksiselitteisiä lisätietoja

EXTRA-kentän sisältö kirjoitetaan yksiselitteisinä tunnisteina ilman erikoismerkkejä. Kentän sisältö ei saa rikkoa sanoman tulkintaa eikä olla ristiriidassa muiden kenttien kanssa.

---


## 4. Kenttien tunnistaminen

| Kenttätyyppi | Tunnistus                                                                                                    |
| ------------ | ------------------------------------------------------------------------------------------------------------ |
| sanoman alku | `WX`                                                                                                         |
| paikka       | yleensä toinen kenttä                                                                                        |
| aika         | päättyy `Z`                                                                                                  |
| lämpötila    | alkaa `T`                                                                                                    |
| kastepiste   | alkaa `D`                                                                                                    |
| sääilmiö     | sääsanaston mukainen avainsana tai alias                                                                     |
| tuuli        | `CALM`, pelkkä nopeus, `VRB` + nopeus, tai ilmansuunta + nopeus (`N4`, `NE5`, `SW8G14`)                      |
| pilvisyys    | `SKC`, `FEW`, `SCT`, `BKN`, `OVC`, `VV`; useita peräkkäin: `FEW025`, `SCT014 BKN021`, `SCT014 BKN021 BKN030` |
| näkyvyys     | `Vn` tai `VOK`                                                                                               |
| ilmanpaine   | alkaa `Q`                                                                                                    |
| UV-indeksi   | alkaa `UV`                                                                                                   |
| kosteus      | alkaa `RH`                                                                                                   |
| sademäärä    | alkaa `RR`                                                                                                   |
| lumensyvyys  | alkaa `SD`                                                                                                   |
| tuore lumi   | alkaa `NS`                                                                                                   |
| lisätiedot   | muut tunnisteelliset tai sovitut kentät sanoman lopussa                                                      |

---


## 5. Sanoman muodostussäännöt

1. Sanoman ensimmäinen kenttä on aina `WX`.
2. Toinen kenttä on paikka.
3. Kolmas kenttä on aika.
4. Aika ilmoitetaan UTC-muodossa ja se sijoitetaan ennen lämpötilaa.
5. Lämpötila sijoitetaan ennen kastepistettä.
6. Kastepiste sijoitetaan ennen sääilmiötä.
7. Sääilmiö sijoitetaan ennen tuulta.
8. Tuuli sijoitetaan ennen pilvisyyttä.
9. Pilvisyys sijoitetaan ennen näkyvyyttä. Jos pilvikerroksia on useita, ne kirjoitetaan peräkkäin alimmasta korkeimpaan.
10. Näkyvyys sijoitetaan ennen ilmanpainetta.
11. Ilmanpaine sijoitetaan ennen UV-indeksiä ja muita täydentäviä havaintoja.
12. UV-indeksi sijoitetaan ennen suhteellista kosteutta, jos se ilmoitetaan.
13. Suhteellinen kosteus sijoitetaan ennen sademäärää.
14. Sademäärä sijoitetaan ennen lumensyvyyttä.
15. Lumensyvyys sijoitetaan ennen tuoretta lunta.
16. Tuore lumi sijoitetaan ennen lisätietoja.
17. Lisätiedot (`EXTRA`) sijoitetaan aina viimeiseksi.
18. Kenttiä saa jättää pois.
19. Tyhjiä kenttiä ei merkitä.
20. Tuntematonta tietoa ei arvata.
21. Kaikkien käytettyjen koodien merkitys tulee olla osapuolille tuttu.
22. Sama yhteisö tai järjestelmä käyttää aina samoja paikkakoodeja.

---


## 6. Käyttöprofiilit

Käyttöprofiilit kuvaavat WX-MOR-sanoman tavallisia laajuuksia eri käyttötarkoituksiin.

Profiilit eivät ole ainoita sallittuja sanomamuotoja. Kenttiä saa jättää pois, jos tietoa ei ole tai sitä ei haluta ilmoittaa.

Jos kenttä ilmoitetaan, se kirjoitetaan tämän määrityksen mukaisessa muodossa ja sanoman muodostussääntöjen mukaisessa järjestyksessä.


### 6.1. Minimiprofiili

```text
WX LOC TIME TEMP WXSTATE
```

Esimerkit:

```text
WX HEL 1420Z T6 RAIN
WX TKU 0915Z TM3 NIL
WX OUL 1830Z T2 FOG
```


### 6.2. Perusprofiili

```text
WX LOC TIME TEMP D WXSTATE WIND CLOUD Q
```

Esimerkit:

```text
WX HEL 1420Z T6 D4 RAIN SW4 OVC Q1008
WX TKU 0915Z TM3 DM5 NIL W3 SCT Q1015
WX OUL 1830Z T2 DM1 FOG N5 BKN Q1002
```

UV-indeksi voidaan lisätä perusprofiiliin ilmanpaineen jälkeen, jos se on olennainen.

Esimerkit:

```
WX HEL 1420Z T18 D9 NIL SW4 SCT Q1018 UV5
WX TKU 1200Z T22 D11 NIL SE3 FEW Q1016 UV6
WX OUL 1100Z T16 D8 NIL W4 SCT Q1019 UV4
```


### 6.3. Laaja profiili

```text
WX LOC TIME TEMP D WXSTATE WIND CLOUD VIS Q UV RH RR SD NS EXTRA
```

Esimerkit:

```text
WX HEL 1420Z T6 D4 RAIN SW4 SCT025 BKN050 V8000 Q1008 UV1 RH86 RR2
WX TKU 0915Z TM3 DM5 NIL W3 SCT V8000 Q1015 UV0 RH78
WX OUL 1830Z T2 DM1 SNOW N5 BKN V3000 Q1002 UV0 RH92 SD12 NS3
```

### 6.4. Kompakti profiili

```text
WX LOC TIME TEMP WXSTATE WIND CLOUD VIS Q UV EXTRA
```

Esimerkit:

```text
WX HEL 1420Z T6 RA SW4 OVC V10 Q1008
WX TKU 0915Z TM3 NIL W3 SCT V8 Q1015
WX OUL 1830Z T2 SN N5 BKN V3 Q1002
```

---

## 7. Esimerkkisanomat

Seuraavassa esitetään esimerkkisanomia eri kategorioista. Kussakin kategoriassa on kolme esimerkkiä, jokainen omalla rivillään.

### 7.1. Yksinkertainen sade

```text
WX HEL 1420Z T6 D4 RAIN SW4 OVC V8000 Q1008
WX TKU 1010Z T7 D5 RAIN S5 SCT V6000 Q1006
WX TMP 1530Z T5 D3 RAIN SE4 BKN V5000 Q1009
```

### 7.2. Kuiva ja pilvinen sää

```text
WX HEL 1200Z T8 D2 NIL W3 BKN VOK Q1017 UV1
WX TKU 1400Z T10 D4 NIL SW4 SCT VOK Q1015 UV2
WX OUL 0900Z T6 D1 NIL N2 OVC V9000 Q1018 UV1
```

### 7.3. Selkeä pakkassää

```text
WX RVN 0900Z TM18 DM20 NIL CALM SKC VOK Q1028
WX OUL 0700Z TM12 DM15 NIL N1 SKC VOK Q1030
WX KTT 0600Z TM20 DM24 NIL CALM SKC V7000 Q1025
```

### 7.4. Lumisade

```text
WX OUL 0715Z TM8 DM10 SNOW NE7 OVC V3000 Q0994
WX RVN 0830Z TM6 DM8 SNOW N5 BKN V4000 Q0998
WX KEM 0600Z TM5 DM7 SNOW NW6 OVC V2000 Q1001
```

### 7.5. Voimakas lumisade ja puuskat

```text
WX OUL 0715Z TM8 DM10 HSNOW NE7G12 OVC V1500 Q0994
WX RVN 0830Z TM6 DM9 HSNOW N6G11 BKN V2000 Q0998
WX KEM 0600Z TM5 DM8 HSNOW NW7G13 OVC V1200 Q1001
```

### 7.6. Lumipyry

```text
WX OUL 0715Z TM8 DM11 HSNOW BLIZZ NE9G16 OVC V500 Q0989
WX RVN 0830Z TM7 DM10 HSNOW BLIZZ N8G15 BKN V800 Q0992
WX KEM 0600Z TM6 DM9 HSNOW BLIZZ NW9G17 OVC V600 Q0995
```

### 7.7. Sumuinen nollakeli

```text
WX TKU 0830Z T0 DM1 FOG CALM OVC V300 Q1011
WX HEL 0600Z T1 D0 FOG CALM SCT V800 Q1013
WX TMP 0700Z T0 DM1 FOG CALM BKN V500 Q1010
```

### 7.8. Liukkausvaroitus

```text
WX HEL 0545Z TM1 DM2 ICE SLIP E3 OVC V5000 Q1002
WX TKU 0600Z T0 DM1 ICE SLIP SE2 SCT V6000 Q1005
WX OUL 0700Z TM2 DM4 ICE SLIP N3 BKN V4000 Q1000
```

### 7.9. Hyvä näkyvyys

```text
WX EFHK 1810Z T2 D0 NIL SW5 SCT025 BKN080 VOK Q1019 UV0 RH79
WX EFTU 1700Z T3 D1 NIL W4 FEW VOK Q1020 UV1 RH70
WX EFTP 1600Z T4 D2 NIL S3 SCT VOK Q1018 UV1 RH65
```

### 7.10. Lumitiedot mukana

```text
WX OUL 0600Z TM6 DM8 SNOW N4 OVC V3000 Q1000 SD22 NS4
WX RVN 0700Z TM8 DM11 SNOW N5 BKN V2000 Q0998 SD18 NS3
WX KEM 0800Z TM5 DM7 SNOW NW6 OVC V2500 Q1002 SD25 NS5
```

Esimerkeissä `NS` kuvaa uuden lumen määrää viimeisen 6 tunnin aikana.

### 7.11. Kompakti sadeviesti

```text
WX HEL 1420Z T6 D4 RA SW4 OVC V8000 Q1008
WX TKU 1010Z T7 D5 RA S5 SCT V6000 Q1006
WX TMP 1530Z T5 D3 RA SE4 BKN V5000 Q1009
```

### 7.12. Kompakti talviviesti

```text
WX OUL 0715Z TM8 DM10 HSN NE7G12 OVC V1500 Q0994 SD18 NS4
WX RVN 0830Z TM6 DM9 HSN N6G11 BKN V2000 Q0998 SD15 NS3
WX KEM 0600Z TM5 DM8 HSN NW7G13 OVC V1200 Q1001 SD20 NS5
```

### 7.13. Korkea UV-indeksi

```text
WX HEL 1100Z T24 D12 NIL S3 SKC VOK Q1018 UV6
WX TKU 1200Z T26 D14 NIL SW4 FEW VOK Q1016 UV7
WX TMP 1300Z T25 D13 NIL CALM SCT VOK Q1017 UV5
```

---

## 8. Virheiden välttäminen

### 8.1. Älä käytä plus- tai miinusmerkkejä

Väärin:

```text
WX HEL 1420Z +6 RAIN
```

Oikein:

```text
WX HEL 1420Z T6 RAIN
```

Väärin:

```text
WX HEL 1420Z T-6 SNOW
```

Oikein:

```text
WX HEL 1420Z TM6 SNOW
```

### 8.2. Älä käytä kauttaviivaa lämpötilalle ja kastepisteelle

Väärin:

```text
WX HEL 1420Z T6/D4 RAIN
```

Oikein:

```text
WX HEL 1420Z T6 D4 RAIN
```

### 8.3. Älä käytä prosenttimerkkiä kosteudessa

Väärin:

```text
RH86%
```

Oikein:

```text
RH86
```

### 8.4. Älä yhdistä lämpötilaa ja kastepistettä samaan kenttään

Väärin:

```text
WX HEL 1420Z T6D4 RAIN
```

### 8.5. Älä jätä WX-tunnistetta pois

Väärin:

```text
HEL 1420Z T6 RAIN
```

Oikein:

```text
WX HEL 1420Z T6 RAIN
```

---

## 9. Pikasanasto

| Koodi     | Merkitys                                      |
| --------- | --------------------------------------------- |
| `BKN`     | runsaasti pilviä                              |
| `BLIZZ`   | lumipyry                                      |
| `BLZ`     | lumipyry (kompakti)                           |
| `BR`      | utu (kompakti)                                |
| `CALM`    | tyyni                                         |
| `CLOUD`   | pilvisyyskenttä; yksi tai useampi pilvikerros |
| `COLD`    | erittäin kylmä                                |
| `D`       | kastepiste                                    |
| `DRIZZLE` | tihku                                         |
| `DRIFT`   | kinostava lumi                                |
| `DRS`     | kinostava lumi (kompakti)                     |
| `DZ`      | tihku (kompakti)                              |
| `E`       | itä                                           |
| `EXTRA`   | vapaamuotoiset lisätiedot                     |
| `FEW`     | vähän pilviä                                  |
| `FG`      | sumu (kompakti)                               |
| `FLOOD`   | tulva                                         |
| `FOG`     | sumu                                          |
| `FROST`   | huurre tai pintapakkanen                      |
| `FRS`     | huurre (kompakti)                             |
| `G`       | puuska                                        |
| `GALE`    | kova tuuli                                    |
| `GR`      | rakeet (kompakti)                             |
| `H`       | voimakas                                      |
| `HAIL`    | rakeet                                        |
| `HAZE`    | auer                                          |
| `HEAT`    | kuumuus                                       |
| `HZ`      | auer (kompakti)                               |
| `ICE`     | jäätävä olosuhde                              |
| `L`       | heikko                                        |
| `LOC`     | paikka                                        |
| `M`       | miinusmerkintä                                |
| `MIST`    | utu                                           |
| `N`       | pohjoinen                                     |
| `NE`      | koillinen                                     |
| `NIL`     | ei merkittävää sääilmiötä                     |
| `NS`      | tuore lumi                                    |
| `NW`      | luode                                         |
| `OVC`     | pilvistä                                      |
| `Q`       | ilmanpaine                                    |
| `RA`      | sade (kompakti)                               |
| `RAIN`    | sade                                          |
| `RH`      | suhteellinen kosteus                          |
| `RR`      | sademäärä                                     |
| `S`       | etelä                                         |
| `SC`      | hajanaisia pilviä (kompakti)                  |
| `SCT`     | hajanaisia pilviä                             |
| `SD`      | lumensyvyys                                   |
| `SE`      | kaakko                                        |
| `SH`      | kuuro (kompakti)                              |
| `SHOWER`  | kuuro                                         |
| `SKC`     | selkeää                                       |
| `SL`      | räntä (kompakti)                              |
| `SLEET`   | räntä                                         |
| `SLIP`    | liukkaus                                      |
| `SLP`     | liukkaus (kompakti)                           |
| `SN`      | lumi (kompakti)                               |
| `SNOW`    | lumi                                          |
| `STORM`   | myrsky                                        |
| `SW`      | lounas                                        |
| `T`       | lämpötila                                     |
| `TEMP`    | lämpötilakenttä                               |
| `THUNDER` | ukkonen                                       |
| `TIME`    | aika                                          |
| `TS`      | ukkonen (kompakti)                            |
| `UV`      | UV-indeksi                                    |
| `V`       | näkyvyys                                      |
| `VIS`     | näkyvyyskenttä                                |
| `VOK`     | hyvä näkyvyys                                 |
| `VRB`     | vaihteleva tuuli                              |
| `VV`      | pystynäkyvyys                                 |
| `W`       | länsi                                         |
| `WIND`    | tuulikenttä                                   |
| `WX`      | sääsanoman tunniste                           |
| `WXSTATE` | sääilmiö- tai säätilakenttä                   |

---
