# DAK Dashboard

A self-hosted wall dashboard for Raspberry Pi, replacing DAKBoard. Displays photos, calendars, weather, and Home Assistant sensors on a wall-mounted TV via Chromium kiosk mode.

## Requirements

- Raspberry Pi (3B+ or newer) with Ubuntu Server 22.04+
- Python 3.11+
- Node.js 18+
- `chromium-browser`, `unclutter`, `xorg`, `lightdm`

---

## Setup

### Step 1 — System dependencies

```bash
sudo apt install -y chromium-browser unclutter xorg lightdm
```

### Step 2 — Clone and configure

```bash
git clone https://github.com/youruser/dak.git
cd dak
cp config.example.json config.json
# Edit config.json with your credentials and settings (see Configuration below)
nano config.json
```

### Step 3 — Python dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Step 4 — Build frontend

```bash
npm install
npm run build
```

### Step 5 — systemd services

```bash
sudo cp systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable dak-server dak-browser
sudo systemctl start dak-server dak-browser
```

### Step 6 — Auto-login

Set the graphical target as default so the Pi boots into a desktop session:

```bash
sudo systemctl set-default graphical.target
```

Configure LightDM to auto-login (replace `ubuntu` with your username if different):

```bash
sudo nano /etc/lightdm/lightdm.conf
```

Add or edit the `[Seat:*]` section:

```ini
[Seat:*]
autologin-user=ubuntu
autologin-user-timeout=0
```

Reboot to apply:

```bash
sudo reboot
```

---

## Configuration

Edit `config.json` (never committed — based on `config.example.json`):

```json
{
  "icloud": {
    "shareToken": "YOUR_TOKEN_HERE",
    "photoIntervalSeconds": 30
  },
  "calendars": [
    { "name": "Family", "url": "https://...", "color": "#4CAF50" }
  ],
  "weather": {
    "provider": "openmeteo",
    "latitude": 50.07,
    "longitude": 14.43,
    "accuweatherApiKey": ""
  },
  "homeAssistant": {
    "url": "http://homeassistant.local:8123",
    "token": "YOUR_LONG_LIVED_TOKEN",
    "entities": [
      { "entityId": "sensor.living_room_temp", "label": "Living Room" }
    ]
  },
  "display": {
    "calendarDaysAhead": 2,
    "weatherDays": 5
  }
}
```

### Updating config

After editing `config.json`, restart only the backend — no frontend rebuild needed:

```bash
sudo systemctl restart dak-server
```

### Updating frontend

After changing frontend source files:

```bash
npm run build
sudo systemctl restart dak-server
```

---

## Calendar ICS URLs

The dashboard accepts standard ICS (iCalendar) URLs.

**iCloud:**
1. Open Calendar on Mac or iCloud.com
2. Click the share icon next to a calendar → enable **Public Calendar**
3. Copy the `webcal://` URL and replace `webcal://` with `https://`

**Google Calendar:**
1. Open Google Calendar → Settings → click your calendar
2. Scroll to **Integrate calendar** → copy the **Secret address in iCal format**

**Microsoft 365 / Outlook:**
1. Open Outlook → right-click a calendar → **Share** → **Publish to web**
2. Choose ICS format and copy the link

---

## iCloud Share Token

The `shareToken` is the identifier in your iCloud shared album URL.

1. Open the Photos app → select a shared album → click the share icon → **Copy Link**
2. The URL looks like: `https://www.icloud.com/photos/0abCDeFGhiJKlMnOpQrSTuvwX`
3. The token is the last path segment: `0abCDeFGhiJKlMnOpQrSTuvwX`
4. Paste that value into `config.json` as `icloud.shareToken`

---

## Logs

View live logs for each service:

```bash
# Backend (FastAPI)
journalctl -u dak-server -f

# Browser (Chromium kiosk)
journalctl -u dak-browser -f
```

To see the last 100 lines without following:

```bash
journalctl -u dak-server -n 100
journalctl -u dak-browser -n 100
```
