# Morsewurst Keyer

**Suunnittelu:** Kasperi Koski

**Sisältö:** Morsewurst (Python-ohjelma), Arduino-koodi ja 3D-tulostettava kotelo

## Lyhyt kuvaus

**Morsewurst Keyer** on ESP32-S3-pohjainen morseharjoituslaite, joka lukee suoraa morseavainta tai iambic-paddlea, tuottaa kuulokkeisiin sidetone-äänen, näyttää perustiedot OLED-näytöllä ja lähettää raakaa ajoitustelemetriaa tietokoneella ajettavalle Morsewurstille.

Laite voi toimia myös USB-näppäimistönä. Tällöin se kirjoittaa puretut merkit suoraan tietokoneelle. Jos USB-näppäimistötila on käytössä, tietokoneessa kannattaa käyttää suomalaista näppäimistöasettelua, koska osa erikoismerkeistä lähetetään suomalaisen näppäimistön näppäinyhdistelmillä.

Ohjelmakoodi ladataan Arduino IDE:llä tiedostosta:

```text
morsewurst_keyer_\*_\*.ino
```

3D-tulostettava kotelo on tiedosto:

```text
Morsewurst_keyer.stl
```

Sopiva mikrokontrolleri tähän versioon on:

```text
Adafruit ESP32-S3 Feather with STEMMA QT 8MB
https://partco.fi/tuote/adafruit-esp32-s3-feather-with-stemma-qt-8mb-329
```

## Keskeiset ominaisuudet

- ESP32-S3-pohjainen morseharjoituslaite
- Suoran avaimen tuki
- Iambic-paddlen tuki
- Kuulokkeisiin tuleva sidetone
- OLED-näyttö laitteen asetuksille ja tilatiedoille
- Painonapillinen rotaatioenkooderi asetusten säätöön
- USB CDC Serial -telemetria Morsewurstille
- USB HID Keyboard -tila merkkien kirjoittamiseen tietokoneelle
- Ajoitustiedot lähetetään JSON-muodossa
- Mittaus käyttää mikrosekuntiresoluutiota, mutta käytännön tarkkuus on realistisesti noin 50-200 mikrosekuntia hyvissä olosuhteissa

## Tarvittavat osat

### Elektroniikka

- Adafruit ESP32-S3 Feather with STEMMA QT 8MB tai vastaava ESP32-S3-kortti, jossa on native USB
- 128x64 I2C OLED -näyttö, esimerkiksi SSD1306- tai SH1106-yhteensopiva
- KY-040 tai vastaava painonapillinen rotaatioenkooderi
- 3,5 mm stereoliitin iambic-paddlelle
- 3,5 mm stereoliitin suoralle avaimelle
- 3,5 mm stereokuulokeliitin, mieluiten kytkimellinen malli
- 10 kΩ logaritminen monopotentiometri äänenvoimakkuudelle
- 2 kpl 1 kΩ metallikalvovastuksia
- 1 kpl 2,2 kΩ metallikalvovastus
- Johtoa, mieluiten useampaa väriä
- Tarvittaessa Wago-liittimiä, maadoituskisko tai muu tapa yhdistää GND-johdot siististi

### Työkalut ja mekaaniset osat

- Juotoskolvi
- Tina
- Johtokuorimet
- Sivuleikkurit
- Pieni porakone tai käsipora reikien siistimiseen
- 3D-tulostin
- PETG-filamentti
- Ruuvit tai muut kiinnikkeet kotelon mukaan

## Ennen lopullista rakentamista

Rakenne kannattaa ensin testata kytkentälaudalla. Kun avaimet, näyttö, rotaatioenkooderi, sidetone ja USB-yhteys toimivat varmasti, lopulliseen koteloon kannattaa tehdä johdotukset juottamalla suoraan ESP32-kortille ja liittimille.

Ahtaassa kotelossa JST-liittimet ja löysät välikytkennät voivat aiheuttaa kontaktihäiriöitä. Siksi lopulliseen versioon suositellaan suoraa juottamista.

## Arduino IDE -asetukset

Tämä firmware on tarkoitettu ESP32-S3-kortille, jossa on native USB. Arduino IDE:ssä olennaiset asetukset ovat:

```text
USB Mode:        USB-OTG tai TinyUSB
USB CDC On Boot: Enabled
Upload Mode:     USB-OTG CDC tai TinyUSB
```

Jos USB CDC On Boot ei ole päällä, Morsewurst ei välttämättä löydä telemetrian sarjaporttia oikein. Jos USB-OTG- tai TinyUSB-tila ei ole käytössä, USB HID Keyboard -tila ei välttämättä toimi.

Käytä USB-datakaapelia, ei pelkkää latauskaapelia.

Jos tietokone ei tunnista ESP32-S3-korttia ohjelmointia varten, kokeile bootloader-tilaa:

1. Pidä BOOT-painike pohjassa
2. Paina RESET-painiketta
3. Vapauta RESET
4. Vapauta BOOT

Tämän jälkeen tietokoneen pitäisi nähdä levy tai sarjaportti ohjelmointia varten.

## Näyttö

Tässä projektissa käytettiin Elcrownin kasvien kastelusetin mukana tullutta 0,96 tuuman I2C OLED -näyttöä. Käytännössä lähes mikä tahansa 128x64-resoluution I2C OLED -näyttö voi toimia, kunhan oikea U8g2-ajuri valitaan näytön ohjainpiirin mukaan.

Tässä kokoonpanossa hyvin toimivaksi osoittautui seuraava määritys:

```cpp
U8G2_SH1106_128X64_NONAME_F_HW_I2C u8g2(
  U8G2_R2,
  U8X8_PIN_NONE
);
```

Vaikka näyttöä voidaan myydä SSD1306-näyttönä, tässä projektissa `SH1106`-ajuri toimi käytännössä paremmin ja esti näytön oikeaan reunaan ilmestyviä häiriöitä ja artefakteja.

Jos kuva näkyy väärin, on osittain siirtynyt tai näyttö käyttäytyy oudosti, kannattaa kokeilla eri U8g2-ajureita. OLED-näytöissä käytetty ohjainpiiri ei aina vastaa täysin sitä nimeä, jolla näyttöä markkinoidaan.

`U8G2_R2` kääntää kuvan 180 astetta. Tätä tarvitaan siksi, että näyttö asennetaan koteloon fyysisesti ylösalaisin tilan säästämiseksi.

Näyttö toimii 3,3 voltin logiikalla ja kytketään ESP32:n I2C-väylään.

Tyypillinen I2C-kytkentä:

| Näyttö | ESP32-S3 Feather |
| ------ | ---------------- |
| GND    | GND              |
| VCC    | 3.3V             |
| SCL    | SCL              |
| SDA    | SDA              |

Jos käytät STEMMA QT -liitintä, johdotus on käytännössä sama, mutta liitin hoitaa johtojen järjestyksen automaattisesti.

On hyvä huomata, että jo pienikin ero näytön fyysisissä mitoissa voi estää sitä mahtumasta `Morsewurst_keyer.stl`-koteloon oikein. Jos käytät eri näyttömallia, koteloa voi joutua muokkaamaan.

Kotelo tulostuu kuitenkin suhteellisen nopeasti. Tavallinen PETG-tuloste valmistuu yleensä muutamassa tunnissa, joten eri näyttöversioiden testaaminen on melko helppoa. Myös monet kirjastot ja makerspacet tarjoavat mahdollisuuden 3D-tulostamiseen.

## Pinout

| Toiminto                  | ESP32-pinni |
| ------------------------- | ----------- |
| Sidetone audio out        | GPIO11      |
| Straight key              | GPIO12      |
| Iambic DIT                | GPIO9       |
| Iambic DAH                | GPIO10      |
| Rotary encoder CLK tai A  | GPIO5       |
| Rotary encoder DT tai B   | GPIO6       |
| Rotary encoder painonappi | GPIO13      |
| Headphone detect          | A3          |

Kaikki avain- ja enkooderitulot käyttävät sisäistä `INPUT_PULLUP`-vastusta. Tämä tarkoittaa, että painike tai avain yhdistää signaalipinnin maahan, kun sitä painetaan.

## Suora morseavain

Suora avain kytketään 3,5 mm stereoliittimeen näin:

| Liittimen osa | Kytkentä    |
| ------------- | ----------- |
| TIP           | GPIO12      |
| RING          | Ei käytössä |
| SLEEVE        | GND         |

Koodissa suora avain on:

```cpp
const int STRAIGHT_KEY_PIN = 12;
```

## Iambic-avain

Iambic-avain kytketään 3,5 mm stereoliittimeen näin:

| Liittimen osa | Kytkentä    |
| ------------- | ----------- |
| TIP           | GPIO9, DIT  |
| RING          | GPIO10, DAH |
| SLEEVE        | GND         |

Koodissa pinnit ovat:

```cpp
const int DIT_PIN = 9;
const int DAH_PIN = 10;
```

Jos DIT ja DAH ovat väärinpäin, sen voi korjata joko vaihtamalla johdot liittimessä tai käyttämällä ohjelman `swapPaddles`-asetusta.

## Rotaatioenkooderi

Suositeltu enkooderi on painonapillinen KY-040 tai vastaava. Kytkentä esitetty seuraavana.

### Ylärivi, kaksi pinniä, painonappi

| Enkooderin pinni       | Kytkentä |
| ---------------------- | -------- |
| Toinen painonappipinni | GPIO13   |
| Toinen painonappipinni | GND      |

### Alarivi, kolme pinniä

| Enkooderin pinni | Kytkentä         |
| ---------------- | ---------------- |
| Vasen            | GPIO5, CLK tai A |
| Keskimmäinen     | GND              |
| Oikea            | GPIO6, DT tai B  |

Jos pyörimissuunta menee väärinpäin, vaihda GPIO5 ja GPIO6 keskenään.

Koodissa enkooderin pinnit ovat:

```cpp
const int ENC_CLK_PIN = 5;
const int ENC_DT_PIN = 6;
const int ENC_SW_PIN = 13;
```

## Sidetone ja kuulokelähtö

Sidetone tuotetaan ESP32:n GPIO11-pinnistä PWM-neliöaaltona. Tätä ei ole tarkoitettu kaiuttimen suoraan ajamiseen, vaan kuuloketasoiseen signaaliin.

Koodissa audio on:

```cpp
const int AUDIO_PIN = 11;
```

Äänenvoimakkuutta säädetään 10 kΩ logaritmisella monopotentiometrillä.

Potentiometrin kytkentä:

| Potentiometrin nasta       | Kytkentä                |
| -------------------------- | ----------------------- |
| Vasen reunimmainen nasta   | GPIO11                  |
| Oikea reunimmainen nasta   | GND                     |
| Keskimmäinen nasta (wiper) | Kuulokelähdön jakopiste |

Jos äänenvoimakkuuden säätö toimii väärinpäin, eli ääni kovenee silloin kun sen pitäisi hiljentyä, vaihda potentiometrin reunimmaisten nastojen johdot keskenään.

Keskimmäisestä nastasta lähtevät vastukset:

| Keskimmäisestä nastasta  | Mihin                 |
| ------------------------ | --------------------- |
| 1 kΩ vastus              | Kuulokeliittimen TIP  |
| 1 kΩ vastus              | Kuulokeliittimen RING |
| 2,2 kΩ tai 10 kΩ vastus* | GND                   |

Nämä kaksi 1 kΩ vastusta ovat erillisiä. Ne eivät ole sarjassa keskenään.

Kuulokeliittimen SLEEVE tai GND menee suoraan maahan ilman vastusta.

\* Jos sidetone-ääni kuuluu edelleen kuulokkeista vaikka potentiometri olisi täysin nollassa, kannattaa kokeilla suurempaa maahan menevää vastusta.

Esimerkiksi:
- 2,2 kΩ voi joissain kokoonpanoissa päästää hieman ääntä läpi
- 10 kΩ voi hiljentää vuotoääntä tehokkaammin

Sopiva arvo riippuu käytetystä potentiometristä, kuulokkeista ja kuulokeliittimen rakenteesta.

Yksinkertaistettu kytkentä:

```text
GPIO11 -> potentiometrin reunimmainen nasta
GND    -> potentiometrin toinen reunimmainen nasta

Potentiometrin keskimmäinen nasta
  ├── 1 kΩ -> kuulokeliitin TIP
  ├── 1 kΩ -> kuulokeliitin RING
  └── 2,2 kΩ tai 10 kΩ -> GND

Kuulokeliitin SLEEVE -> GND
```

## Kuulokkeiden tunnistus (valinnainen)

Projektissa on varattu tuki kytkimelliselle 3,5 mm kuulokeliittimelle. Tarkoituksena on, että kuulokeliitin voi vetää `A3`-pinnin maahan silloin, kun kuulokkeet ovat kytkettyinä.

Koodissa tämä näkyy esimerkiksi näin:

```cpp
const int HEADPHONE_DETECT_PIN = A3;

bool headphonesConnected() {
  return digitalRead(HEADPHONE_DETECT_PIN) == LOW;
}
```

Ominaisuuden ajatuksena on ollut mahdollistaa esimerkiksi sellainen toiminta, että sidetone-ääni kuuluu vain silloin, kun kuulokkeet ovat paikallaan.

Tämä toiminto ei kuitenkaan ole tällä hetkellä aktiivisessa käytössä projektissa, vaan kyseessä on lähinnä varattu laajennusmahdollisuus tulevaa käyttöä varten.

Jos käytät tavallista 3,5 mm kuulokeliitintä ilman tunnistuskytkintä, koko tunnistusominaisuuden voi jättää pois käytöstä kommentoimalla pinnimäärityksen pois:

```cpp
// const int HEADPHONE_DETECT_PIN = A3;
```

Tällöin tavallinen kuulokeliitin toimii normaalisti ilman tunnistuskytkentää.


## 3D-tulostettava kotelo

Kotelotiedosto:

```text
Morsewurst_keyer.stl
```

Suositus:

- Materiaali: PETG
- Kerroskorkeus: noin 0,2 mm
- Täyttö: noin 20-30 %
- Seinämät: 2-3 perimetriä
- Tulostin: esimerkiksi Prusa i3 MK3S Plus tai vastaava

Jos tulostimen tarkkuus ei riitä suoraan kaikkien reikien osalta, reiät kannattaa porata tai siistiä varovasti käsin. Älä käytä liikaa voimaa, jotta kotelo ei halkea.

Näyttö asennetaan koteloon fyysisesti ylösalaisin, koska kotelon sisäinen tila on rajallinen. Ohjelmassa kuva käännetään takaisin oikein päin `U8G2_R2`-asetuksella.

## Telemetria Morsewurstille

Laite lähettää ajoitustapahtumat USB CDC Serial -yhteyden kautta JSON-muodossa. Morsewurst lukee nämä rivit ja käyttää niitä harjoituksen ajoituksen, rytmin ja dekoodauksen analysointiin.

Esimerkki tone-tapahtumasta:

```json
{
  "v": 1,
  "type": "tone",
  "src": "straight",
  "t0": 123456789,
  "t1": 123556789,
  "dur": 100000
}
```

Iambic-tilassa mukana voi olla myös elementti ja yksikköpituus:

```json
{
  "v": 1,
  "type": "tone",
  "src": "iambic",
  "el": ".",
  "t0": 123456789,
  "t1": 123516789,
  "dur": 60000,
  "unit": 60000,
  "wpm": 20.0
}
```

Tärkeää on, että `t0`, `t1` ja `dur` ovat ESP32:n mittaamia arvoja. USB:n ja Pythonin viive vaikuttaa siihen, milloin tapahtuma näkyy tietokoneella, mutta ei muuta näitä ESP32:n jo mittaamia arvoja.

## Mittaustarkkuus

Koodi käyttää ESP32:n mikrosekuntiresoluutioista aikajärjestelmää:

```cpp
uint64_t nowTime() {
  return (uint64_t)esp_timer_get_time();
}
```

Aikaleimat tallennetaan mikrosekunteina, mutta koko järjestelmän käytännön tarkkuus ei ole yksi mikrosekunti. Nykyisessä polling-pohjaisessa toteutuksessa realistinen käytännön tarkkuus on hyvissä olosuhteissa noin:

```text
50-200 mikrosekuntia
```

Tämä riittää erittäin hyvin morseharjoitteluun, koska ihmisen käsialan ajoitusvaihtelu on yleensä paljon suurempaa kuin laitteen mittausvirhe.

Jos tulevaisuudessa halutaan vielä tarkempi reunojen mittaus suoralle avaimelle, seuraava kehitysaskel olisi GPIO-keskeytyksiin perustuva mittaus. Silloin pitää kuitenkin käsitellä myös mekaanisen avaimen kontaktivärinä.

## USB HID Keyboard -tila

Laite voi lähettää puretut merkit tietokoneelle USB-näppäimistönä.

Tämä on kätevää, jos laitetta halutaan käyttää suoraan tekstinsyöttöön. Erikoismerkkien osalta koodi olettaa suomalaisen näppäimistöasettelun. Jos tietokoneessa on esimerkiksi englanninkielinen näppäimistöasettelu, osa merkeistä voi tulla väärin.

Tilan voi ottaa käyttöön tai pois laitteen asetuksista.

## Rakennusjärjestys

1. Lataa `morsewurst_keyer_\*_\*.ino` Arduino IDE:en
2. Valitse oikea ESP32-S3-kortti ja USB-asetukset
3. Testaa ESP32:n ohjelmointi USB-C-kaapelilla
4. Kytke OLED-näyttö ja varmista, että kuva näkyy oikein
5. Kytke rotaatioenkooderi ja testaa valikon käyttö
6. Kytke suora avain GPIO12-pinniin ja GND:hen
7. Kytke iambic-paddle GPIO9-, GPIO10- ja GND-pinneihin
8. Rakenna sidetone-kytkentä potentiometrillä ja vastuksilla
9. Testaa kuulokelähtö pienellä äänenvoimakkuudella
10. Testaa USB serial -telemetria Morsewurstissa
11. Testaa USB keyboard -tila tarvittaessa
12. Tulosta kotelo PETG-muovista
13. Siisti reiät varovasti
14. Juota lopulliset johdotukset
15. Asenna osat koteloon
16. Tee lopputesti ennen kotelon sulkemista

## Huomioita turvallisuudesta ja luotettavuudesta

- Käytä 3,3 voltin logiikkaa
- Älä syötä ESP32:n GPIO-pinneihin 5 volttia
- Älä aja kaiutinta suoraan GPIO11-pinnistä
- Aloita kuuloketestit pienellä äänenvoimakkuudella
- Tee lopulliset johdotukset mahdollisimman lyhyiksi ja mekaanisesti tukeviksi
- Vältä ahtaassa kotelossa löysiä liittimiä
- Merkitse GND-johdot selvästi
- Testaa jokainen osa erikseen ennen lopullista kasausta

## Tiedostot

| Tiedosto                   | Tarkoitus              |
| -------------------------- | ---------------------- |
| morsewurst_keyer_\*_\*.ino | Arduino-firmware       |
| Morsewurst_keyer.stl       | 3D-tulostettava kotelo |
| Morsewurst                 | Harjoitteluun          |


## Yhteenveto

Tein Morsewurst Keyerin alun perin omaan morseharjoitteluun. Koko projektin suunnittelufilosofia oli siinä, että halusin tehdä omasta morsetuksesta mahdollisimman mitattavaa, analysoitavaa ja visualisoitavaa sen sijaan, että harjoittelu olisi kuolemaakin tylsempää naputtelua vailla mitään tietoa siitä, kuinka hyvin pärjää.

ESP32-S3 mittaa avaimen painallusten ajoitukset mikrosekuntimuodossa ja lähettää tapahtumat JSON-telemetriana Morsewurstille. Morsewurst pystyy sitten analysoimaan rytmiä, ajoitusta, virheitä ja muita yksityiskohtia paljon tarkemmin kuin mitä pelkästään kuuntelemalla huomaisi.

Mukavana lisäbonuksena laite pystyy toimimaan myös USB-näppäimistönä, jos asetus otetaan käyttöön. Tällöin morsetettu teksti kirjoitetaan suoraan tietokoneelle.

Suosittelen todella vahvasti rakentamaan ja testaamaan koko laitteen ensin kytkentälaudalla ennen mitään lopullisia juotoksia. Kun näyttö, avaimet, rotaatioenkooderi, sidetone ja USB-yhteydet toimivat varmasti, lopullinen versio kannattaa tehdä niin, että kaikki johdot juotetaan suoraan ESP32-S3-piiriin. Ahtaassa kotelossa irtojohtimet ja löysät liittimet aiheuttavat helposti kontaktihäiriöitä.

Jos haluaa käyttää valmista koteloa, mukana on `Morsewurst_keyer.stl`-tiedosto. Kotelo on suunniteltu PETG-tulostukseen. Käytännössä sen toimivuus kuitenkin vaatii, että käytössä ovat hyvin lähellä samat komponentit kuin tässä projektissa. Jo pienet erot näytön tai liittimien mitoissa voivat estää osia mahtumasta koteloon oikein.

Onneksi vastaavan kotelon suunnittelu itse on nykyään melko helppoa esimerkiksi Fusion 360:llä tai Blenderillä.

Tässä koteloratkaisussa näyttö asennetaan fyysisesti ylösalaisin tilansäästön vuoksi. Näytön kuva käännetään ohjelmallisesti takaisin oikein päin tällä U8g2-asetuksella:

```cpp
U8G2_SH1106_128X64_NONAME_F_HW_I2C u8g2(
  U8G2_R2,
  U8X8_PIN_NONE
);
```

`U8G2_R2` kääntää kuvan 180 astetta.

Jos teet oman kotelon ja ihmettelet, miksi näyttö näkyy ylösalaisin, muuta tuo rivi esimerkiksi tähän:

```cpp
U8G2_SH1106_128X64_NONAME_F_HW_I2C u8g2(
  U8G2_R0,
  U8X8_PIN_NONE
);
```

Tällöin näyttöä ei enää käännetä ohjelmallisesti.


## Serial API yhteensopiville laitteille

Morsewurstin tärkein laiterajapinta on USB CDC Serial -yhteyden kautta lähetettävä rivipohjainen JSON-telemetria.

Tämä tarkoittaa, että Morsewurstin kanssa yhteensopivan laitteen ei tarvitse olla alkuperäinen ESP32-S3-pohjainen Morsewurst Keyer. Mikä tahansa mikrokontrolleri, Arduino-yhteensopiva laite tai muu oma laiteratkaisu voi toimia, jos se pystyy lähettämään oikeanmuotoisia JSON-rivejä sarjaportin kautta.

Rajapinta on käytännössä yksisuuntainen. Laite lähettää ajoitusdataa Morsewurstille. Morsewurstin ei tarvitse lähettää komentoja laitteelle takaisinpäin.

### Sarjayhteys

Suositeltu sarjanopeus on:

```text
115200 baud
```

Laite lähettää yhden JSON-objektin per rivi.

Jokainen viesti päätetään rivinvaihtoon:

```text
\n
```

Käytännössä Morsewurst lukee sarjaporttia rivi kerrallaan ja yrittää tulkita jokaisen rivin JSON-objektina.

### Laitteen tunnistaminen

Morsewurst voi tunnistaa oikean sarjaportin sen perusteella, että portista tulee Morsewurst-yhteensopivia JSON-viestejä.

Tunnistuksen kannalta hyödyllisiä viestejä ovat:

```text
hello
heartbeat
tone
```

Hyvä yhteensopiva laite lähettää `hello`-viestin käynnistyksen tai sarjayhteyden avaamisen jälkeen ja `heartbeat`-viestin säännöllisesti myös silloin, kun avainta ei paineta.

Tämä auttaa Morsewurstia löytämään oikean COM-portin tai serial-portin myös silloin, kun käyttäjä ei juuri sillä hetkellä morseta mitään.

### Hello-viesti

`hello` kertoo, että portissa on Morsewurst-yhteensopiva laite.

Esimerkki:

```json
{"v":1,"type":"hello","app":"morsewurst","device":"Morsewurst Keyer","fw":"1.0","mode":"raw_timing"}
```

Kentät:

| Kenttä   | Tyyppi | Merkitys                                           |
| -------- | ------ | -------------------------------------------------- |
| `v`      | number | Protokollaversio. Nykyinen versio on `1`.          |
| `type`   | string | Viestin tyyppi. Tässä `hello`.                     |
| `app`    | string | Sovellustunniste. Suositeltu arvo on `morsewurst`. |
| `device` | string | Laitteen nimi.                                     |
| `fw`     | string | Firmware- tai ohjelmistoversio.                    |
| `mode`   | string | Telemetriatila. Suositeltu arvo on `raw_timing`.   |

### Heartbeat-viesti

`heartbeat` kertoo, että laite on edelleen kiinni, toimii ja lähettää raw timing -telemetriaa.

Suositeltu lähetysväli on noin 5 sekuntia.

Esimerkki:

```json
{"v":1,"type":"heartbeat","app":"morsewurst","device":"morsewurst","fw":"1.0","mode":"raw_timing","uptime":5000000,"wpm":20,"telemetry":true}
```

Kentät:

| Kenttä      | Tyyppi  | Merkitys                                                         |
| ----------- | ------- | ---------------------------------------------------------------- |
| `v`         | number  | Protokollaversio.                                                |
| `type`      | string  | Viestin tyyppi. Tässä `heartbeat`.                               |
| `app`       | string  | Sovellustunniste. Morsewurst-ohjelma odottaa arvoa `morsewurst`. |
| `device`    | string  | Laitteen nimi.                                                   |
| `fw`        | string  | Firmware- tai ohjelmistoversio.                                  |
| `mode`      | string  | Telemetriatila. Suositeltu arvo on `raw_timing`.                 |
| `uptime`    | number  | Laitteen käynnissäoloaika mikrosekunteina.                       |
| `wpm`       | number  | Laitteen tämänhetkinen WPM-asetus, jos sellainen on olemassa.    |
| `telemetry` | boolean | `true`, kun raw timing -telemetria on käytössä.                  |

`heartbeat` ei korvaa varsinaisia ajoitustapahtumia, mutta se on tärkeä käytännön yhteensopivuuden kannalta. Ilman sitä Morsewurst voi löytää laitteen vasta silloin, kun laitteesta tulee ensimmäinen `tone`-tapahtuma.

### Tone-viesti

Morsewurstin ajoitusanalyysin kannalta tärkein viesti on `tone`.

`tone` kertoo yhden äänen, painalluksen tai morse-elementin ajoituksen.

Vähimmäismuoto:

```json
{"v":1,"type":"tone","src":"straight","t0":1000000,"t1":1100000,"dur":100000}
```

Kentät:

| Kenttä | Tyyppi | Pakollinen | Merkitys                                               |
| ------ | ------ | ---------- | ------------------------------------------------------ |
| `v`    | number | kyllä      | Protokollaversio. Nykyinen versio on `1`.              |
| `type` | string | kyllä      | Viestin tyyppi. Ajoitustapahtumassa arvo on `tone`.    |
| `src`  | string | kyllä      | Tapahtuman lähde, esimerkiksi `straight` tai `iambic`. |
| `t0`   | number | kyllä      | Painalluksen tai äänen alkuhetki mikrosekunteina.      |
| `t1`   | number | kyllä      | Painalluksen tai äänen loppuhetki mikrosekunteina.     |
| `dur`  | number | kyllä      | Kesto mikrosekunteina. Yleensä `t1 - t0`.              |

Jos laite lähettää vain suoran avaimen painallusten raw timing -dataa, tämä vähimmäismuoto riittää.

### Aikaleimat

Aikaleimojen pitää olla laitteen itsensä mittaamia mikrosekuntiaikaleimoja.

Niiden ei tarvitse olla todellista kellonaikaa. Ne voivat olla mikrosekunteja laitteen käynnistymisestä.

Tärkeää on, että arvot ovat:

* mikrosekunteja
* kokonaislukuja
* saman laitteen omasta kellosta
* monotonisesti kasvavia
* keskenään vertailukelpoisia saman harjoitussession aikana

Jos yhteensopiva laite tehdään ESP32:lla, hyvä tapa hakea aika on esimerkiksi `esp_timer_get_time()`, koska se palauttaa mikrosekuntiajan.

Esimerkki ESP32-tyylisestä toteutuksesta:

```cpp
uint64_t nowTime() {
  return (uint64_t)esp_timer_get_time();
}
```

Jos laite tehdään toisella mikrokontrollerilla, sen ei tarvitse käyttää samaa funktiota. Riittää, että se pystyy lähettämään luotettavia ja monotonisesti kasvavia mikrosekuntiaikaleimoja.

Jos mahdollista, aikaleimat kannattaa lähettää 64-bittisinä kokonaislukuina, jotta ylivuoto ei tule nopeasti vastaan.

### Suoran avaimen tapahtumat

Suoralla avaimella suositeltu lähdearvo on:

```text
straight
```

Suoran avaimen tapauksessa laitteen ei tarvitse itse päättää, onko painallus piste vai viiva. Riittää, että se lähettää painalluksen alkuajan, loppuajan ja keston.

Esimerkki:

```json
{"v":1,"type":"tone","src":"straight","t0":123456789,"t1":123556789,"dur":100000}
```

Morsewurst voi tämän jälkeen arvioida ajoituksesta, oliko kyseessä piste, viiva, kirjainväli tai sanaväli.

### Iambic-avaimen tapahtumat

Jos laite tekee itse iambic-keyerin logiikan, se voi lähettää myös tiedon siitä, oliko tuotettu elementti piste vai viiva.

Iambic-avaimelle suositeltu lähdearvo on:

```text
iambic
```

Esimerkki pisteestä:

```json
{"v":1,"type":"tone","src":"iambic","el":".","t0":1000000,"t1":1060000,"dur":60000,"unit":60000,"wpm":20.0}
```

Esimerkki viivasta:

```json
{"v":1,"type":"tone","src":"iambic","el":"-","t0":1200000,"t1":1380000,"dur":180000,"unit":60000,"wpm":20.0}
```

Lisäkentät:

| Kenttä | Tyyppi | Merkitys                                  |
| ------ | ------ | ----------------------------------------- |
| `el`   | string | Morse-elementti, joko `.` tai `-`.        |
| `unit` | number | Yhden dit-yksikön pituus mikrosekunteina. |
| `wpm`  | number | Nopeus sanoina minuutissa.                |

Iambic-tilassa `unit` voidaan laskea näin:

```text
unit = 1200000 / wpm
```

20 WPM nopeudella yhden dit-yksikön pituus on:

```text
60000 µs
```

### JSON-muoto

Numeroarvot lähetetään JSON-numeroina, ei merkkijonoina.

Oikein:

```json
{"t0":123456789,"dur":100000}
```

Ei näin:

```json
{"t0":"123456789","dur":"100000"}
```

Merkkijonot lähetetään normaaleina JSON-merkkijonoina.

Oikein:

```json
{"type":"tone","src":"straight"}
```

Jokainen JSON-objekti pitää lähettää omalla rivillään.

Oikein:

```text
{"v":1,"type":"heartbeat","app":"morsewurst","device":"Morsewurst Keyer","fw":"1.0","mode":"raw_timing","uptime":5000000,"wpm":20,"telemetry":true}
{"v":1,"type":"tone","src":"straight","t0":6000000,"t1":6100000,"dur":100000}
```

### Käytännön vähimmäistoteutus

Yksinkertaisin yhteensopiva laite tekee tämän:

1. Avaa USB CDC Serial -yhteyden nopeudella 115200 baud
2. Lähettää `hello`-viestin, kun yhteys on käytettävissä
3. Lähettää `heartbeat`-viestin säännöllisesti
4. Mittaa avaimen painalluksen alkuhetken mikrosekunteina
5. Mittaa avaimen vapautushetken mikrosekunteina
6. Laskee painalluksen keston mikrosekunteina
7. Lähettää jokaisesta painalluksesta yhden `tone`-viestin

Vähimmäisesimerkki:

```json
{"v":1,"type":"hello","app":"morsewurst","device":"Morsewurst Keyer","fw":"1.0","mode":"raw_timing"}
{"v":1,"type":"heartbeat","app":"morsewurst","device":"Morsewurst Keyer","fw":"1.0","mode":"raw_timing","uptime":5000000,"wpm":20,"telemetry":true}
{"v":1,"type":"tone","src":"straight","t0":6000000,"t1":6100000,"dur":100000}
```

### Tekstimuotoinen serial output ei riitä

Pelkkä tekstimuotoinen sarjatuloste ei riitä Morsewurstin raw timing -analyysiin.

Esimerkiksi tällainen ei riitä:

```text
HELLO WORLD
```

Eikä myöskään pelkkä purettu merkki kerrallaan:

```text
H
E
L
L
O
```

Raw timing -analyysi tarvitsee painallusten ajat:

```text
t0
t1
dur
```

Ilman näitä Morsewurst ei voi analysoida painallusten rytmiä, pisteiden ja viivojen kestoja, kirjainvälejä tai sanavälejä luotettavasti.

### USB HID Keyboard -tila

Alkuperäisessä Morsewurst ESP32 -firmwaressa on myös USB HID Keyboard -tila. Sen avulla laite voi kirjoittaa dekoodattuja merkkejä suoraan tietokoneelle näppäimistön tavoin.

Tämä on lähinnä ylimääräinen hauska toiminnallisuus. Sitä ei kannata pitää vakavamielisenä morse-dekooderina, koska laitteen oma reaaliaikainen dekoodaus voi tehdä virheitä ja tekstinsyöttö näppäimistönä ei ole yhtä käytännöllinen kuin Morsewurstin raw timing -analyysi.

Morsewurstin kannalta USB HID Keyboard -tila ei ole tarpeellinen. Varsinainen yhteensopivuus perustuu USB CDC Serial -telemetriaan.

### Suositeltu API-yhteensopiva viestisarja

Hyvä Morsewurst-yhteensopiva laite lähettää esimerkiksi tällaisen sarjan:

```json
{"v":1,"type":"hello","app":"morsewurst","device":"Morsewurst Keyer","fw":"1.0","mode":"raw_timing"}
{"v":1,"type":"heartbeat","app":"morsewurst","device":"Morsewurst Keyer","fw":"1.0","mode":"raw_timing","uptime":5000000,"wpm":20,"telemetry":true}
{"v":1,"type":"tone","src":"straight","t0":6000000,"t1":6060000,"dur":60000}
{"v":1,"type":"tone","src":"straight","t0":6120000,"t1":6300000,"dur":180000}
{"v":1,"type":"tone","src":"straight","t0":6360000,"t1":6420000,"dur":60000}
{"v":1,"type":"heartbeat","app":"morsewurst","device":"Morsewurst Keyer","fw":"1.0","mode":"raw_timing","uptime":10000000,"wpm":20,"telemetry":true}
```

Kun laite lähettää tällaisia rivejä USB CDC Serial -yhteyden kautta, Morsewurst voi lukea tapahtumat, tunnistaa laitteen ja analysoida morseajoitusta riippumatta siitä, millä mikrokontrollerilla tai elektroniikalla laite on toteutettu.
