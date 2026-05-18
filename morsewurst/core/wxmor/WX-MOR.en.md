# WX-MOR

**Specification version:** 0.9  
**Author:** Kasperi Koski  
**Language:** English  
**Purpose:** a compact weather message format for Morse code, radio, text messages, or fast person-to-person weather communication

> [!WARNING]
> This English document is a machine-translated version of the original Finnish WX-MOR specification.
>
> The Finnish specification is the authoritative and most up-to-date version. If there are differences, ambiguities or translation errors, the Finnish document takes precedence.
>
> See the original Finnish specification:
>
> `WX-MOR.fi.md`

- [WX-MOR](#wx-mor)
  - [1. Introduction](#1-introduction)
    - [1.1. Purpose](#11-purpose)
    - [1.2. Basic principles](#12-basic-principles)
    - [1.3. Default units](#13-default-units)
  - [2. General message structure](#2-general-message-structure)
    - [2.1. Basic order](#21-basic-order)
    - [2.2. Meaning of fields](#22-meaning-of-fields)
    - [2.3. Minimum form](#23-minimum-form)
    - [2.4. Recommended core message](#24-recommended-core-message)
    - [2.5. Extended message](#25-extended-message)
    - [2.6. Field order and flexibility](#26-field-order-and-flexibility)
  - [3. Fields](#3-fields)
    - [3.1. Location `LOC`](#31-location-loc)
      - [3.1.1. General location code](#311-general-location-code)
      - [3.1.2. Exact airport or weather station](#312-exact-airport-or-weather-station)
      - [3.1.3. Locally agreed code](#313-locally-agreed-code)
    - [3.2. Time `TIME`](#32-time-time)
      - [3.2.1. Primary time format](#321-primary-time-format)
      - [3.2.2. Time format extended with date](#322-time-format-extended-with-date)
      - [3.2.3. Local time](#323-local-time)
    - [3.3. Temperature `TEMP`](#33-temperature-temp)
      - [3.3.1. Basic form](#331-basic-form)
      - [3.3.2. Rules](#332-rules)
      - [3.3.3. Examples](#333-examples)
    - [3.4. Dew point `D`](#34-dew-point-d)
      - [3.4.1. Basic form](#341-basic-form)
      - [3.4.2. Rules](#342-rules)
      - [3.4.3. Examples](#343-examples)
    - [3.5. Weather phenomenon and weather state `WXSTATE`](#35-weather-phenomenon-and-weather-state-wxstate)
      - [3.5.1. General principle](#351-general-principle)
      - [3.5.2. Basic keywords](#352-basic-keywords)
      - [3.5.3. Intensity prefixes](#353-intensity-prefixes)
      - [3.5.4. Multiple weather phenomena](#354-multiple-weather-phenomena)
      - [3.5.5. Recommended order of WXSTATE codes](#355-recommended-order-of-wxstate-codes)
      - [3.5.6. NIL](#356-nil)
      - [3.5.7. Compact weather aliases](#357-compact-weather-aliases)
        - [3.5.7.1. Intended use](#3571-intended-use)
        - [3.5.7.2. Alias list](#3572-alias-list)
        - [3.5.7.3. Compact intensity examples](#3573-compact-intensity-examples)
        - [3.5.7.4. Recommendation](#3574-recommendation)
    - [3.6. Wind `WIND`](#36-wind-wind)
      - [3.6.1. Basic principle](#361-basic-principle)
      - [3.6.2. Direction and speed](#362-direction-and-speed)
      - [3.6.3. Gusts](#363-gusts)
      - [3.6.4. Speed only](#364-speed-only)
      - [3.6.5. Variable wind](#365-variable-wind)
      - [3.6.6. Calm](#366-calm)
      - [3.6.7. Units](#367-units)
      - [3.6.8. Exact degree direction](#368-exact-degree-direction)
      - [3.6.9. Invalid forms](#369-invalid-forms)
      - [3.6.10. Formation rule](#3610-formation-rule)
    - [3.7. Cloud cover `CLOUD`](#37-cloud-cover-cloud)
      - [3.7.1. Basic codes](#371-basic-codes)
      - [3.7.2. Cloud height](#372-cloud-height)
    - [3.8. Visibility `VIS`](#38-visibility-vis)
    - [3.9. Air pressure `Q`](#39-air-pressure-q)
      - [3.9.1. Basic form](#391-basic-form)
      - [3.9.2. Examples](#392-examples)
      - [3.9.3. Pressure tendency](#393-pressure-tendency)
    - [3.10. UV index `UV`](#310-uv-index-uv)
      - [3.10.1. Basic form](#3101-basic-form)
      - [3.10.2. Examples](#3102-examples)
    - [3.11. Relative humidity `RH`](#311-relative-humidity-rh)
      - [3.11.1. Basic form](#3111-basic-form)
      - [3.11.2. Examples](#3112-examples)
    - [3.12. Precipitation amount `RR`](#312-precipitation-amount-rr)
      - [3.12.1. Basic form](#3121-basic-form)
      - [3.12.2. Examples](#3122-examples)
    - [3.13. Snow depth `SD`](#313-snow-depth-sd)
    - [3.14. New snow `NS`](#314-new-snow-ns)
    - [3.15. Free-form additional information](#315-free-form-additional-information)
  - [4. Field recognition](#4-field-recognition)
  - [5. Message formation rules](#5-message-formation-rules)
  - [6. Usage profiles](#6-usage-profiles)
    - [6.1. Minimum profile](#61-minimum-profile)
    - [6.2. Basic profile](#62-basic-profile)
    - [6.3. Extended profile](#63-extended-profile)
    - [6.4. Compact profile](#64-compact-profile)
  - [7. Example messages](#7-example-messages)
    - [7.1. Simple rain](#71-simple-rain)
    - [7.2. Dry and cloudy weather](#72-dry-and-cloudy-weather)
    - [7.3. Clear freezing weather](#73-clear-freezing-weather)
    - [7.4. Snowfall](#74-snowfall)
    - [7.5. Heavy snowfall and gusts](#75-heavy-snowfall-and-gusts)
    - [7.6. Blizzard](#76-blizzard)
    - [7.7. Foggy zero-degree weather](#77-foggy-zero-degree-weather)
    - [7.8. Slipperiness warning](#78-slipperiness-warning)
    - [7.9. Good visibility](#79-good-visibility)
    - [7.10. Snow information included](#710-snow-information-included)
    - [7.11. Compact rain message](#711-compact-rain-message)
    - [7.12. Compact winter message](#712-compact-winter-message)
    - [7.13. High UV index](#713-high-uv-index)
  - [8. Avoiding errors](#8-avoiding-errors)
    - [8.1. Do not use plus or minus signs](#81-do-not-use-plus-or-minus-signs)
    - [8.2. Do not use a slash for temperature and dew point](#82-do-not-use-a-slash-for-temperature-and-dew-point)
    - [8.3. Do not use a percent sign for humidity](#83-do-not-use-a-percent-sign-for-humidity)
    - [8.4. Do not combine temperature and dew point in the same field](#84-do-not-combine-temperature-and-dew-point-in-the-same-field)
    - [8.5. Do not omit the WX identifier](#85-do-not-omit-the-wx-identifier)
  - [9. Quick glossary](#9-quick-glossary)



---
## 1. Introduction

### 1.1. Purpose

WX-MOR is a compact weather message format designed especially for Morse code use, but it can also be used in other short text-based weather communication.

The goals of WX-MOR are:

- to be as universal as possible
- to be Morse-friendly
- to be human-readable
- to be easy to learn
- to use METAR-type thinking
- to also work as a very short message
- to be extendable without breaking the basic form

WX-MOR is not an official aviation weather message and does not replace METAR, TAF, SYNOP or official weather warnings.

---



### 1.2. Basic principles

1. The message always begins with the identifier `WX`.
2. The most important information is placed at the beginning.
3. Fields may be omitted without placeholders.
4. Fields are separated by one space.
5. Everything is written in uppercase letters.
6. Only the letters `A-Z`, numbers `0-9` and space are allowed.
7. Special characters are not used.
8. The plus sign is not used.
9. Minus is expressed with the letter `M`.
10. Unknown information is not guessed.

Allowed character set:

```text
ABCDEFGHIJKLMNOPQRSTUVWXYZ 0123456789 SPACE
```

---

### 1.3. Default units

WX-MOR uses the following default units:

| Quantity            | Default unit                      |
| :------------------ | :-------------------------------- |
| temperature         | Celsius                           |
| dew point           | Celsius                           |
| wind                | metres per second                 |
| visibility          | metre                             |
| air pressure        | hectopascal                       |
| UV index            | UV index value                    |
| precipitation       | millimetre                        |
| relative humidity   | percent without the percent sign  |
| snow depth          | centimetre                        |
| new snow            | centimetre                        |
| time                | UTC                               |

---

## 2. General message structure

### 2.1. Basic order

The following basic order is used in the message:

```text
WX LOC TIME TEMP D WXSTATE WIND CLOUD VIS Q UV RH RR SD NS EXTRA
```

### 2.2. Meaning of fields

| Field     | Meaning                                  |
| --------- | ---------------------------------------- |
| `WX`      | weather message identifier               |
| `LOC`     | location                                 |
| `TIME`    | observation time                         |
| `TEMP`    | temperature (T)                          |
| `D`       | dew point                                |
| `WXSTATE` | weather phenomenon or weather state      |
| `WIND`    | wind                                     |
| `CLOUD`   | cloud cover                              |
| `VIS`     | visibility                               |
| `Q`       | air pressure                             |
| `UV`      | UV index                                 |
| `RH`      | relative humidity                        |
| `RR`      | precipitation amount                     |
| `SD`      | snow depth                               |
| `NS`      | new snow                                 |
| `EXTRA`   | free-form additional information         |

### 2.3. Minimum form

```text
WX LOC TIME TEMP WXSTATE
```

Example:

```text
WX HEL 1420Z T6 RAIN
```

### 2.4. Recommended core message

```text
WX LOC TIME TEMP D WXSTATE WIND CLOUD Q
```

Example:

```text
WX HEL 1420Z T6 D4 RAIN SW4 OVC Q1008
```

The UV index may be added to the end of the core message after air pressure if the information is available and relevant.

Example:

```text
WX HEL 1420Z T18 D9 NIL SW4 SCT Q1018 UV5
```

### 2.5. Extended message

```text
WX LOC TIME TEMP D WXSTATE WIND CLOUD VIS Q UV RH RR SD NS EXTRA
```

Example:

```text
WX HEL 1420Z T6 D4 RAIN SW4 SCT025 BKN050 V8000 Q1008 UV1 RH86 RR2
```

### 2.6. Field order and flexibility

The recommended WX-MOR field order is:

```text
WX LOC TIME TEMP D WXSTATE WIND CLOUD VIS Q UV RH RR SD NS EXTRA
```

The recommended order is chosen according to what a person usually wants to know first:

1. what kind of message this is
2. where the weather is observed
3. when the observation was made
4. how warm or cold it is
5. what the dew point is
6. whether there is precipitation or other significant weather
7. how windy it is
8. what the cloud cover is like
9. how good the visibility is
10. what the air pressure is
11. what the UV index is, if the information is available and relevant
12. what supplementary information is available

Fields may be omitted. Empty placeholders are not used.

Because most fields are identified by their own prefixes, the message can, if necessary, also be understood when some fields are in a different order. For interoperability, fields are written in the recommended order.

---

## 3. Fields

### 3.1. Location `LOC`

#### 3.1.1. General location code

A three-letter code is primarily used as the location code.

If the location has a known IATA code, it is recommended as the general location code.

Examples:

| Code  | Location  |
| ----- | --------- |
| `HEL` | Helsinki  |
| `TKU` | Turku     |
| `TMP` | Tampere   |
| `OUL` | Oulu      |
| `RVN` | Rovaniemi |

#### 3.1.2. Exact airport or weather station

If an exact airport or official weather observation station is meant, a four-letter ICAO code may be used.

Examples:

| Code   | Location         |
| ------ | ---------------- |
| `EFHK` | Helsinki-Vantaa  |
| `EFTU` | Turku            |
| `EFTP` | Tampere-Pirkkala |
| `EFOU` | Oulu             |

#### 3.1.3. Locally agreed code

If no suitable official or established code exists, a locally agreed 3-6 character code may be used.

Examples:

```text
KRUU
MAUNU
PATA
SALO
```

The same location should always use the same code.

---

### 3.2. Time `TIME`

#### 3.2.1. Primary time format

Time is primarily given in UTC in the format:

```text
HHMMZ
```

Examples:

| Code    | Meaning    |
| ------- | ---------- |
| `0915Z` | 09:15 UTC  |
| `1420Z` | 14:20 UTC  |
| `2305Z` | 23:05 UTC  |

#### 3.2.2. Time format extended with date

If the date is relevant, the following format is used:

```text
DDHHMMZ
```

Example:

| Code      | Meaning                              |
| --------- | ------------------------------------ |
| `010005Z` | day 1 of the month at 00:05 UTC      |
| `071230Z` | day 7 of the month at 12:30 UTC      |
| `152359Z` | day 15 of the month at 23:59 UTC     |
| `201045Z` | day 20 of the month at 10:45 UTC     |
| `301815Z` | day 30 of the month at 18:15 UTC     |

#### 3.2.3. Local time

Local time is not used.

---

### 3.3. Temperature `TEMP`

#### 3.3.1. Basic form

Temperature is marked with the identifier `T`.

```text
Tn
TMn
```

#### 3.3.2. Rules

* `T` means air temperature.
* The plus sign is not used.
* Minus is expressed with the letter `M`.
* Temperature is given in whole degrees Celsius.
* Decimals are not used.

#### 3.3.3. Examples

| Code   | Meaning |
| ------ | ------- |
| `T6`   | +6 °C   |
| `T0`   | 0 °C    |
| `TM3`  | -3 °C   |
| `TM18` | -18 °C  |

### 3.4. Dew point `D`

#### 3.4.1. Basic form

Dew point is marked with the identifier `D`.

```text
Dn
DMn
```

#### 3.4.2. Rules

* `D` means dew point.
* Dew point is written, where applicable, in the same way as temperature.
* Dew point is placed immediately after temperature as its own field.
* Dew point is separated from temperature by a space.
* The plus sign is not used.
* Minus is expressed with the letter `M`.
* Dew point is given in whole degrees Celsius.
* Decimals are not used.

#### 3.4.3. Examples

| Code   | Meaning           |
| ------ | ----------------- |
| `D2`   | dew point +2 °C   |
| `D0`   | dew point 0 °C    |
| `DM4`  | dew point -4 °C   |
| `DM12` | dew point -12 °C  |

---

### 3.5. Weather phenomenon and weather state `WXSTATE`

#### 3.5.1. General principle

Weather phenomena are primarily expressed with human-readable English keywords.

This makes the message easier to understand internationally than a fully coded METAR-style form.

The WXSTATE field contains both actual weather phenomena, weather conditions and warning-type states. A separate warning field is not used.

The WXSTATE field may be omitted if the code `VOK` is used in the message.

#### 3.5.2. Basic keywords

| Code      | Meaning                                      |
| --------- | -------------------------------------------- |
| `NIL`     | no significant weather phenomenon            |
| `RAIN`    | rain                                         |
| `DRIZZLE` | drizzle                                      |
| `SNOW`    | snow                                         |
| `SLEET`   | sleet                                        |
| `HAIL`    | hail                                         |
| `SHOWER`  | shower                                       |
| `THUNDER` | thunder                                      |
| `FOG`     | fog                                          |
| `MIST`    | mist                                         |
| `HAZE`    | haze                                         |
| `ICE`     | freezing condition or icing                  |
| `SLIP`    | slippery conditions                          |
| `BLIZZ`   | blizzard                                     |
| `FROST`   | frost or ground frost                        |
| `DRIFT`   | drifting snow                                |
| `FLOOD`   | flood or flood risk                          |
| `HEAT`    | heat or hot weather                          |
| `COLD`    | very cold weather                            |
| `STORM`   | storm                                        |
| `GALE`    | strong wind                                  |

#### 3.5.3. Intensity prefixes

The intensity of a weather phenomenon may be specified with a prefix if unusually weak or strong intensity is to be emphasized.

| Prefix | Meaning |
| ------ | ------- |
| `L`    | light   |
| `H`    | heavy   |

If no prefix is used, the weather phenomenon is expressed neutrally without an exact intensity classification.

In WX-MOR, the intensity prefixes `L` and `H` may be used only with the WXSTATE codes listed below.

| Code       | Meaning             |
| ---------- | ------------------- |
| `LTHUNDER` | light thunder       |
| `HTHUNDER` | heavy thunder       |
| `LSHOWER`  | light shower        |
| `HSHOWER`  | heavy shower        |
| `LDRIZZLE` | light drizzle       |
| `HDRIZZLE` | heavy drizzle       |
| `LRAIN`    | light rain          |
| `HRAIN`    | heavy rain          |
| `LSLEET`   | light sleet         |
| `HSLEET`   | heavy sleet         |
| `LSNOW`    | light snow          |
| `HSNOW`    | heavy snow          |
| `LHAIL`    | light hail          |
| `HHAIL`    | heavy hail          |
| `LBLIZZ`   | light blizzard      |
| `HBLIZZ`   | heavy blizzard      |
| `LFOG`     | light fog           |
| `HFOG`     | very dense fog      |
| `LMIST`    | light mist          |
| `HMIST`    | heavy mist          |
| `LHAZE`    | light haze          |
| `HHAZE`    | heavy haze          |
| `LGALE`    | light gale          |
| `HGALE`    | very strong gale    |
| `LSTORM`   | weak storm          |
| `HSTORM`   | strong storm        |

Not all WXSTATE codes support intensity prefixes.

Intensity prefixes are primarily used for precipitation, showers, thunder, wind and visibility phenomena.

The following codes are binary or state-descriptive by nature, and intensity prefixes are not used with them:

`SLIP`, `FROST`, `COLD`, `HEAT`, `FLOOD`, `DRIFT`, `ICE`


#### 3.5.4. Multiple weather phenomena

Multiple weather phenomena may be reported one after another.

Examples:

```text
RAIN FOG
SNOW BLIZZ
THUNDER HRAIN
SLEET ICE
SNOW SLIP
```

#### 3.5.5. Recommended order of WXSTATE codes

If multiple weather phenomena are used in the WXSTATE field, they are written in the following order:

| Order | Group                              | Codes                                               |
| :---: | ---------------------------------- | --------------------------------------------------- |
|   1   | No significant weather phenomenon  | `NIL`                                               |
|   2   | Thunder and shower type            | `THUNDER`, `SHOWER`                                 |
|   3   | Precipitation and phase            | `DRIZZLE`, `RAIN`, `SLEET`, `SNOW`, `HAIL`, `BLIZZ` |
|   4   | Visibility phenomena               | `FOG`, `MIST`, `HAZE`                               |
|   5   | Ice, slipperiness and winter states| `ICE`, `SLIP`, `FROST`, `DRIFT`                     |
|   6   | Wind and hazard conditions         | `GALE`, `STORM`, `FLOOD`, `HEAT`, `COLD`            |
|   7   | Unknown phenomenon                 | `UNKNOWN`                                           |

The order is a recommendation for improving message consistency and readability. It does not change the meaning of the codes.

If intensity prefixes are used, the prefixed code is placed in the same group as its basic code. For example, `HRAIN` is placed in the same position as `RAIN`, and `HFOG` in the same position as `FOG`.

#### 3.5.6. NIL

`NIL` means that there is no significant weather phenomenon.

`NIL` does not automatically mean:

* clear sky
* calm weather
* good visibility
* high air pressure

Example:

```text
WX HEL 1200Z T8 NIL BKN W3 Q1017
```

---

#### 3.5.7. Compact weather aliases

##### 3.5.7.1. Intended use

The default WX-MOR profile uses human-readable weather words such as `RAIN` and `SNOW`.

In compact notation, METAR-style aliases may be used.

##### 3.5.7.2. Alias list

| Default code | Compact form |
| ------------ | ------------ |
| `RAIN`       | `RA`         |
| `DRIZZLE`    | `DZ`         |
| `SNOW`       | `SN`         |
| `SLEET`      | `SL`         |
| `HAIL`       | `GR`         |
| `SHOWER`     | `SH`         |
| `THUNDER`    | `TS`         |
| `FOG`        | `FG`         |
| `MIST`       | `BR`         |
| `HAZE`       | `HZ`         |
| `ICE`        | `ICE`        |
| `SLIP`       | `SLP`        |
| `BLIZZ`      | `BLZ`        |
| `FROST`      | `FRS`        |
| `DRIFT`      | `DRS`        |
| `GALE`       | `GAL`        |
| `STORM`      | `STM`        |
| `FLOOD`      | `FLD`        |
| `HEAT`       | `HOT`        |
| `COLD`       | `CLD`        |

##### 3.5.7.3. Compact intensity examples

| Human-readable | Compact form |
| -------------- | ------------ |
| `LRAIN`        | `LRA`        |
| `HRAIN`        | `HRA`        |
| `LDRIZZLE`     | `LDZ`        |
| `HDRIZZLE`     | `HDZ`        |
| `LSNOW`        | `LSN`        |
| `HSNOW`        | `HSN`        |
| `LSLEET`       | `LSL`        |
| `HSLEET`       | `HSL`        |
| `LHAIL`        | `LGR`        |
| `HHAIL`        | `HGR`        |
| `LBLIZZ`       | `LBLZ`       |
| `HBLIZZ`       | `HBLZ`       |
| `LFOG`         | `LFG`        |
| `HFOG`         | `HFG`        |
| `LMIST`        | `LBR`        |
| `HMIST`        | `HBR`        |
| `LHAZE`        | `LHZ`        |
| `HHAZE`        | `HHZ`        |
| `LGALE`        | `LGAL`       |
| `HGALE`        | `HGAL`       |
| `LSTORM`       | `LSTM`       |
| `HSTORM`       | `HSTM`       |
| `THUNDER RAIN` | `TSRA`       |
| `SHOWER RAIN`  | `SHRA`       |
| `SHOWER SNOW`  | `SHSN`       |

##### 3.5.7.4. Recommendation

In compact form, the intensity prefix `L` or `H` is attached in front of the compact weather code. Human-readable codes are recommended for general use.

```text
RAIN
SNOW
FOG
ICE
SLIP
```

Compact codes may be used in compact notation.

```text
RA
SN
FG
ICE
SLP
```

---

### 3.6. Wind `WIND`

#### 3.6.1. Basic principle

Wind is reported without a separate identifier.

The default wind unit is metres per second. The unit does not need to be written.

Wind is presented in the form:

```text
DIRss
DIRssGmm
ss
ssGmm
```

Where:

* `DIR` = wind direction as a compass direction: `N`, `NE`, `E`, `SE`, `S`, `SW`, `W`, `NW` or `VRB`
* `ss` = mean wind speed (0-99)
* `Gmm` = maximum gust speed (0-99)

#### 3.6.2. Direction and speed

If the wind direction is known, a compass direction is used.

```text
DIRss
DIRssGmm
```

Where:

* `DIR` = wind direction
* `ss` = mean wind speed
* `Gmm` = maximum gust speed, if reported

Examples:

| Code  | Meaning               |
| ----- | --------------------- |
| `N4`  | north wind 4 m/s      |
| `NE5` | northeast wind 5 m/s  |
| `S6`  | south wind 6 m/s      |
| `W10` | west wind 10 m/s      |

#### 3.6.3. Gusts

Gusts are indicated with the letter `G`, which is appended after the mean wind speed.

```text
DIRssGmm
ssGmm
```

Where:

* `G` = gust identifier
* `mm` = maximum gust speed

The gust value is always greater than or equal to the mean wind speed.

Gusts are reported only if they are meaningful.

Examples:

| Code     | Meaning                                  |
| -------- | ---------------------------------------- |
| `SW5G10` | southwest wind 5 m/s, gusts 10 m/s       |
| `NW8G14` | northwest wind 8 m/s, gusts 14 m/s       |
| `6G12`   | wind 6 m/s, gusts 12 m/s                 |

#### 3.6.4. Speed only

If the direction is unknown or is not to be reported:

```text
ss
ssGmm
```

Examples:

| Code   | Meaning                  |
| ------ | ------------------------ |
| `4`    | wind 4 m/s               |
| `10`   | wind 10 m/s              |
| `6G12` | wind 6 m/s, gusts 12 m/s |

#### 3.6.5. Variable wind

If the wind direction is variable, the code `VRB` is used.

```text
VRB3
VRB5G9
```

#### 3.6.6. Calm

Calm is expressed with the code:

```text
CALM
```

Example:

```text
WX HEL 0900Z T2 NIL CALM SKC Q1020
```

#### 3.6.7. Units

Wind speed is always reported in metres per second (m/s).

The unit is not written in the wind field.

Wrong:

```text
SW5MPS
NW15KT
```

Correct:

```text
SW5
NW8
```

If the source information is in other units, it is converted to metres per second before forming the WX-MOR message.

If necessary, the wind speed may be reported in the original unit in the `EXTRA` field in free form, for example:

```text
WND15KT
WNDKTG21KT
```


#### 3.6.8. Exact degree direction

The WX-MOR wind field does not use degree-form wind direction.

If the exact degree direction needs to be preserved, it may be reported in the `EXTRA` field at the end of the message.

Example:

```text
WX HEL 1420Z T6 D4 RAIN SW5 OVC Q1008 WD230
```


#### 3.6.9. Invalid forms

The wind field must not be written in degrees or without a clear structure.

Wrong:

```text
2305
SW
VRB
5MPS
15KT
```

Correct:

```text
SW5
SW5G10
4
6G11
VRB3
VRB5G9
```

#### 3.6.10. Formation rule

If wind information is reported, the wind field must always include at least the wind speed.

```text
ss
```

If the wind direction is known, it is added before the speed:

```text
DIRss
```

If gusts are known and meaningful, they are added after the speed:

```text
DIRssGmm
ssGmm
```

Where:

* `DIR` = wind direction, optional
* `ss` = wind speed, required if the wind field is used
* `Gmm` = maximum gust speed, optional


---

### 3.7. Cloud cover `CLOUD`

One or more cloud cover fields may be reported. If multiple cloud layers are reported, they are written consecutively, separated by spaces, from lowest to highest.

Cloud cover does not need to be reported if the code `VOK` is used in the message. Otherwise cloud cover is optional.

#### 3.7.1. Basic codes

Cloud cover uses abbreviations familiar from METAR.

| Code  | Meaning                                                  |
| ----- | -------------------------------------------------------- |
| `SKC` | clear sky                                                |
| `FEW` | few clouds                                               |
| `SCT` | scattered clouds or partly cloudy                        |
| `BKN` | broken cloud cover                                       |
| `OVC` | overcast                                                 |
| `VV`  | vertical visibility, sky structure is not distinguishable |

#### 3.7.2. Cloud height

Cloud height may be added to the cloud code in METAR style as a three-digit number.

The number means hundreds of feet.

| Code     | Meaning                              |
| -------- | ------------------------------------ |
| `FEW025` | few clouds, base 2500 ft             |
| `BKN012` | broken cloud cover, base 1200 ft     |
| `OVC006` | overcast, base 600 ft                |

Cloud height does not need to be reported.

Examples

```text
SKC
FEW025
SCT014 BKN021
FEW020 SCT050 BKN090
SCT014 BKN021 BKN030
```

---

### 3.8. Visibility `VIS`

Visibility is expressed in metres with the identifier `V`.

```text
Vn
```

The value `n` means visibility in metres. Leading zeroes are not used.

If visibility is 9999 metres or better, the following code is used:

```text
VOK
```

`VOK` means good visibility. In the basic form it means that visibility is 9999 metres or better.

`VOK` may be given when all of the following conditions are met:

- visibility is at least 10 km
- no significant weather phenomena such as rain, snow or fog occur
- no significant low clouds occur

When all of the above conditions are met, the situation may be expressed with the code `VOK` alone, and weather phenomenon or cloud cover do not need to be reported as separate fields.

| Code    | Meaning              |
| ------- | -------------------- |
| `V500`  | visibility 500 m     |
| `V1000` | visibility 1000 m    |
| `V3000` | visibility 3000 m    |
| `V8000` | visibility 8000 m    |
| `VOK`   | good visibility      |


---

### 3.9. Air pressure `Q`

#### 3.9.1. Basic form

Air pressure is expressed with the identifier `Q`.

```text
Qnnnn
```

The value is given in hectopascals (hPa) as a fixed four-digit number. Values below 1000 hPa use a leading zero.

#### 3.9.2. Examples

| Code    | Meaning  |
| ------- | -------- |
| `Q1013` | 1013 hPa |
| `Q0998` | 998 hPa  |
| `Q1026` | 1026 hPa |

#### 3.9.3. Pressure tendency

Pressure tendency may be expressed with an additional code, written after the pressure and separated by a space.

| Code | Meaning          |
| ---- | ---------------- |
| `QR` | pressure rising  |
| `QF` | pressure falling |
| `QS` | pressure steady  |

Example:

```text
Q1004 QF
Q0989 QR
Q1012 QS
```

---

### 3.10. UV index `UV`

#### 3.10.1. Basic form

The UV index is expressed with the identifier `UV`.

```text
UVn
```

The value `n` is the integer value of the UV index. Decimals are not used.

#### 3.10.2. Examples

| Code  | Meaning    |
| ----- | ---------- |
| `UV0` | UV index 0 |
| `UV2` | UV index 2 |
| `UV5` | UV index 5 |
| `UV8` | UV index 8 |

---

### 3.11. Relative humidity `RH`

#### 3.11.1. Basic form

Relative humidity is expressed with the identifier `RH`.

```text
RHn
```

#### 3.11.2. Examples

| Code   | Meaning                |
| ------ | ---------------------- |
| `RH76` | relative humidity 76 % |
| `RH92` | relative humidity 92 % |

---

### 3.12. Precipitation amount `RR`

#### 3.12.1. Basic form

Precipitation amount is expressed with the identifier `RR`.

```text
RRn
```

The value is given in millimetres and corresponds to the accumulation during the last 1 hour.

Precipitation amount includes all melted precipitation (water, snow, sleet).

#### 3.12.2. Examples

| Code   | Meaning                  |
| ------ | ------------------------ |
| `RR1`  | 1 mm of precipitation    |
| `RR5`  | 5 mm of precipitation    |
| `RR12` | 12 mm of precipitation   |

---

### 3.13. Snow depth `SD`

Snow depth is expressed with the identifier `SD`.

```text
SDn
```

The value is given in centimetres and describes the total amount of snow on the ground at the observation time.

| Code   | Meaning          |
| ------ | ---------------- |
| `SD5`  | snow depth 5 cm  |
| `SD18` | snow depth 18 cm |
| `SD42` | snow depth 42 cm |


### 3.14. New snow `NS`

New snow is expressed with the identifier `NS`.

```text
NSn
```

The value is given in centimetres and describes the accumulation of new snow during the last 6 hours.

| Code   | Meaning                                  |
| ------ | ---------------------------------------- |
| `NS1`  | 1 cm of new snow during the last 6 hours |
| `NS4`  | 4 cm of new snow during the last 6 hours |
| `NS12` | 12 cm of new snow during the last 6 hours|


---


### 3.15. Free-form additional information

The EXTRA field contains weather-message-related information that is not defined in other fields or codes.

The field is used for supplementary and clarifying information that is relevant to the situation but does not belong to the actual basic format.

The EXTRA field may contain, for example:

- wind direction in degrees (`WD230`)
- original wind speed and unit (`WND15KT`, `WNDKTG21KT`)
- local observations (`ROADICE`, `SEAFOG`)
- other unambiguous additional information

The content of the EXTRA field is written as unambiguous identifiers without special characters. The content of the field must not break interpretation of the message or conflict with other fields.

---


## 4. Field recognition

| Field type      | Recognition                                                                                                      |
| --------------- | ---------------------------------------------------------------------------------------------------------------- |
| message start   | `WX`                                                                                                             |
| location        | usually the second field                                                                                         |
| time            | ends with `Z`                                                                                                    |
| temperature     | begins with `T`                                                                                                  |
| dew point       | begins with `D`                                                                                                  |
| weather phenomenon | weather vocabulary keyword or alias                                                                           |
| wind            | `CALM`, speed only, `VRB` + speed, or compass direction + speed (`N4`, `NE5`, `SW8G14`)                         |
| cloud cover     | `SKC`, `FEW`, `SCT`, `BKN`, `OVC`, `VV`; several in sequence: `FEW025`, `SCT014 BKN021`, `SCT014 BKN021 BKN030` |
| visibility      | `Vn` or `VOK`                                                                                                    |
| air pressure    | begins with `Q`                                                                                                  |
| UV index        | begins with `UV`                                                                                                 |
| humidity        | begins with `RH`                                                                                                 |
| precipitation   | begins with `RR`                                                                                                 |
| snow depth      | begins with `SD`                                                                                                 |
| new snow        | begins with `NS`                                                                                                 |
| additional information | other identified or agreed fields at the end of the message                                               |

---


## 5. Message formation rules

1. The first field of the message is always `WX`.
2. The second field is location.
3. The third field is time.
4. Time is given in UTC form and is placed before temperature.
5. Temperature is placed before dew point.
6. Dew point is placed before the weather phenomenon.
7. The weather phenomenon is placed before wind.
8. Wind is placed before cloud cover.
9. Cloud cover is placed before visibility. If there are several cloud layers, they are written consecutively from lowest to highest.
10. Visibility is placed before air pressure.
11. Air pressure is placed before the UV index and other supplementary observations.
12. The UV index is placed before relative humidity, if reported.
13. Relative humidity is placed before precipitation amount.
14. Precipitation amount is placed before snow depth.
15. Snow depth is placed before new snow.
16. New snow is placed before additional information.
17. Additional information (`EXTRA`) is always placed last.
18. Fields may be omitted.
19. Empty fields are not marked.
20. Unknown information is not guessed.
21. The meaning of all used codes must be known to the parties.
22. The same community or system always uses the same location codes.

---


## 6. Usage profiles

Usage profiles describe common WX-MOR message lengths for different use cases.

Profiles are not the only allowed message forms. Fields may be omitted if the information is unavailable or is not to be reported.

If a field is reported, it is written in the form specified by this specification and in the order defined by the message formation rules.


### 6.1. Minimum profile

```text
WX LOC TIME TEMP WXSTATE
```

Examples:

```text
WX HEL 1420Z T6 RAIN
WX TKU 0915Z TM3 NIL
WX OUL 1830Z T2 FOG
```


### 6.2. Basic profile

```text
WX LOC TIME TEMP D WXSTATE WIND CLOUD Q
```

Examples:

```text
WX HEL 1420Z T6 D4 RAIN SW4 OVC Q1008
WX TKU 0915Z TM3 DM5 NIL W3 SCT Q1015
WX OUL 1830Z T2 DM1 FOG N5 BKN Q1002
```

The UV index may be added to the basic profile after air pressure if it is relevant.

Examples:

```text
WX HEL 1420Z T18 D9 NIL SW4 SCT Q1018 UV5
WX TKU 1200Z T22 D11 NIL SE3 FEW Q1016 UV6
WX OUL 1100Z T16 D8 NIL W4 SCT Q1019 UV4
```


### 6.3. Extended profile

```text
WX LOC TIME TEMP D WXSTATE WIND CLOUD VIS Q UV RH RR SD NS EXTRA
```

Examples:

```text
WX HEL 1420Z T6 D4 RAIN SW4 SCT025 BKN050 V8000 Q1008 UV1 RH86 RR2
WX TKU 0915Z TM3 DM5 NIL W3 SCT V8000 Q1015 UV0 RH78
WX OUL 1830Z T2 DM1 SNOW N5 BKN V3000 Q1002 UV0 RH92 SD12 NS3
```

### 6.4. Compact profile

```text
WX LOC TIME TEMP WXSTATE WIND CLOUD VIS Q UV EXTRA
```

Examples:

```text
WX HEL 1420Z T6 RA SW4 OVC V10 Q1008
WX TKU 0915Z TM3 NIL W3 SCT V8 Q1015
WX OUL 1830Z T2 SN N5 BKN V3 Q1002
```

---

## 7. Example messages

The following section presents example messages from different categories. Each category contains three examples, each on its own line.

### 7.1. Simple rain

```text
WX HEL 1420Z T6 D4 RAIN SW4 OVC V8000 Q1008
WX TKU 1010Z T7 D5 RAIN S5 SCT V6000 Q1006
WX TMP 1530Z T5 D3 RAIN SE4 BKN V5000 Q1009
```

### 7.2. Dry and cloudy weather

```text
WX HEL 1200Z T8 D2 NIL W3 BKN VOK Q1017 UV1
WX TKU 1400Z T10 D4 NIL SW4 SCT VOK Q1015 UV2
WX OUL 0900Z T6 D1 NIL N2 OVC V9000 Q1018 UV1
```

### 7.3. Clear freezing weather

```text
WX RVN 0900Z TM18 DM20 NIL CALM SKC VOK Q1028
WX OUL 0700Z TM12 DM15 NIL N1 SKC VOK Q1030
WX KTT 0600Z TM20 DM24 NIL CALM SKC V7000 Q1025
```

### 7.4. Snowfall

```text
WX OUL 0715Z TM8 DM10 SNOW NE7 OVC V3000 Q0994
WX RVN 0830Z TM6 DM8 SNOW N5 BKN V4000 Q0998
WX KEM 0600Z TM5 DM7 SNOW NW6 OVC V2000 Q1001
```

### 7.5. Heavy snowfall and gusts

```text
WX OUL 0715Z TM8 DM10 HSNOW NE7G12 OVC V1500 Q0994
WX RVN 0830Z TM6 DM9 HSNOW N6G11 BKN V2000 Q0998
WX KEM 0600Z TM5 DM8 HSNOW NW7G13 OVC V1200 Q1001
```

### 7.6. Blizzard

```text
WX OUL 0715Z TM8 DM11 HSNOW BLIZZ NE9G16 OVC V500 Q0989
WX RVN 0830Z TM7 DM10 HSNOW BLIZZ N8G15 BKN V800 Q0992
WX KEM 0600Z TM6 DM9 HSNOW BLIZZ NW9G17 OVC V600 Q0995
```

### 7.7. Foggy zero-degree weather

```text
WX TKU 0830Z T0 DM1 FOG CALM OVC V300 Q1011
WX HEL 0600Z T1 D0 FOG CALM SCT V800 Q1013
WX TMP 0700Z T0 DM1 FOG CALM BKN V500 Q1010
```

### 7.8. Slipperiness warning

```text
WX HEL 0545Z TM1 DM2 ICE SLIP E3 OVC V5000 Q1002
WX TKU 0600Z T0 DM1 ICE SLIP SE2 SCT V6000 Q1005
WX OUL 0700Z TM2 DM4 ICE SLIP N3 BKN V4000 Q1000
```

### 7.9. Good visibility

```text
WX EFHK 1810Z T2 D0 NIL SW5 SCT025 BKN080 VOK Q1019 UV0 RH79
WX EFTU 1700Z T3 D1 NIL W4 FEW VOK Q1020 UV1 RH70
WX EFTP 1600Z T4 D2 NIL S3 SCT VOK Q1018 UV1 RH65
```

### 7.10. Snow information included

```text
WX OUL 0600Z TM6 DM8 SNOW N4 OVC V3000 Q1000 SD22 NS4
WX RVN 0700Z TM8 DM11 SNOW N5 BKN V2000 Q0998 SD18 NS3
WX KEM 0800Z TM5 DM7 SNOW NW6 OVC V2500 Q1002 SD25 NS5
```

In the examples, `NS` describes the amount of new snow during the last 6 hours.

### 7.11. Compact rain message

```text
WX HEL 1420Z T6 D4 RA SW4 OVC V8000 Q1008
WX TKU 1010Z T7 D5 RA S5 SCT V6000 Q1006
WX TMP 1530Z T5 D3 RA SE4 BKN V5000 Q1009
```

### 7.12. Compact winter message

```text
WX OUL 0715Z TM8 DM10 HSN NE7G12 OVC V1500 Q0994 SD18 NS4
WX RVN 0830Z TM6 DM9 HSN N6G11 BKN V2000 Q0998 SD15 NS3
WX KEM 0600Z TM5 DM8 HSN NW7G13 OVC V1200 Q1001 SD20 NS5
```

### 7.13. High UV index

```text
WX HEL 1100Z T24 D12 NIL S3 SKC VOK Q1018 UV6
WX TKU 1200Z T26 D14 NIL SW4 FEW VOK Q1016 UV7
WX TMP 1300Z T25 D13 NIL CALM SCT VOK Q1017 UV5
```

---

## 8. Avoiding errors

### 8.1. Do not use plus or minus signs

Wrong:

```text
WX HEL 1420Z +6 RAIN
```

Correct:

```text
WX HEL 1420Z T6 RAIN
```

Wrong:

```text
WX HEL 1420Z T-6 SNOW
```

Correct:

```text
WX HEL 1420Z TM6 SNOW
```

### 8.2. Do not use a slash for temperature and dew point

Wrong:

```text
WX HEL 1420Z T6/D4 RAIN
```

Correct:

```text
WX HEL 1420Z T6 D4 RAIN
```

### 8.3. Do not use a percent sign for humidity

Wrong:

```text
RH86%
```

Correct:

```text
RH86
```

### 8.4. Do not combine temperature and dew point in the same field

Wrong:

```text
WX HEL 1420Z T6D4 RAIN
```

### 8.5. Do not omit the WX identifier

Wrong:

```text
HEL 1420Z T6 RAIN
```

Correct:

```text
WX HEL 1420Z T6 RAIN
```

---

## 9. Quick glossary

| Code      | Meaning                                             |
| --------- | --------------------------------------------------- |
| `BKN`     | broken cloud cover                                  |
| `BLIZZ`   | blizzard                                            |
| `BLZ`     | blizzard (compact)                                  |
| `BR`      | mist (compact)                                      |
| `CALM`    | calm                                                |
| `CLOUD`   | cloud cover field; one or more cloud layers         |
| `COLD`    | very cold                                           |
| `D`       | dew point                                           |
| `DRIZZLE` | drizzle                                             |
| `DRIFT`   | drifting snow                                       |
| `DRS`     | drifting snow (compact)                             |
| `DZ`      | drizzle (compact)                                   |
| `E`       | east                                                |
| `EXTRA`   | free-form additional information                    |
| `FEW`     | few clouds                                          |
| `FG`      | fog (compact)                                       |
| `FLOOD`   | flood                                               |
| `FOG`     | fog                                                 |
| `FROST`   | frost or ground frost                               |
| `FRS`     | frost (compact)                                     |
| `G`       | gust                                                |
| `GALE`    | strong wind                                         |
| `GR`      | hail (compact)                                      |
| `H`       | heavy                                               |
| `HAIL`    | hail                                                |
| `HAZE`    | haze                                                |
| `HEAT`    | heat                                                |
| `HZ`      | haze (compact)                                      |
| `ICE`     | freezing condition                                  |
| `L`       | light                                               |
| `LOC`     | location                                            |
| `M`       | minus marker                                        |
| `MIST`    | mist                                                |
| `N`       | north                                               |
| `NE`      | northeast                                           |
| `NIL`     | no significant weather phenomenon                   |
| `NS`      | new snow                                            |
| `NW`      | northwest                                           |
| `OVC`     | overcast                                            |
| `Q`       | air pressure                                        |
| `RA`      | rain (compact)                                      |
| `RAIN`    | rain                                                |
| `RH`      | relative humidity                                   |
| `RR`      | precipitation amount                                |
| `S`       | south                                               |
| `SC`      | scattered clouds (compact)                          |
| `SCT`     | scattered clouds                                    |
| `SD`      | snow depth                                          |
| `SE`      | southeast                                           |
| `SH`      | shower (compact)                                    |
| `SHOWER`  | shower                                              |
| `SKC`     | clear sky                                           |
| `SL`      | sleet (compact)                                     |
| `SLEET`   | sleet                                               |
| `SLIP`    | slippery conditions                                 |
| `SLP`     | slippery conditions (compact)                       |
| `SN`      | snow (compact)                                      |
| `SNOW`    | snow                                                |
| `STORM`   | storm                                               |
| `SW`      | southwest                                           |
| `T`       | temperature                                         |
| `TEMP`    | temperature field                                   |
| `THUNDER` | thunder                                             |
| `TIME`    | time                                                |
| `TS`      | thunder (compact)                                   |
| `UV`      | UV index                                            |
| `V`       | visibility                                          |
| `VIS`     | visibility field                                    |
| `VOK`     | good visibility                                     |
| `VRB`     | variable wind                                       |
| `VV`      | vertical visibility                                 |
| `W`       | west                                                |
| `WIND`    | wind field                                          |
| `WX`      | weather message identifier                          |
| `WXSTATE` | weather phenomenon or weather state field           |

---
