# QR-C2 — Android Security Research Lab

**QR-based payload delivery | Android agent | HTTP polling | Kali Linux**

Laboratorní projekt zaměřený na analýzu distribuce souborů prostřednictvím QR kódů, komunikaci Android klienta s řídicím serverem a bezpečnostní omezení mobilního operačního systému.

> **Disclaimer:** Projekt je určen výhradně pro bezpečnostní výzkum a testování na vlastních nebo výslovně autorizovaných zařízeních.

## Overview

Projekt simuluje scénář, ve kterém uživatel naskenuje QR kód, otevře webovou stránku a stáhne testovací soubor.

V laboratorním prostředí lze následně pomocí autorizovaného ADB spustit testovacího klienta, který komunikuje se serverem na Kali Linuxu prostřednictvím HTTP pollingu.

**Workflow:**

```text
QR Code
   |
   v
Landing Page
   |
   v
File Download
   |
   v
Manual Execution (ADB)
   |
   v
Android Test Agent
   |
   | HTTP Polling
   v
Kali Linux C2 Server
   |
   +-- Task Queue
   +-- Result Collection
   +-- Test File Transfers
   +-- Dashboard
```

**Important:** QR kód sám o sobě soubor nespouští. Stažení, instalace a spuštění jsou na Androidu oddělené operace.

## Features

| Feature | Status | Description |
|---|---|---|
| QR Code Generation | PASS | Generování QR kódu s URL |
| HTTP File Delivery | PASS | Stažení ARM64 binárního souboru |
| File Integrity | PASS | Bitová shoda přeneseného souboru |
| HTTP Polling | PASS | Komunikace klient → server |
| Task Queue | PASS | Předávání laboratorních úloh |
| Result Reporting | PASS | Vrácení výsledků |
| Test File Transfer | PASS | Přenos testovacích obrazových dat |
| Base64 Decoding | PASS | Dekódování na straně serveru |
| Web Dashboard | Implemented | Rozhraní pro správu testu |
| APK Delivery | NOT TESTED | Alternativní distribuční model |
| Automatic Execution | NOT SUPPORTED | QR nezajišťuje spuštění |

## Requirements

**Server:**
- Kali Linux
- Python 3
- `qrencode`
- HTTP server na portu `8080`

**Android:**
- Testovací Android zařízení
- ARM64 architektura pro daný binární soubor
- USB debugging a autorizované ADB pro scénář A

**Optional:**
- Android SDK pro vývoj testovací APK
- Izolovaná Wi-Fi síť nebo VPN

## Project Structure

Orientační rozložení projektu:

```text
qr-c2/
├── README.md
├── c2-qr.py
├── agent
├── qr.png
└── exfil/
    └── test-data/
```

Popis souborů:

| File | Purpose |
|---|---|
| `c2-qr.py` | HTTP laboratorní server |
| `agent` | Testovací ARM64 klient |
| `qr.png` | QR kód s odkazem |
| `exfil/` | Lokální výstupní adresář testovacích přenosů |

## Usage

### 1. Prepare the environment

Na Kali Linuxu ověř dostupnost potřebných nástrojů:

```bash
python3 --version
qrencode --version
adb version
```

### 2. Start laboratory server

Server využívá TCP port `8080`.

Doporučuje se provoz pouze v izolované testovací síti. Administrační rozhraní by nemělo být bez autentizace vystaveno internetu.

### 3. Generate QR code

Ukázka vytvoření QR kódu pro lokální laboratorní stránku:

```bash
qrencode -o qr.png \
  "http://127.0.0.1:8080/"
```

Pro skenování z jiného zařízení nahraď `127.0.0.1` adresou serveru dosažitelnou z telefonu.

### 4. Validate download

Pro kontrolu integrity testovacího souboru lze použít SHA-256:

```bash
sha256sum agent
```

Hash staženého souboru musí odpovídat původnímu souboru.

### 5. Run authorized testing

Spuštění nativního laboratorního klienta vyžaduje samostatný autorizovaný krok. V ověřeném scénáři bylo použito ADB.

Testovací komunikace by měla probíhat pouze s neškodnými příkazy a syntetickými soubory.

## API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Landing page |
| `/agent` | GET | Binary delivery |
| `/task` | GET | Polling endpoint |
| `/result` | POST | Results |
| `/upload` | POST | Test file transfer |
| `/push` | GET/POST | Laboratory task queue |
| `/queue` | GET | Queue status |
| `/files` | GET | Transferred file list |
| `/dashboard` | GET | Web dashboard |

## Verified Results

### Binary delivery

```text
GET /agent
HTTP 200 OK

Size:      7,012,648 bytes
Integrity: PASS
```

### Polling

```text
Client ID: redmi

[SERVER] Test task queued
[CLIENT] Polling server
[CLIENT] Task received
[CLIENT] Result submitted
[SERVER] Result received
```

### File transfer

| Test file | Size | Result |
|---|---:|---|
| `IMG_2024.jpg` | 20 000 B | PASS |
| `pic.png` | 5 000 B | PASS |
| `chaos_1.png` | 9 350 200 B | PASS |

Přenesená testovací data byla po Base64 dekódování porovnána s originály pomocí `cmp`.

**Integrity check: PASS**

## Android Execution Limitations

### Native binary vs APK

| Property | ELF (ARM64) | APK |
|---|---|---|
| Download via QR | Yes | Yes |
| Direct execution after download | No | No |
| Standard Android installation | No | Yes |
| User interaction required | Yes | Yes |
| Android permission model | Depends on execution context | App permissions |

### Storage restrictions

Na standardním Androidu nelze obvykle přímo spustit nativní ELF soubor ze sdíleného adresáře:

```text
/sdcard/Download
```

ADB shell používá jiný bezpečnostní kontext než běžně instalovaná Android aplikace. Výsledky z ADB proto nelze bez dalšího zobecňovat na APK.

### Persistence

`nohup` může umožnit pokračování procesu po ukončení shellu, ale **nezajišťuje automatické spuštění po restartu telefonu**.

## Security Considerations

Mezi hlavní analyzované bezpečnostní oblasti patří:

- QR-based social engineering a rizika nedůvěryhodných odkazů.
- Oddělení stažení souboru od jeho spuštění.
- Android application sandboxing.
- Runtime permissions.
- Ochrana sdíleného a soukromého úložiště.
- HTTP polling a bezpečnost síťové komunikace.
- Integrita přenesených dat.
- Dopady nadměrného zatížení systémových prostředků.

## Test Summary

```text
QR Generation           [PASS]
HTTP Download           [PASS]
Binary Integrity        [PASS]
HTTP Polling            [PASS]
Task Queue              [PASS]
Result Reporting        [PASS]
Test Data Transfer      [PASS]
Base64 Integrity        [PASS]

APK Execution           [NOT TESTED]
QR Auto Execution       [NOT SUPPORTED]
Reboot Persistence      [NOT VERIFIED]
```

## Cleanup

Po ukončení experimentu je vhodné:

1. Zastavit laboratorní server a testovacího klienta.
2. Ověřit, že na zařízení nezůstaly žádné testovací procesy.
3. Odstranit testovací soubory a nepotřebná výstupní data.
4. Vypnout USB debugging, pokud již není potřeba.
5. Uzavřít síťový přístup k laboratorním službám.

## Key Findings

**QR delivery ≠ code execution.**

Distribuce souboru, jeho instalace, spuštění a následný přístup k systémovým prostředkům představují samostatné bezpečnostní kroky.

Projekt ověřil komunikaci mezi klientem a serverem, HTTP distribuci a integritu testovacích přenosů. Automatické spuštění po načtení QR kódu ani perzistence po restartu nebyly prokázány.

---

**Environment:** Kali Linux / Android  
**Category:** Mobile Security Research  
**Purpose:** Authorized Security Testing & Education
