# ============================================================
# morsewurst/ui/help_content.py
# ============================================================

from __future__ import annotations


HELP_DOCUMENT = [
    {
        "type": "title",
        "text": "Morsewurst ohje"
    },
    {
        "type": "paragraph",
        "text": "Morsewurst on morseharjoitusohjelma, joka lukee morseavaimen, keyerin tai tietokoneen näppäimistön tuottamaa ajoitustelemetriaa, dekoodaa painallukset morsemerkeiksi, pisteyttää harjoituskierrokset ja seuraa kehitystä pitkällä aikavälillä. Ohjelmaa voi käyttää paikallisesti tai network-tilassa muiden käyttäjien kanssa."
    },
    {
        "type": "paragraph",
        "text": "Ohjelman perusajatus on, että valitset harjoituksen asetukset, lähetät näytöllä näkyvän tavoitteen ja annat ohjelman tallentaa tuloksen. Historia, vaikeimmat merkit, WPM-arvot, ajoitusprofiilit ja taitotaso päivittyvät tallennettujen kierrosten perusteella."
    },
    {
        "type": "note",
        "text": "Ohje kuvaa tätä ohjelmaversiota. Jos olet juuri muuttanut koodia, poista __pycache__-kansiot tai käynnistä ohjelma uudelleen, jotta uusi ohjesisältö ja uudet asetukset tulevat varmasti käyttöön."
    },
    {
        "type": "heading",
        "text": "Peruskäyttö"
    },
    {
        "type": "bullet",
        "text": "Yhdistä Morsewurst-laite tai muu tuettu sarjatelemetrialähde tietokoneeseen USB-kaapelilla, tai ota asetuksista käyttöön tietokoneen näppäimistöllä morsetus."
    },
    {
        "type": "bullet",
        "text": "Jos käytät fyysistä laitetta, valitse oikea COM-portti Serial-telemetria-kohdasta tai anna automaattisen yhdistämisen etsiä laite."
    },
    {
        "type": "bullet",
        "text": "Jos haluat lähettää tai kuunnella muiden morsetusta verkon yli, avaa Network-ikkuna ja liity huoneeseen tai käynnistä oma huone."
    },
    {
        "type": "bullet",
        "text": "Valitse harjoituksen asetukset, kuten kirjaimet, numerot, erikoismerkit, WX-MOR, kierrosmäärä, ryhmämäärät ja tavoite-WPM."
    },
    {
        "type": "bullet",
        "text": "Paina Aloita harjoitus."
    },
    {
        "type": "bullet",
        "text": "Lähetä näytöllä näkyvä tavoite morseavaimella."
    },
    {
        "type": "bullet",
        "text": "Ohjelma dekoodaa telemetrian, näyttää tuloksen ja tallentaa valmiin kierroksen tietokantaan."
    },
    {
        "type": "bullet",
        "text": "Jos harjoitussarjassa on useita kierroksia, seuraava kierros alkaa automaattisesti lyhyen tauon jälkeen."
    },
    {
        "type": "paragraph",
        "text": "Kierros alkaa vasta ensimmäisestä todellisesta syötteestä. Pelkkä tavoitteen näkyminen ruudulla ei vielä käynnistä aikaa."
    },
    {
        "type": "heading",
        "text": "Pääikkunan alueet"
    },
    {
        "type": "subheading",
        "text": "Tavoite"
    },
    {
        "type": "paragraph",
        "text": "Tavoite näyttää tekstin, joka pitää lähettää. Tavallisessa harjoituksessa tavoite muodostetaan valituista merkkiluokista, ryhmäasetuksista ja mahdollisesta vaikeimpien merkkien painotuksesta. WX-MOR-tilassa tavoite muodostetaan sääsanomageneraattorilla."
    },
    {
        "type": "subheading",
        "text": "Raakatelemetria"
    },
    {
        "type": "paragraph",
        "text": "Raakatelemetria näyttää tone-tapahtumat aikajanana. Mustat palkit ovat aktiivisia painalluksia. Näkymä auttaa havaitsemaan pisteiden, viivojen ja taukojen pituuksia sekä mahdollisia puuttuvia merkkivälejä."
    },
    {
        "type": "subheading",
        "text": "Telemetriasta dekoodattu syöte"
    },
    {
        "type": "paragraph",
        "text": "Tässä näkyy teksti, jonka ohjelma on tulkinnut raakatelemetriasta. Kun Käytä telemetriaa totuutena on päällä, tämä teksti on pisteytyksen ensisijainen lähde."
    },
    {
        "type": "paragraph",
        "text": "Tuntematon morsekuvio näytetään merkillä �. Se on erotettu oikeasta kysymysmerkistä, jotta oikea merkki ? ja tuntematon dekoodaus eivät sekoitu tilastoissa."
    },
    {
        "type": "subheading",
        "text": "Tulos"
    },
    {
        "type": "paragraph",
        "text": "Tulosalue näyttää harjoituksen tilan, ajan, harjoitussarjan yhteenvedon ja viimeisimmän kierroksen tuloksen. Näkyviä arvoja ovat esimerkiksi tarkkuus, puhtaus, pisteet, ajoitus, virheet, väärät merkit, ylimääräiset ja puuttuvat merkit, WPM-arvot, viivasuhde sekä dit- ja dah-hajonta."
    },
    {
        "type": "subheading",
        "text": "Yleistä tietoa"
    },
    {
        "type": "paragraph",
        "text": "Yleistä tietoa näyttää historian yhteenvedon. Se käyttää asetuksissa valittua määrää viimeisimpiä kierroksia ja näyttää esimerkiksi kierrosmäärän, tarkkuuden, puhtauden, pisteet, brutto-WPM:n, netto-WPM:n, laite-WPM:n, viivasuhteen sekä dit- ja dah-hajonnan."
    },
    {
        "type": "subheading",
        "text": "Viimeisimmät kierrokset"
    },
    {
        "type": "paragraph",
        "text": "Viimeisimmät kierrokset -taulukko näyttää tallennetut harjoitukset. Taulukossa näkyvät ID, aika, tarkkuus, puhtaus, pisteet, virheet, WPM, kesto, syöte ja tavoite. Riviä napsauttamalla voi avata historiakierroksen takaisin pääikkunan näkymään tarkastelua varten."
    },
    {
        "type": "subheading",
        "text": "Taitotaso"
    },
    {
        "type": "paragraph",
        "text": "Taitotaso näyttää nykyisen levelin, tason nimen, yleistaito-WPM:n, molemmilla avaintyypeillä todistetun WPM:n, seuraavan tason etenemisen sekä tarkkuuden, puhtauden, ajoituksen, korjauksen, luottamuksen, merkkien hallinnan, kattavuuden ja käytettyjen kierrosten määrän."
    },
    {
        "type": "subheading",
        "text": "Serial-telemetria"
    },
    {
        "type": "paragraph",
        "text": "Serial-telemetria-alueella valitaan portti, päivitetään porttilista, yhdistetään laitteeseen ja katkaistaan yhteys. Viimeisin tapahtuma näyttää viimeksi saadun sarjatapahtuman tyypin."
    },
    {
        "type": "subheading",
        "text": "Network"
    },
    {
        "type": "paragraph",
        "text": "Network avaa verkkoyhteysikkunan, jossa voi liittyä relay-palvelimen kautta huoneeseen, seurata julkisia huoneita, säätää vastaanoton ääntä ja viivepuskuria sekä lähettää omaa tone-telemetriaa muille käyttäjille."
    },
    {
        "type": "subheading",
        "text": "Vaikeimmat merkit"
    },
    {
        "type": "paragraph",
        "text": "Vaikeimmat merkit -taulukko näyttää merkit, joissa tavoitemerkkeihin perustuva virheprosentti on suurin. Taulukko näyttää merkin, yritysten määrän, virheiden määrän ja virheprosentin."
    },
    {
        "type": "heading",
        "text": "Harjoituksen asetukset"
    },
    {
        "type": "subheading",
        "text": "Kirjaimet A-Z"
    },
    {
        "type": "paragraph",
        "text": "Kun tämä on valittuna, tavallisissa tavoitteissa käytetään kirjaimia A-Z."
    },
    {
        "type": "subheading",
        "text": "Numerot 0-9"
    },
    {
        "type": "paragraph",
        "text": "Kun tämä on valittuna, tavallisissa tavoitteissa käytetään numeroita 0-9."
    },
    {
        "type": "subheading",
        "text": "Erikoismerkit"
    },
    {
        "type": "paragraph",
        "text": "Kun tämä on valittuna, tavallisissa tavoitteissa voidaan käyttää asetuksessa PUNCTUATION määriteltyjä merkkejä. Niihin kuuluvat esimerkiksi piste, pilkku, kysymysmerkki, huutomerkki, kauttaviiva, sulut, plus, miinus ja muut tuetut välimerkit."
    },
    {
        "type": "subheading",
        "text": "Jos kaikki merkkiluokat poistetaan"
    },
    {
        "type": "paragraph",
        "text": "Jos kirjaimet, numerot ja erikoismerkit poistetaan kaikki käytöstä, ohjelma käyttää turvavalintana kirjaimia ja numeroita. Näin tyhjää tavoitetta ei synny."
    },
    {
        "type": "subheading",
        "text": "Harjoittele WX-MOR-sanomaa"
    },
    {
        "type": "paragraph",
        "text": "WX-MOR-tila ohittaa tavallisen satunnaisen merkkigeneraattorin ja luo sääsanomatyylisen harjoitustavoitteen. WX-MOR-profiileja ovat Automaattinen, Minimi, Perus, Kompakti ja Laaja."
    },
    {
        "type": "paragraph",
        "text": "WX-MOR ei tuota tasaisesti kaikkia merkkejä. Sääsanomien rakenteet, lukuarvot, ilmanpaineet ja näkyvyysarvot voivat lisätä joidenkin numeroiden ja kirjainten, kuten nollan, esiintymistä historiassa."
    },
    {
        "type": "subheading",
        "text": "Harjoittele vaikeimpia merkkejä"
    },
    {
        "type": "paragraph",
        "text": "Kun tämä on päällä, osa merkeistä valitaan vaikeimpien merkkien listasta. Vaikeimmat merkit eivät korvaa koko merkkivalikoimaa, vaan saavat suuremman todennäköisyyden tulla mukaan uusiin tavallisiin harjoitustavoitteisiin."
    },
    {
        "type": "paragraph",
        "text": "Painotus koskee vain sallittuja merkkejä. Jos numerot eivät ole käytössä, vaikeimmat numerot eivät tule tavalliseen harjoitukseen mukaan."
    },
    {
        "type": "subheading",
        "text": "Kierroksia"
    },
    {
        "type": "paragraph",
        "text": "Kierroksia määrittää, montako kierrosta yhteen harjoitussarjaan kuuluu. Jos arvo on 1, tehdään yksi kierros. Jos arvo on suurempi, ohjelma jatkaa automaattisesti seuraavaan kierrokseen, kunnes sarja on valmis."
    },
    {
        "type": "subheading",
        "text": "Ryhmiä min ja max"
    },
    {
        "type": "paragraph",
        "text": "Ryhmiä min ja max määrittävät, montako sanaryhmää tavalliseen tavoitteeseen luodaan. Ryhmät erotetaan välilyönnillä."
    },
    {
        "type": "subheading",
        "text": "Merkkejä min ja max"
    },
    {
        "type": "paragraph",
        "text": "Merkkejä min ja max määrittävät, kuinka monta varsinaista merkkiä yhdessä ryhmässä on. Ryhmien välissä oleva välilyönti ei ole ryhmän sisäinen merkki, mutta sisäinen ryhmäväli huomioidaan puhtaudessa ja virhelaskennassa."
    },
    {
        "type": "heading",
        "text": "Harjoitusnopeus"
    },
    {
        "type": "subheading",
        "text": "Tavoite-WPM"
    },
    {
        "type": "paragraph",
        "text": "Tavoite-WPM määrittää vertailuajan, johon kierroksen nopeutta verrataan. Se vaikuttaa nopeuspisteisiin, vertailuaikaan ja myös taitotason todistamiseen, koska matalalla tavoite-WPM:llä tehty kierros ei voi todistaa valittua tavoitenopeutta korkeampaa onnistunutta WPM:ää."
    },
    {
        "type": "subheading",
        "text": "Äänitesti"
    },
    {
        "type": "paragraph",
        "text": "Asetusten Nopeus-välilehdellä oleva äänitesti soittaa esimerkkitekstin valitulla tavoite-WPM:llä. Jos ääntä ei saada käyntiin, ohjelma näyttää ilmoituksen tarvittavista Python-kirjastoista."
    },
    {
        "type": "subheading",
        "text": "Ehdota harjoitusnopeutta"
    },
    {
        "type": "paragraph",
        "text": "Ehdota harjoitusnopeutta etsii historiasta kierrokset, jotka ylittävät tehokkaan WPM:n minimitarkkuuden ja minimipuhtauden. Jokaiselle sopivalle kierrokselle lasketaan toteutunut PARIS-WPM tavoitetekstin morseyksiköistä ja kierroksen kestosta."
    },
    {
        "type": "paragraph",
        "text": "Lopullinen arvio on mediaani, jotta yksittäinen poikkeava kierros ei hallitse tulosta. Ehdotettu harjoitusnopeus on käytännössä todistettu mediaani lisättynä pienellä nousuvaralla ja rajattuna sallittuun WPM-alueeseen."
    },
    {
        "type": "subheading",
        "text": "Tavoite-WPM:n vieressä oleva merkintä"
    },
    {
        "type": "paragraph",
        "text": "Tavoite-WPM:n vieressä näkyvä pieni merkintä kertoo, miten nykyinen asetus suhteutuu historian perusteella ehdotettuun nopeuteen. Plus tarkoittaa, että ohjelma ehdottaisi korkeampaa nopeutta. Miinus tarkoittaa, että ehdotus olisi matalampi. Valintamerkki tarkoittaa, että nykyinen arvo vastaa ehdotusta."
    },
    {
        "type": "heading",
        "text": "Syötteen lähteet"
    },
    {
        "type": "subheading",
        "text": "Tone-tapahtumat"
    },
    {
        "type": "paragraph",
        "text": "Ohjelman tärkein syötemuoto on tone-tapahtuma. Tapahtumasta odotetaan lähde, alkuaika, loppuaika ja kesto. Lähteenä voi olla esimerkiksi straight tai iambic. Duplikaattitapahtumat ohitetaan saman lähteen ja aikaleimojen perusteella."
    },
    {
        "type": "paragraph",
        "text": "Tone-tapahtumia voi tulla fyysiseltä sarjalaitteelta, verkon kautta toiselta käyttäjältä tai tietokoneen näppäimistöstä, kun näppäimistömorse on käytössä."
    },
    {
        "type": "subheading",
        "text": "Sarjatelemetria"
    },
    {
        "type": "paragraph",
        "text": "Sarjatelemetriassa ohjelma lukee USB-sarjaportista Morsewurst-laitteen tai muun tuetun laitteen lähettämiä tone-tapahtumia. Tämä on ensisijainen tapa käyttää fyysistä keyeriä tai straight keytä ohjelman kanssa."
    },
    {
        "type": "subheading",
        "text": "Automaattinen yhdistäminen"
    },
    {
        "type": "paragraph",
        "text": "Jos automaattinen yhdistäminen on käytössä, ohjelma etsii sopivaa laitetta sarjaporteista säännöllisesti. Kun yhteys katkeaa, ohjelma merkitsee laitteen irrotetuksi, päivittää portit ja voi yrittää yhdistää uudelleen."
    },
    {
        "type": "subheading",
        "text": "Näppäimistömorse"
    },
    {
        "type": "paragraph",
        "text": "Näppäimistömorse tekee tietokoneen näppäimistöstä virtuaalisen straight keyn. Kun valittu näppäin painetaan alas, ohjelma aloittaa tone-tapahtuman ajanoton. Kun näppäin vapautetaan, ohjelma muodostaa painalluksesta straight-lähteisen tone-tapahtuman."
    },
    {
        "type": "paragraph",
        "text": "Näppäimistömorse käyttää samaa raakatelemetrian käsittelyä kuin fyysinen laite. Siksi se näkyy raakatelemetriassa, dekoodautuu telemetriasyötteeksi ja vaikuttaa pisteytykseen samalla periaatteella kuin straight key."
    },
    {
        "type": "paragraph",
        "text": "Kun näppäimistömorse otetaan käyttöön, ohjelma pitää telemetrian totuutena ja estää sarjaportin automaattihaun. Tämä ehkäisee sitä, että HID-teksti, fyysinen serial-laite ja virtuaalinen näppäimistöavain sekoittuisivat samaan suoritukseen."
    },
    {
        "type": "subheading",
        "text": "Näppäimistömorsen näppäin"
    },
    {
        "type": "paragraph",
        "text": "Syöte ja yhteys -välilehdellä voi valita, mitä näppäintä käytetään virtuaalisena straight keynä. Vaihtoehtoja voivat olla esimerkiksi välilyönti, Enter, nuolinäppäimet, Ctrl-, Shift- ja Alt-näppäimet sekä funktionäppäimet."
    },
    {
        "type": "paragraph",
        "text": "Oletuksena välilyönti on helppo käyttää, mutta esimerkiksi oikea Ctrl tai F9 voi olla parempi, jos välilyönti häiritsee muuta käyttöliittymän toimintaa."
    },
    {
        "type": "subheading",
        "text": "Käytä telemetriaa totuutena"
    },
    {
        "type": "paragraph",
        "text": "Kun tämä asetus on päällä, pisteytys käyttää telemetriasta dekoodattua tekstiä. Tämä on suositeltu tila, koska se perustuu painallusten todelliseen ajoitukseen."
    },
    {
        "type": "paragraph",
        "text": "Kun asetus ei ole päällä, pisteytys käyttää HID-syötekentän tekstiä. Tämä voi olla hyödyllistä laitteen testauksessa, mutta HID ei sisällä samaa ajoitusdataa kuin raakatelemetria."
    },
    {
        "type": "paragraph",
        "text": "Näppäimistömorse tarvitsee telemetrian totuudeksi, koska se ei tuota valmista tekstisyötettä vaan tone-tapahtumia. Siksi ohjelma palauttaa tämän asetuksen päälle, jos näppäimistömorse on käytössä."
    },
    {
        "type": "subheading",
        "text": "Pidä syötekenttä aktiivisena"
    },
    {
        "type": "paragraph",
        "text": "Tämä pitää syötekentän aktiivisena, jotta HID-syöte ja näppäimistötapahtumat menevät oikeaan paikkaan eivätkä esimerkiksi painikkeisiin. Asetus auttaa erityisesti silloin, kun laite toimii myös näppäimistönä."
    },
    {
        "type": "heading",
        "text": "Kierroksen käynnistyminen ja päättyminen"
    },
    {
        "type": "subheading",
        "text": "Käynnistyminen"
    },
    {
        "type": "paragraph",
        "text": "Kierroksen kello käynnistyy ensimmäisestä telemetriatapahtumasta, ensimmäisestä näppäimistömorsen tone-tapahtumasta tai ensimmäisestä HID-syötteestä. Ennen ensimmäistä syötettä näkyvä vertailuaika on vain ohjearvo."
    },
    {
        "type": "subheading",
        "text": "Aloitus avaintapahtumilla"
    },
    {
        "type": "paragraph",
        "text": "Jos harjoitus ei ole käynnissä, fyysisen laitteen tai näppäimistömorsen tone-tapahtumat voivat käynnistää aloituslaskennan. Oletuksena seitsemän tone-tapahtumaa kolmen sekunnin sisällä aloittaa kolmen sekunnin lähtölaskennan ja sen jälkeen harjoituksen."
    },
    {
        "type": "subheading",
        "text": "Normaali päättyminen"
    },
    {
        "type": "paragraph",
        "text": "Telemetriakäytössä kierros päättyy normaalisti vasta, kun lopullinen dekoodattu teksti vastaa tavoitetta ilman välilyöntien poistamista. Tämä ehkäisee liian aikaista päättymistä tilanteissa, joissa dekooderi voisi väliaikaisesti näyttää riittävän pitkän mutta väärin jaksottuneen tekstin."
    },
    {
        "type": "subheading",
        "text": "Pitkän tauon automaattinen lopetus"
    },
    {
        "type": "paragraph",
        "text": "Jos syöte ei näytä valmiilta, mutta käyttäjä on selvästi lopettanut lähettämisen, ohjelma voi päättää kierroksen pitkän hiljaisen tauon jälkeen. Tämä toimii vain telemetriatilassa ja vain silloin, kun kierroksella on jo vähintään yksi tone-tapahtuma."
    },
    {
        "type": "paragraph",
        "text": "Lopetuksen hiljaisuusraja on pidempi kahdesta arvosta. Ensimmäinen on valittu määrä morseyksiköitä kerrottuna nykyisellä gap-yksiköllä. Toinen on vähimmäistauko sekunteina."
    },
    {
        "type": "subheading",
        "text": "Miksi pitkä tauko ei vääristä nopeutta"
    },
    {
        "type": "paragraph",
        "text": "Kierroksen WPM- ja aikamittaus perustuu raakatelemetrian ensimmäiseen ja viimeiseen äänielementtiin. Lopussa oleva odottelu, jolla ohjelma varmistaa päättymisen, ei itsessään pidennä varsinaista lähetyskestoa."
    },
    {
        "type": "heading",
        "text": "Tunnistus ja ajoitusprofiili"
    },
    {
        "type": "subheading",
        "text": "Adaptiivinen dekoodaus"
    },
    {
        "type": "paragraph",
        "text": "Dekooderi käyttää tavoite-WPM:ää aloitusarviona, mutta arvioi kierroksen aikana erikseen straight- ja iambic-lähteiden ajoitusta. Straightissa arvioidaan elementtiyksikköä pisteiden ja viivojen perusteella sekä gap-yksikköä tauoista. Iambicissa käyttäjän hallitsema osa on erityisesti merkkien ja sanojen välinen tauotus."
    },
    {
        "type": "subheading",
        "text": "Opittu ajoitusprofiili"
    },
    {
        "type": "paragraph",
        "text": "Ajoitusprofiili rakennetaan viimeisistä hyvistä kierroksista. Kierroksen pitää ylittää profiilin minimitarkkuus, minimipuhtaus ja ajoituspisteraja. Lisäksi liian äärimmäiset elementit tai tauot voivat estää kierroksen käytön profiilin oppimisessa."
    },
    {
        "type": "subheading",
        "text": "Milloin profiili otetaan käyttöön"
    },
    {
        "type": "paragraph",
        "text": "Profiili vaatii oletuksena vähintään 100 hyväksyttyä kierrosta kyseisestä lähteestä. Näytetty luottamus kasvaa kohti täyttä luottamusta noin 300 hyväksyttyyn kierrokseen asti. Profiilin pitää myös ylittää siemenkäytön minimiluottamus, jotta sitä käytetään dekooderin aloitusarvona."
    },
    {
        "type": "subheading",
        "text": "Päivitä profiili"
    },
    {
        "type": "paragraph",
        "text": "Päivitä profiili laskee profiilin yhteenvedon uudelleen ja päivittää straight- ja iambic-palkit. Palkki näyttää, kerätäänkö dataa, onko profiili melkein valmis vai onko se käytössä."
    },
    {
        "type": "subheading",
        "text": "Raakatelemetrian näyttö"
    },
    {
        "type": "paragraph",
        "text": "Pikseleitä / ajoitusyksikkö säätää raakatelemetrian vaakasuuntaista skaalaa. Suurempi arvo venyttää aikajanaa ja tekee yksityiskohdista helpommin näkyviä."
    },
    {
        "type": "heading",
        "text": "Pisteytys"
    },
    {
        "type": "subheading",
        "text": "Edit distance -kohdistus"
    },
    {
        "type": "paragraph",
        "text": "Pisteytys kohdistaa tavoitteen ja syötteen edit distance -menetelmällä. Tämä estää yhden ylimääräisen tai puuttuvan merkin siirtämästä koko loppua vääräksi."
    },
    {
        "type": "subheading",
        "text": "Virhetyypit"
    },
    {
        "type": "bullet",
        "text": "Väärä merkki tarkoittaa, että tavoitemerkin kohdalla tuli toinen merkki."
    },
    {
        "type": "bullet",
        "text": "Ylimääräinen merkki tarkoittaa, että syötteessä oli merkki, jolle ei löytynyt vastaavaa tavoitemerkkiä."
    },
    {
        "type": "bullet",
        "text": "Puuttuva merkki tarkoittaa, että tavoitemerkki jäi antamatta."
    },
    {
        "type": "bullet",
        "text": "Tuntematon merkki � tarkoittaa, että morsekuviota ei tunnistettu tuetuksi merkiksi."
    },
    {
        "type": "subheading",
        "text": "Tarkkuus"
    },
    {
        "type": "paragraph",
        "text": "Tarkkuus lasketaan varsinaisista merkeistä ilman välilyöntejä. Se kertoo, kuinka moni tavoitteen kirjain, numero tai muu merkki meni oikein. Välilyöntivirheet eivät laske tarkkuutta."
    },
    {
        "type": "subheading",
        "text": "Puhtaus"
    },
    {
        "type": "paragraph",
        "text": "Puhtaus laskee koko yrityksen siisteyttä. Puhtaudessa sisäiset välilyönnit ovat mukana, joten puuttuva, ylimääräinen tai väärässä kohdassa oleva ryhmäväli heikentää puhtautta."
    },
    {
        "type": "paragraph",
        "text": "Puhtauden jakajana käytetään suurinta arvoa tavoitteen pituudesta, syötteen pituudesta ja yhdestä. Näin myös ylimääräiset merkit vaikuttavat tulokseen järkevästi."
    },
    {
        "type": "subheading",
        "text": "Kokonaispisteet"
    },
    {
        "type": "paragraph",
        "text": "Kokonaispisteet yhdistävät tarkkuuden, puhtauden, nopeuden ja ajoituksen. Nykyisessä mallissa painot ovat tarkkuus 60 prosenttia, puhtaus 20 prosenttia, nopeus 10 prosenttia ja ajoitus 10 prosenttia."
    },
    {
        "type": "paragraph",
        "text": "Jos nopeus- tai ajoitusosuus ei ole saatavilla, kyseinen osa käsitellään neutraalina. Nopeus ei anna yli sadan prosentin bonusta, vaikka suoritus olisi tavoiteaikaa nopeampi."
    },
    {
        "type": "heading",
        "text": "Välilyönnit"
    },
    {
        "type": "paragraph",
        "text": "Alun ja lopun tyhjät merkit siivotaan ennen pisteytystä. Sisäiset välilyönnit säilyvät puhtaus- ja virhelaskennassa."
    },
    {
        "type": "bullet",
        "text": "Puuttuva tavoitevälilyönti heikentää puhtautta."
    },
    {
        "type": "bullet",
        "text": "Ylimääräinen sisäinen välilyönti heikentää puhtautta."
    },
    {
        "type": "bullet",
        "text": "Väärässä kohdassa oleva välilyönti voi näkyä edit distance -kohdistuksessa virheenä."
    },
    {
        "type": "bullet",
        "text": "Tarkkuusprosentti ei laske pelkän välilyöntivirheen takia, koska tarkkuus mittaa varsinaisia merkkejä ilman välilyöntejä."
    },
    {
        "type": "paragraph",
        "text": "Esimerkiksi tavoite ABCDE ABCDE ja syöte ABCDEABCDE voivat saada hyvät varsinaisten merkkien tarkkuuspisteet, mutta puhtaus laskee puuttuvan ryhmävälin vuoksi."
    },
    {
        "type": "heading",
        "text": "Ajoituspisteet"
    },
    {
        "type": "subheading",
        "text": "Yleinen periaate"
    },
    {
        "type": "paragraph",
        "text": "Ajoituspisteet kuvaavat, kuinka lähellä morseajoitus on odotettua rytmiä. Ajoitus ei korvaa tarkkuutta tai puhtautta, vaan muodostaa oman 10 prosentin osansa kokonaispisteistä ja vaikuttaa myös netto-WPM:n ajoituskertoimeen."
    },
    {
        "type": "subheading",
        "text": "Straight key -ajoitus"
    },
    {
        "type": "paragraph",
        "text": "Straight-kierroksen ajoituksessa huomioidaan pisteiden tasaisuus, viivojen tasaisuus, viivan ja pisteen suhde sekä taukojen laatu. Nykyiset painot ovat dit-tasaisuus 20 prosenttia, dah-tasaisuus 20 prosenttia, dah/dit-suhde 25 prosenttia ja gap-osuus 35 prosenttia."
    },
    {
        "type": "paragraph",
        "text": "Straightin gap-osuuden sisällä painot ovat merkin sisäinen väli 30 prosenttia, kirjainväli 55 prosenttia ja sanaväli 15 prosenttia."
    },
    {
        "type": "subheading",
        "text": "Iambic-ajoitus"
    },
    {
        "type": "paragraph",
        "text": "Iambicissa pisteiden, viivojen ja merkkien sisäisten välien pituudet syntyvät pitkälti keyerin logiikasta. Siksi iambic-kierroksen ajoituspisteissä ei pisteytetä intra-gap-välejä, vaan käyttäjän hallitsemia kirjain- ja sanavälejä."
    },
    {
        "type": "paragraph",
        "text": "Iambicissa gap-osuuden painot ovat kirjainväli 75 prosenttia ja sanaväli 25 prosenttia. Jos pisteytettäviä kirjain- tai sanavälejä ei ole, iambic-ajoitusta ei pidä tulkita täydelliseksi, vaan dataa on liian vähän."
    },
    {
        "type": "subheading",
        "text": "Miten yksittäinen gap pisteytetään"
    },
    {
        "type": "paragraph",
        "text": "Kirjainvälin tavoite on yleensä 3 yksikköä ja sanavälin tavoite 7 yksikköä. Gap-pisteet laskevat sen mukaan, kuinka monta yksikköä havaittu väli poikkeaa tavoitteesta. Oletusmallissa noin 3 yksikön virhe vie gap-pisteen nollaan."
    },
    {
        "type": "subheading",
        "text": "Dit- ja dah-hajonta"
    },
    {
        "type": "paragraph",
        "text": "Dit-hajonta ja dah-hajonta kertovat, kuinka paljon straight-painallusten pituudet vaihtelevat. Pieni prosentti tarkoittaa tasaista lähetystä. Suuri prosentti tarkoittaa, että samanlaiset elementit vaihtelevat paljon."
    },
    {
        "type": "subheading",
        "text": "Viivasuhde"
    },
    {
        "type": "paragraph",
        "text": "Viivasuhde kuvaa dahin ja ditin pituussuhdetta straight-käytössä. Ihanne on noin 3.00. Käyttöliittymä näyttää tämän laatuprosenttina ja suluissa varsinaisena suhteena."
    },
    {
        "type": "heading",
        "text": "WPM ja PARIS-laskenta"
    },
    {
        "type": "subheading",
        "text": "PARIS-yksiköt"
    },
    {
        "type": "paragraph",
        "text": "Morsewurst laskee WPM:n tavoitetekstin todellisista morseyksiköistä. Dit on 1 yksikkö, dah on 3 yksikköä, saman merkin elementtien väli on 1 yksikkö, kirjainväli on 3 yksikköä ja sanaväli on 7 yksikköä."
    },
    {
        "type": "subheading",
        "text": "Toteutunut PARIS-WPM"
    },
    {
        "type": "paragraph",
        "text": "Toteutunut WPM lasketaan kaavalla morseyksiköt kertaa 1 200 000 jaettuna kierroksen kestolla mikrosekunteina. Tämä vastaa PARIS-tyyppistä WPM-laskentaa ja huomioi sen, että eri merkeillä on erilainen kesto."
    },
    {
        "type": "subheading",
        "text": "Vertailuaika"
    },
    {
        "type": "paragraph",
        "text": "Vertailuaika lasketaan samoista morseyksiköistä ja tavoite-WPM:stä. Se ei ole aikaraja, vaan vertailuarvo nopeuspisteille."
    },
    {
        "type": "subheading",
        "text": "Brutto-WPM"
    },
    {
        "type": "paragraph",
        "text": "Brutto-WPM kertoo tavoitetekstin morseyksiköihin ja toteutuneeseen kestoon perustuvan lähetysnopeuden. Se ei vähennä virheitä."
    },
    {
        "type": "subheading",
        "text": "Netto-WPM"
    },
    {
        "type": "paragraph",
        "text": "Netto-WPM perustuu brutto-WPM:ään, mutta sitä kerrotaan tarkkuus-, puhtaus- ja ajoituskertoimilla. Virheet, epäpuhtaus ja heikko ajoitus laskevat sitä."
    },
    {
        "type": "subheading",
        "text": "Laite-WPM"
    },
    {
        "type": "paragraph",
        "text": "Laite-WPM perustuu telemetriasta saatuihin elementtikohtaisiin WPM-arvoihin, jos niitä on saatavilla. Se kuvaa laitteen havaintojen mukaista elementtinopeutta."
    },
    {
        "type": "heading",
        "text": "Tehokas WPM"
    },
    {
        "type": "paragraph",
        "text": "Tehokas WPM on historian perusteella laskettu käytännön nopeusarvio hyvistä kierroksista. Sitä käytetään harjoitusnopeuden ehdottamiseen."
    },
    {
        "type": "bullet",
        "text": "Ohjelma lukee asetetun määrän viimeisimpiä kierroksia."
    },
    {
        "type": "bullet",
        "text": "Mukaan otetaan vain kierrokset, jotka ylittävät minimitarkkuuden ja minimipuhtauden."
    },
    {
        "type": "bullet",
        "text": "Jokaiselle hyväksytylle kierrokselle lasketaan PARIS-WPM."
    },
    {
        "type": "bullet",
        "text": "Lopullinen arvo on hyväksyttyjen kierrosten mediaani."
    },
    {
        "type": "bullet",
        "text": "Harjoitusnopeuden ehdotukseen tarvitaan vähintään asetettu minimimäärä sopivia kierroksia."
    },
    {
        "type": "heading",
        "text": "Taitotaso"
    },
    {
        "type": "subheading",
        "text": "Mitä taitotaso mittaa"
    },
    {
        "type": "paragraph",
        "text": "Taitotaso on pitkän aikavälin arvio käytännön morseosaamisesta. Se ei ole sama asia kuin yhden kierroksen pistemäärä. Taitotaso päivittyy jokaisen tallennetun kierroksen jälkeen ja siitä tallennetaan snapshot tietokantaan."
    },
    {
        "type": "subheading",
        "text": "Riittävän pitkät kierrokset"
    },
    {
        "type": "paragraph",
        "text": "Taitotasoon otetaan mukaan vain riittävän pitkät kierrokset. Oletusarvo on vähintään 12 varsinaista tavoitemerkkiä ilman välilyöntejä."
    },
    {
        "type": "subheading",
        "text": "Molemmat avaintyypit"
    },
    {
        "type": "paragraph",
        "text": "Yleistaitotaso vaatii laskentakelpoista dataa sekä straight- että iambic-kierroksista. Jos toista avaintyyppiä ei ole harjoiteltu tarpeeksi, taitotasoa ei vielä voida laskea."
    },
    {
        "type": "subheading",
        "text": "Straight WPM ja Iambic WPM"
    },
    {
        "type": "paragraph",
        "text": "Straight WPM ja Iambic WPM ovat lähdekohtaisia mediaaniarvoja hyvistä, riittävän pitkistä kierroksista. Kierros luokitellaan sille lähteelle, jolla on kierroksella eniten pisteytettyjä tavoitemerkkejä."
    },
    {
        "type": "subheading",
        "text": "Molemmilla WPM"
    },
    {
        "type": "paragraph",
        "text": "Molemmilla WPM on tasapainotettu onnistunut WPM. Se käyttää heikompaa lähdekohtaista mediaania eli käytännössä pienempää arvoa straight- ja iambic-WPM:stä. Näin korkea taitotaso edellyttää molempien lähetystapojen hallintaa."
    },
    {
        "type": "subheading",
        "text": "Yleistaito WPM"
    },
    {
        "type": "paragraph",
        "text": "Yleistaito WPM perustuu molempien lähteiden laatuun. Ensin lasketaan kummallekin avaintyypille laatu- ja puhtauspainotettu raw skill -mediaani. Varsinaiseksi pohjaksi valitaan heikompi näistä kahdesta. Sitä korjataan ajoituskertoimella ja merkkihallinnan luottamuskorjauksella."
    },
    {
        "type": "subheading",
        "text": "Level"
    },
    {
        "type": "paragraph",
        "text": "Level lasketaan Yleistaito WPM -arvosta. Yksi WPM vastaa 2,5 leveliä. Esimerkiksi raw skill 12,0 vastaa noin leveliä 30. Tason nimi määräytyy level-alueen perusteella."
    },
    {
        "type": "subheading",
        "text": "Tason nimet"
    },
    {
        "type": "bullet",
        "text": "Level 0 näyttää Ei vielä tasoa."
    },
    {
        "type": "bullet",
        "text": "Level 1-4 näyttää Ensiaskeleet."
    },
    {
        "type": "bullet",
        "text": "Level 5-9 näyttää Aloittelija."
    },
    {
        "type": "bullet",
        "text": "Level 10-14 näyttää Harjoittelija."
    },
    {
        "type": "bullet",
        "text": "Level 15-24 näyttää Perustaso."
    },
    {
        "type": "bullet",
        "text": "Level 25-34 näyttää Kehittyvä operaattori."
    },
    {
        "type": "bullet",
        "text": "Level 35-49 näyttää Taitava operaattori."
    },
    {
        "type": "bullet",
        "text": "Level 50-74 näyttää Edistynyt operaattori."
    },
    {
        "type": "bullet",
        "text": "Level 75-99 näyttää Kokenut operaattori."
    },
    {
        "type": "bullet",
        "text": "Level 100-124 näyttää Nopea operaattori."
    },
    {
        "type": "bullet",
        "text": "Level 125 ja yli näyttää Huipputason operaattori."
    },
    {
        "type": "subheading",
        "text": "Luottamus"
    },
    {
        "type": "paragraph",
        "text": "Luottamus kertoo, kuinka hyvin nykyinen harjoitushistoria riittää todistamaan näytetyn arvion. Luottamus muodostuu sopivien kierrosten määrästä, merkkien hallinnasta ja merkkivalikoiman kattavuudesta."
    },
    {
        "type": "paragraph",
        "text": "Sanallinen asteikko on matala alle 20 prosenttia, alustava 20-44 prosenttia, kohtalainen 45-69 prosenttia, hyvä 70-89 prosenttia ja erinomainen 90 prosentista ylöspäin."
    },
    {
        "type": "subheading",
        "text": "Merkit ja kattavuus"
    },
    {
        "type": "paragraph",
        "text": "Merkit-arvo kuvaa odotettujen merkkien hallintaa. Kattavuus kertoo, kuinka suuri osa odotetusta merkkivalikoimasta on saanut vähintään asetetun määrän yrityksiä. Oletuksena kattavuuden merkki vaatii vähintään 5 yritystä."
    },
    {
        "type": "subheading",
        "text": "Min.kier. ja Yht.kier."
    },
    {
        "type": "paragraph",
        "text": "Min.kier. näyttää heikomman avaintyypin sopivien kierrosten määrän. Yht.kier. näyttää straight- ja iambic-lähdekohtaisten sopivien kierrosten yhteenlasketun määrän taitotasopaneelissa."
    },
    {
        "type": "heading",
        "text": "Vaikeimmat merkit"
    },
    {
        "type": "paragraph",
        "text": "Vaikeimmat merkit lasketaan tavoitemerkeistä. Jos käyttäjä lähettää ylimääräisen merkin, ylimääräisestä merkistä ei tule vaikeaa merkkiä, koska insertiolla ei ole target_char-arvoa."
    },
    {
        "type": "paragraph",
        "text": "Jos tavoitemerkki menee väärin tai jää puuttumaan, virhe kirjautuu kyseiselle tavoitemerkille. Tämä pitää ongelmamerkkitilaston sidottuna siihen, mitä oli tarkoitus lähettää."
    },
    {
        "type": "paragraph",
        "text": "Tuntematon syötemerkki � voi näkyä entered_char-kentässä, mutta ongelmatilasto perustuu tavoitemerkkiin. Siksi tuntematon dekoodaus ei tee �-merkistä harjoiteltavaa ongelmamerkkiä."
    },
    {
        "type": "heading",
        "text": "Asetukset-ikkuna"
    },
    {
        "type": "subheading",
        "text": "Nopeus"
    },
    {
        "type": "paragraph",
        "text": "Nopeus-välilehdellä säädetään tavoite-WPM:ää, käynnistetään äänitesti ja pyydetään ohjelmaa ehdottamaan harjoitusnopeutta historian perusteella."
    },
    {
        "type": "subheading",
        "text": "Tunnistus"
    },
    {
        "type": "paragraph",
        "text": "Tunnistus-välilehdellä hallitaan opittua ajoitusprofiilia, profiilin tarkasteluikkunaa, minimitarkkuutta, minimipuhtautta, pitkän hiljaisuuden automaattista lopetusta sekä raakatelemetrian näyttöasteikkoa."
    },
    {
        "type": "subheading",
        "text": "Vaikeimmat merkit"
    },
    {
        "type": "paragraph",
        "text": "Vaikeimmat merkit -välilehdellä säädetään vaikeimpien merkkien painotusprosenttia, käytettävien vaikeiden merkkien määrää ja sitä, monenko viimeisimmän kierroksen perusteella vaikeimmat merkit lasketaan."
    },
    {
        "type": "subheading",
        "text": "Äänet"
    },
    {
        "type": "paragraph",
        "text": "Äänet-välilehdellä on yleinen äänikytkin sekä erilliset kytkimet harjoitussarjan valmistumiselle, sarjalaitteen yhdistämiselle, yhteyden katkeamiselle ja levelin nousulle."
    },
    {
        "type": "subheading",
        "text": "Syöte ja yhteys"
    },
    {
        "type": "paragraph",
        "text": "Syöte ja yhteys -välilehdellä hallitaan telemetrian käyttöä totuutena, syötekentän fokusta, automaattista sarjayhdistämistä, näppäimistömorsea, näppäimistömorsen näppäinvalintaa ja pitkän tauon automaattista lopetusta."
    },
    {
        "type": "subheading",
        "text": "Tehokas WPM"
    },
    {
        "type": "paragraph",
        "text": "Tehokas WPM -välilehdellä säädetään, montako viimeisintä kierrosta käytetään tehokkaan WPM:n arvioon sekä minimitarkkuus ja minimipuhtaus hyväksytyille kierroksille."
    },
    {
        "type": "subheading",
        "text": "Taitotaso"
    },
    {
        "type": "paragraph",
        "text": "Taitotaso-välilehdellä säädetään, kuinka monesta viimeisimmästä riittävän pitkästä kierroksesta taitotaso lasketaan."
    },
    {
        "type": "subheading",
        "text": "Tilastot"
    },
    {
        "type": "paragraph",
        "text": "Tilastot-välilehdellä säädetään, kuinka monesta viimeisimmästä kierroksesta pääikkunan historiayhteenveto lasketaan."
    },
    {
        "type": "subheading",
        "text": "Debug"
    },
    {
        "type": "paragraph",
        "text": "Debug-välilehdellä voi ottaa kierroskohtaisen debug-snapshotin käyttöön, tallentaa koko debug-historian, avata debug-ikkunan, kopioida viimeisimmän debug-snapshotin ja tyhjentää debug-datan."
    },
    {
        "type": "heading",
        "text": "Tilastot"
    },
    {
        "type": "paragraph",
        "text": "Tilastot-ikkunassa voi tarkastella harjoitushistoriaa valitulla aikavälillä. Pikavalintoja ovat 30 päivää, 90 päivää, vuosi ja kaikki."
    },
    {
        "type": "bullet",
        "text": "Yhteenveto näyttää kierrosmäärän, tarkkuuden, puhtauden, pisteet, WPM-arvot, virheet, viivasuhteen sekä dit- ja dah-hajonnan."
    },
    {
        "type": "bullet",
        "text": "WPM-kehitys näyttää brutto-WPM:n, netto-WPM:n, laite-WPM:n sekä lähdekohtaiset straight- ja iambic-WPM-arvot, jos niitä on saatavilla."
    },
    {
        "type": "bullet",
        "text": "Tarkkuus, puhtaus ja pisteet -näkymä näyttää laadun kehityksen."
    },
    {
        "type": "bullet",
        "text": "Taitotaso-näkymä näyttää skill-snapshotien kehityksen, kuten raw skillin, effective WPM:n ja levelin."
    },
    {
        "type": "bullet",
        "text": "Vaikeimmat merkit -näkymä näyttää valitun aikavälin merkkikohtaiset virheprosentit."
    },
    {
        "type": "paragraph",
        "text": "Keskiarvo-valinta rauhoittaa kuvaajia. Vaihtoehdot ovat Automaattinen, Raaka data, 15 minuuttia, 1 tunti, Päivä, Viikko ja Kuukausi. Ikkuna päivittyy myös automaattisesti muutaman sekunnin välein."
    },
    {
        "type": "heading",
        "text": "Debug-data"
    },
    {
        "type": "paragraph",
        "text": "Debug-snapshot tallennetaan vasta kierroksen päätyttyä, joten se ei kirjoita tiedostoon live-morsetuksen aikana. Snapshot sisältää muun muassa tone-tapahtumat, lasketut tauot, ajoitusarviot, rescue-tiedot, asetukset ja lopullisen tulkinnan."
    },
    {
        "type": "bullet",
        "text": "Näytä viimeisin kierros näyttää latest_round_debug.json-tiedoston sisällön."
    },
    {
        "type": "bullet",
        "text": "Näytä historia siistinä näyttää debug_history.jsonl-tiedoston luettavammassa muodossa."
    },
    {
        "type": "bullet",
        "text": "Näytä raaka JSONL näyttää debug-historian sellaisenaan."
    },
    {
        "type": "bullet",
        "text": "Kopioi näkyvä teksti kopioi ruudulla olevan debug-datan leikepöydälle."
    },
    {
        "type": "bullet",
        "text": "Avaa kansio avaa debug-hakemiston tiedostonhallinnassa."
    },
    {
        "type": "bullet",
        "text": "Tyhjennä debug-data poistaa latest_round_debug.json- ja debug_history.jsonl-tiedostot."
    },
    {
        "type": "heading",
        "text": "Poista harjoituksia"
    },
    {
        "type": "paragraph",
        "text": "Poista harjoituksia -ikkunassa voi poistaa yksittäisen harjoituksen, valitun aikavälin harjoitukset tai kaikki harjoitukset."
    },
    {
        "type": "bullet",
        "text": "Päivitä lista lataa harjoituslistan uudelleen."
    },
    {
        "type": "bullet",
        "text": "Laske aikavälin määrä kertoo, montako harjoitusta valittuun aikaväliin osuu."
    },
    {
        "type": "bullet",
        "text": "Poista valittu poistaa taulukosta valitun harjoituksen."
    },
    {
        "type": "bullet",
        "text": "Poista aikaväli poistaa valitulle aikavälille osuvat harjoitukset."
    },
    {
        "type": "bullet",
        "text": "Poista kaikki poistaa kaikki tallennetut harjoitukset."
    },
    {
        "type": "paragraph",
        "text": "Poisto poistaa myös harjoitukseen liittyvät telemetriatapahtumat, merkkikohtaiset tulokset ja taitotason snapshotit. Vaikeimpien merkkien tilasto rakennetaan uudelleen jäljelle jäävästä datasta."
    },
    {
        "type": "note",
        "text": "Poistoa ei voi perua. Tee tietokannasta varmuuskopio ennen suuria poistoja."
    },
    {
        "type": "heading",
        "text": "Network"
    },
    {
        "type": "paragraph",
        "text": "Network-tila mahdollistaa morseäänen lähettämisen ja vastaanottamisen verkon yli. Paikallinen ohjelma lähettää omat tone-tapahtumat WebSocket-yhteyden kautta huoneeseen, ja vastaanotetut tone-tapahtumat toistetaan paikallisena äänenä."
    },
    {
        "type": "subheading",
        "text": "Network-ikkuna"
    },
    {
        "type": "paragraph",
        "text": "Network-ikkunassa voi antaa kutsutunnuksen, valita huoneen, liittyä relay-palvelimen kautta huoneeseen, käynnistää oman huoneen, katkaista yhteyden ja säätää vastaanoton asetuksia."
    },
    {
        "type": "paragraph",
        "text": "Ohjelman oletuspalvelin on julkinen relay-osoite. Network-asetuksiin tallennetaan muun muassa kutsutunnus, huone, salasana, palvelimen osoite, lähetysasetus ja vastaanoton ääniasetukset."
    },
    {
        "type": "subheading",
        "text": "Julkiset ja yksityiset huoneet"
    },
    {
        "type": "paragraph",
        "text": "Relay-palvelin voi tarjota julkisia huoneita, jotka näkyvät huonelistassa. Julkisen huoneen nimen vieressä voidaan näyttää käyttäjämäärä ja enimmäismäärä. Yksityiseen huoneeseen liitytään huoneen nimellä tai tunnisteella, ja huone voidaan suojata salasanalla."
    },
    {
        "type": "subheading",
        "text": "Liittyminen huoneeseen"
    },
    {
        "type": "paragraph",
        "text": "Kun liityt huoneeseen, ohjelma muodostaa WebSocket-yhteyden palvelimeen ja lähettää tunnistautumistiedot. Sen jälkeen omat tone-tapahtumat voidaan lähettää muille huoneen käyttäjille, jos lähetys on käytössä."
    },
    {
        "type": "subheading",
        "text": "Oman huoneen käynnistäminen"
    },
    {
        "type": "paragraph",
        "text": "Oman huoneen käynnistäminen käyttää paikallista huonepalvelinta. Tämä sopii lähiverkko- tai testikäyttöön. Julkiseen internetiin avattavissa yhteyksissä kannattaa käyttää suojattua yhteyttä, käänteistä välityspalvelinta, VPN:ää tai muuta hallittua verkkoratkaisua."
    },
    {
        "type": "subheading",
        "text": "Lähetys"
    },
    {
        "type": "paragraph",
        "text": "Kun lähetys on käytössä, ohjelma julkaisee paikalliset tone-tapahtumat verkkoon. Tone voi tulla fyysiseltä sarjalaitteelta tai näppäimistömorsesta. Jos lähetys poistetaan käytöstä, voit edelleen vastaanottaa muiden ääntä, mutta omia tone-tapahtumia ei lähetetä."
    },
    {
        "type": "subheading",
        "text": "Vastaanotto ja äänentoisto"
    },
    {
        "type": "paragraph",
        "text": "Vastaanotetut tone-tapahtumat eivät ole valmiita äänitiedostoja, vaan ajoitustietoa. Ohjelma muodostaa niistä paikallisen äänen käyttäen valittua taajuutta, äänenvoimakkuutta, aaltomuotoa ja äänilaitetta."
    },
    {
        "type": "paragraph",
        "text": "Vastaanoton ääniasetuksia ovat esimerkiksi vastaanoton päälläolo, viivepuskuri, taajuus, äänenvoimakkuus, aaltomuoto, näytteenottotaajuus, blocksize, latency ja valinnainen äänilaite."
    },
    {
        "type": "subheading",
        "text": "Viivepuskuri"
    },
    {
        "type": "paragraph",
        "text": "Viivepuskuri antaa verkon kautta tuleville tone-tapahtumille aikaa saapua ennen niiden toistamista. Suurempi puskuri vähentää myöhässä tulevien äänten riskiä, mutta lisää vastaanoton viivettä."
    },
    {
        "type": "paragraph",
        "text": "Jos tone saapuu liian myöhään, ohjelma voi ajoittaa sen heti, hylätä liian vanhan tapahtuman tai ehdottaa suurempaa viivepuskuria. Ehdotus perustuu havaittuun myöhästymiseen ja turvamarginaaliin."
    },
    {
        "type": "subheading",
        "text": "Yhteyden tila ja ilmoitukset"
    },
    {
        "type": "paragraph",
        "text": "Network-ikkuna näyttää yhteyden tilaa ja palvelimen ilmoituksia. Yhteys voidaan pysäyttää käsin, ja ohjelma tyhjentää vastaanoton puskurin sekä pysäyttää paikallisen network-äänentoiston yhteyden katketessa."
    },
    {
        "type": "subheading",
        "text": "Server info ja ping"
    },
    {
        "type": "paragraph",
        "text": "Ohjelma voi pyytää palvelimelta tietoja ja ping-vastauksia. Näitä käytetään yhteyden tilan, viiveen ja palvelimen toiminnan arvioimiseen."
    },
    {
        "type": "subheading",
        "text": "Network ja harjoituspisteytys"
    },
    {
        "type": "paragraph",
        "text": "Network-vastaanotto on ensisijaisesti kuuntelua ja yhteydenpitoa varten. Harjoituksen pisteytys perustuu paikalliseen syötteeseen, kuten fyysiseen laitteeseen, näppäimistömorseen tai HID-syötteeseen. Muiden käyttäjien verkosta vastaanotettu ääni ei normaalisti ole oma harjoitussuorituksesi."
    },
    {
        "type": "subheading",
        "text": "Network ja näppäimistömorse"
    },
    {
        "type": "paragraph",
        "text": "Näppäimistömorse toimii myös network-lähetyksen kanssa, koska se tuottaa tavallisia straight-lähteisiä tone-tapahtumia. Kun network-yhteys on käynnissä ja lähetys on käytössä, valitulla näppäimellä tehdyt painallukset voidaan lähettää huoneeseen samalla tavalla kuin fyysisen straight keyn painallukset."
    },
    {
        "type": "subheading",
        "text": "Network-asetusten tallennus"
    },
    {
        "type": "paragraph",
        "text": "Network-asetukset tallennetaan erillisiin network-asetuksiin. Käyttöliittymän yleiset asetukset, kuten näppäimistömorse ja Syöte ja yhteys -välilehden valinnat, tallennetaan ui_settings.json-tiedostoon."
    },
    {
        "type": "heading",
        "text": "Tallennus ja tietokanta"
    },
    {
        "type": "paragraph",
        "text": "Harjoitukset tallennetaan SQLite-tietokantaan käyttäjäkohtaiseen AppData-sijaintiin. Ohjelman voi siis asentaa muualle ilman, että harjoitusdata on ohjelmakansion sisällä."
    },
    {
        "type": "code",
        "text": "APP_DATA_DIR = Path(os.environ.get(\"APPDATA\", str(Path.home()))) / \"Morsewurst\"\nDATA_DIR = APP_DATA_DIR / \"data\"\nDB_PATH = DATA_DIR / \"morsewurst.sqlite3\""
    },
    {
        "type": "paragraph",
        "text": "Käyttöliittymän asetukset tallennetaan samaan datahakemistoon tiedostoon ui_settings.json. Tähän kuuluvat esimerkiksi harjoitusasetukset, Syöte ja yhteys -välilehden asetukset, näppäimistömorse, näppäimistömorsen valittu näppäin, tilastoasetukset ja debug-valinnat. Debug-tiedostot tallennetaan datahakemiston debug-alikansioon."
    },
    {
        "type": "paragraph",
        "text": "Network-asetukset tallennetaan erilliseen network-asetustiedostoon, jotta verkkoyhteyden kutsutunnus, huone, palvelin ja ääniasetukset säilyvät erillään tavallisista harjoitus- ja käyttöliittymäasetuksista."
    },
    {
        "type": "subheading",
        "text": "Tietokantaan tallennetaan"
    },
    {
        "type": "bullet",
        "text": "Kierroksen aloitus- ja lopetusaika."
    },
    {
        "type": "bullet",
        "text": "Tavoite, syöte ja syötteen lähde."
    },
    {
        "type": "bullet",
        "text": "Tarkkuus, puhtaus, kokonaispisteet, nopeuspisteet ja ajoituspisteet."
    },
    {
        "type": "bullet",
        "text": "Virheiden määrä sekä väärät, ylimääräiset ja puuttuvat merkit."
    },
    {
        "type": "bullet",
        "text": "Kierroksen kesto, vertailuaika, aika ok -tieto ja WPM-arvot."
    },
    {
        "type": "bullet",
        "text": "Straight key -mittarit, kuten pisteiden ja viivojen kestot, hajonnat ja viivasuhde."
    },
    {
        "type": "bullet",
        "text": "Kirjain- ja sanavälien ajoitustiedot."
    },
    {
        "type": "bullet",
        "text": "Raakatelemetrian tapahtumat."
    },
    {
        "type": "bullet",
        "text": "Merkkikohtaiset tulokset, mukaan lukien target_char, entered_char, result, entered_code ja ajoitustiedot."
    },
    {
        "type": "bullet",
        "text": "Vaikeimpien merkkien koontitilasto."
    },
    {
        "type": "bullet",
        "text": "Ajoitusprofiilin tila straight- ja iambic-lähteille."
    },
    {
        "type": "bullet",
        "text": "Taitotason snapshotit."
    },
    {
        "type": "subheading",
        "text": "Yhteensopimaton tietokanta"
    },
    {
        "type": "paragraph",
        "text": "Käynnistyksessä ohjelma tarkistaa, että tietokannassa on tarvittavat taulut ja sarakkeet. Jos vanha tietokanta ei näytä yhteensopivalta, ohjelma siirtää sen sivuun varmuuskopioksi ja luo uuden tyhjän tietokannan."
    },
    {
        "type": "heading",
        "text": "Harjoitteluvinkit"
    },
    {
        "type": "bullet",
        "text": "Aloita nopeudella, jolla pystyt lähettämään rauhallisesti ja puhtaasti."
    },
    {
        "type": "bullet",
        "text": "Jos virheitä tulee paljon, laske tavoite-WPM:ää tai lyhennä kierroksia."
    },
    {
        "type": "bullet",
        "text": "Nosta nopeutta vasta, kun tarkkuus, puhtaus ja ajoitus pysyvät hyvinä."
    },
    {
        "type": "bullet",
        "text": "Harjoittele vaikeimpia merkkejä välillä, mutta pidä mukana myös koko merkkivalikoimaa."
    },
    {
        "type": "bullet",
        "text": "Tee riittävän pitkiä, vähintään 12 varsinaisen merkin kierroksia, jotta data vaikuttaa taitotasoon."
    },
    {
        "type": "bullet",
        "text": "Harjoittele sekä straightia että iambicia, jos haluat nostaa yleistaitotasoa."
    },
    {
        "type": "bullet",
        "text": "Jos käytät näppäimistömorsea, valitse näppäin, jota voit painaa rennosti ja tasaisesti."
    },
    {
        "type": "bullet",
        "text": "Jos käytät Network-tilaa, aloita suuremmalla viivepuskurilla ja pienennä sitä vasta, kun yhteys toimii tasaisesti."
    },
    {
        "type": "bullet",
        "text": "WX-MOR on hyvä erikoisharjoitus, mutta sen merkkijakauma ei ole tasainen."
    },
    {
        "type": "paragraph",
        "text": "Hyvä kehitys syntyy nopeuden, tarkkuuden, puhtauden, rytmin ja monipuolisen merkkikattavuuden yhdistelmästä."
    }
]
