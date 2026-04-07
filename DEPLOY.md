# DAK Dashboard — Deployment Guide

Target platform: Raspberry Pi or any Ubuntu Server 22.04/24.04 machine running in kiosk mode.

---

## 1. System Requirements

- Ubuntu Server 22.04/24.04 (or Raspberry Pi OS 64-bit)
- Python 3.11+
- Node.js 18+
- Chromium browser
- A display connected to the machine (HDMI)

---

## 2. Install System Dependencies

```bash
sudo apt update && sudo apt install -y \
  python3 python3-pip python3-venv \
  nodejs npm \
  chromium-browser \
  xorg lightdm openbox \
  unclutter
```

> On Raspberry Pi OS, `chromium-browser` may be named `chromium`. Check with `which chromium` after install.

---

## 3. Create a Dedicated User (optional but recommended)

The systemd services default to user `ubuntu`. On Raspberry Pi OS, the default user is `pi`. Adjust if needed — the username appears in `systemd/*.service` files.

---

## 4. Clone the Repository

```bash
git clone <repo-url> /home/ubuntu/dak
cd /home/ubuntu/dak
```

Replace `ubuntu` with your actual username if different.

---

## 5. Configure

```bash
cp config.example.json config.json
nano config.json
```

Fill in your values. Minimum required fields:

| Field | Description |
|-------|-------------|
| `icloud.shareToken` | Token from an iCloud shared album URL (the part after `?token=`) |
| `calendars[].url` | ICS feed URL (iCloud, Google, etc.) |
| `weather.latitude` / `longitude` | Your location coordinates |
| `homeAssistant.url` / `token` | HA instance URL and long-lived access token |

Optional integrations: `ms365` (Microsoft 365 calendars), `miniCalendar` (separate ICS feed).

See `CLAUDE.md` for the full config schema.

---

## 6. Build the Frontend

```bash
npm install
npm run build
```

This produces `static/js/app.js`. Re-run after any frontend change.

---

## 7. Set Up the Python Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## 8. Configure Auto-Login (LightDM)

The kiosk browser needs a graphical session. Configure LightDM for automatic login:

```bash
sudo nano /etc/lightdm/lightdm.conf
```

Add or update the `[Seat:*]` section:

```ini
[Seat:*]
autologin-user=ubuntu
autologin-user-timeout=0
user-session=openbox
```

Replace `ubuntu` with your actual username.

Set graphical mode as default:

```bash
sudo systemctl set-default graphical.target
```

---

## 9. Install Systemd Services

If your username is not `ubuntu`, edit the service files first:

```bash
# Replace 'ubuntu' with your actual username in both service files
sed -i 's/ubuntu/YOUR_USERNAME/g' systemd/dak-server.service
sed -i 's/ubuntu/YOUR_USERNAME/g' systemd/dak-browser.service
```

Install and enable:

```bash
sudo cp systemd/dak-server.service /etc/systemd/system/
sudo cp systemd/dak-browser.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable dak-server dak-browser
sudo systemctl start dak-server dak-browser
```

---

## 10. Verify

```bash
# Check backend is running
systemctl status dak-server
curl http://localhost:3000/api/data

# Check browser is running
systemctl status dak-browser

# Follow live logs
journalctl -u dak-server -f
journalctl -u dak-browser -f
```

The dashboard should appear on the connected display after a few seconds.

---

## Updating

After pulling changes:

```bash
cd /home/ubuntu/dak
git pull

# If Python dependencies changed
source .venv/bin/activate && pip install -r requirements.txt

# If frontend changed
npm run build

# Restart backend (browser restarts automatically via systemd dependency)
sudo systemctl restart dak-server
```

---

## Troubleshooting

**Browser shows blank screen or can't connect**
- Check `dak-server` is running: `systemctl status dak-server`
- Check port 3000 is listening: `ss -tlnp | grep 3000`
- The browser service waits 3 seconds after `dak-server` starts; give it a moment

**Photos not loading**
- Verify `icloud.shareToken` in `config.json`
- Check logs: `journalctl -u dak-server -f`

**Calendar events missing**
- Confirm the ICS URL is publicly accessible from the Pi
- Test: `curl "<your-ics-url>"` — should return iCalendar data

**Weather not showing**
- Default provider is MET.no (free, no key). Check coordinates are correct.
- Test: `curl "http://localhost:3000/api/data" | python3 -m json.tool | grep weather`

**Chromium command not found**
- On Raspberry Pi OS: check `which chromium` and update `ExecStart` in `dak-browser.service` accordingly

**Display is blank after reboot**
- Confirm LightDM auto-login is configured (step 8)
- Confirm graphical target is default: `systemctl get-default` → should return `graphical.target`
- Check: `journalctl -u lightdm -b`

---

## Kiosk Hardening (optional)

To prevent the screensaver or display power-off from blanking the TV:

```bash
# Add to /home/ubuntu/.config/openbox/autostart
xset s off
xset -dpms
xset s noblank
unclutter -idle 0 &
```

Create the file if it doesn't exist:

```bash
mkdir -p ~/.config/openbox
cat >> ~/.config/openbox/autostart << 'EOF'
xset s off
xset -dpms
xset s noblank
unclutter -idle 0 &
EOF
```
