# claude-buddy (Kindle e-ink port)

A port of [m5-paper-buddy](https://github.com/op7418/m5-paper-buddy) for Kindle e-ink displays.
Displays Claude Code session status, approval requests, and logs on the Kindle screen — approve or deny with a tap.

## Features

- **Dashboard** — Real-time display of model name, current phase, active task, and activity log
- **Approval cards** — Approve or deny bash commands, file edits, and writes by touch. Countdown timer in the top-right corner
- **Multi-session** — List multiple Claude Code windows and switch between them with a tap. Automatically switches to approval cards from other sessions
- **Context usage** — Progress bar and percentage display for token consumption
- **DND mode** — Auto-approve all permission requests
- **KUAL extension** — Launch, stop, and view logs from the Kindle launcher

---

## Supported Devices

| Model | Identifier | Jailbreak | Status |
|---|---|---|---|
| Kindle 8th gen (2016) | sy69jl | WinterBreak | ✅ Supported |

---

## Setup

### 0. Jailbreak

**sy69jl (K8) — WinterBreak**
- Requires firmware 5.16.4 – 5.18.0.2
- Enable **Airplane Mode** before connecting (prevents OTA updates)

### 1. Hotfix + KUAL + MRPI

1. Copy `Update_hotfix_universal.bin` to the Kindle root → Settings → Update Your Kindle
2. Copy the `mrpackages/` folder and `KUAL-KDK-2.0.azw2` to `documents/`
3. Type `;log mrpi` in the search bar → Enter

### 2. Install packages via MRPI

Place the following `.bin` files in `mrpackages/` and run KUAL → MRPI:

- `Update_python3_0.15.N_install_pw2_and_up.bin` — Python 3.9.8
- `Update_usbnet_0.22.N_install_pw2_and_up.bin` — USBNet + SSH

Download from [NiLuJe's snapshots (MobileRead)](https://www.mobileread.com/forums/showthread.php?t=225030).

> py-fbink / Pillow / libevdev are bundled with the Python snapshot.

### 3. Verify SSH

Connect over WiFi. On the Kindle: KUAL → USBNetwork → Allow SSH over WiFi → Toggle USBNetwork ON.

```sh
ssh root@<Kindle WiFi IP>
```

Leave the password prompt blank on first login.

Find the Kindle's WiFi IP from your Mac:
```sh
arp -a | grep <Kindle MAC address>
```

Check if SSH is up:
```sh
nc -vz <Kindle WiFi IP> 22
```

If you get `Connection refused`, the IP is correct but the SSH server isn't running.
If the Kindle is mounted as a USB drive in Finder, eject it safely, then KUAL → USBNetwork → Toggle USBNetwork OFF → ON to restart SSH.

### 3.1. Key-based login (passwordless)

The USBNetwork `authorized_keys` on the Kindle lives at `/mnt/us/usbnet/etc/authorized_keys`, not `~/.ssh/authorized_keys`.

Generate a key on your Mac:
```sh
ssh-keygen -t rsa -b 4096 -f ~/.ssh/kindle_buddy -C "kindle-buddy"
```

> Use `rsa` first — older Kindle / Dropbear builds may not accept `ed25519`.

Copy the public key to the Kindle:
```sh
scp ~/.ssh/kindle_buddy.pub root@<KINDLE_IP>:/mnt/us/usbnet/etc/authorized_keys
```

To copy via Finder:
1. Connect the Kindle via USB and open it in Finder.
2. Open the `usbnet/etc/` folder (this maps to `/mnt/us/usbnet/etc/` on the Kindle).
3. In Finder press `Cmd-Shift-G` → `~/.ssh` and locate `kindle_buddy.pub`.
4. Copy `kindle_buddy.pub` into `usbnet/etc/` and rename it to `authorized_keys`.
5. Eject the Kindle safely, then KUAL → USBNetwork → Toggle USBNetwork OFF → ON.

If `authorized_keys` already exists, append rather than overwrite:
```sh
ssh root@<KINDLE_IP>
cat >> /mnt/us/usbnet/etc/authorized_keys
# Paste the single line from ~/.ssh/kindle_buddy.pub → Ctrl-D
```

Verify key login:
```sh
ssh -i ~/.ssh/kindle_buddy -o PasswordAuthentication=no root@<KINDLE_IP>
```

Once confirmed, add an entry to `~/.ssh/config` on your Mac:
```sh
mkdir -p ~/.ssh
touch ~/.ssh/config
chmod 700 ~/.ssh
chmod 600 ~/.ssh/config
chmod 600 ~/.ssh/kindle_buddy
```

> Run the `chmod` commands on the Mac — not inside an SSH session on the Kindle.

```sshconfig
Host kindle-buddy
  HostName <KINDLE_IP>
  User root
  IdentityFile ~/.ssh/kindle_buddy
  IdentitiesOnly yes
```

After this you can use:
```sh
ssh kindle-buddy
cd ~/claude-buddy
scp -r kindle kindle-buddy:/mnt/us/buddy
```

To disable password authentication, edit `/mnt/us/usbnet/etc/config` on the Kindle **only after** confirming key login works. This file is on the Kindle — it is not the same as `~/.ssh/config` on your Mac.
Check the relevant lines first, as the option name varies by USBNetwork / Dropbear version:
```sh
grep -nE 'PASS|PASSWORD|DROPBEAR|SSHD|AUTH' /mnt/us/usbnet/etc/config
```

Set `ALLOW_PASSWORD_LOGIN="true"` to `false` if present. For Dropbear startup-option style, add `-s` (disable password login).
Restart SSH with KUAL → USBNetwork → Toggle USBNetwork OFF → ON, then verify in a separate terminal:
```sh
ssh -i ~/.ssh/kindle_buddy -o PasswordAuthentication=no root@<KINDLE_IP>
```

Keep the existing SSH session open until you have confirmed the new session works.

### 4. Deploy the app

Run the following on your Mac (not inside an SSH session on the Kindle).

```sh
cd ~/claude-buddy
bash kindle/install/deploy.sh
```

This script copies both:
- App: `/mnt/us/buddy/app`
- KUAL extension: `/mnt/us/extensions/ClaudeBuddy`

If `Claude Buddy` does not appear in KUAL, verify the files on the Kindle:
```sh
ls -la /mnt/us/extensions/ClaudeBuddy
```

If `config.xml` / `menu.json` / `start.sh` are present, the files are in place. Try reopening KUAL or restarting the Kindle.

---

## Running the App

### Manual launch (for testing)

From your Mac:
```sh
ssh kindle-buddy 'cd /mnt/us/buddy/app && python3 buddy.py --transport wifi --tcp-port 9877 --log-level DEBUG'
```

Or SSH into the Kindle first:
```sh
ssh kindle-buddy
cd /mnt/us/buddy/app
python3 buddy.py --transport wifi --tcp-port 9877 --log-level DEBUG
```

If you only see `[root@kindle root]#`, the app is not running yet. Run the commands above from that prompt.

When running correctly, the Kindle log shows:
```text
[wifi] listening on 0.0.0.0:9877
buddy ready
```

When the Mac bridge connects:
```text
[wifi] connected from ...
[rx] {"total":...
[render] dashboard ...
```

If you see `[wifi] connected from ...` but no `[rx]` or `[render]`, the Mac bridge is not sending state JSON.

If `[render]` appears but the screen does not update, run an FBInk display test on the Kindle:
```sh
fbink -q -pmh "Claude Buddy FBInk test"
```

If that also fails to display, the issue is with the Kindle's display environment, not the app.

### Via KUAL (normal use)

`kindle/install/deploy.sh` automatically places `kual-extension/` into `extensions/ClaudeBuddy`.
On the Kindle: KUAL → Claude Buddy → Start Buddy.
If startup fails: KUAL → Claude Buddy → Status.

While Buddy is running, it grabs `/dev/input/event0` so touches don't pass through to the Kindle UI underneath.
`View Log` will show `[touch] grabbed /dev/input/event0` when active.
Stop Buddy only stops the process — it does not force-clear the Kindle screen.

The Kindle clock/status strip at the top is a safe zone and is never drawn over by Buddy.
Battery level is not shown inside the Buddy UI.

Main screen:
- `SETTINGS` — Open settings
- `EXIT` — Stop Buddy
- Bottom-right DND zone — Toggle DND

Settings screen:
- `BACK` — Return to main screen
- `EXIT` — Stop Buddy
- `DND` — Toggle DND
- `Full refresh` — Black-then-white full e-ink refresh to clear ghosting

View logs:
```sh
tail -f /mnt/us/buddy/buddy.log
```

---

## Project Structure

```
kindle/
├── app/
│   ├── buddy.py        # Main loop (transport + touch + display)
│   ├── display.py      # PIL → FBInk rendering (600×800)
│   ├── state.py        # JSON state parsing, thread-safe state management
│   ├── transport.py    # WiFi TCP (port 9877) + USB Serial
│   ├── touch.py        # evdev touch input (/dev/input/event0)
│   ├── frames.py       # Buddy ASCII art (IDLE/BUSY/ATTENTION etc.)
│   ├── layout.py       # Coordinate and font size constants
│   └── fonts/          # CJK-capable fonts (NotoSansCJKjp-Regular.otf etc.)
├── kual-extension/     # KUAL start/stop scripts
└── install/
    └── deploy.sh       # rsync deploy script
```

---

## Technical Notes

### FBInk (Python CFFI)

The installed module is `_fbink` (not `pyfbink`).
Initialize via CFFI:

```python
import _fbink
lib, ffi = _fbink.lib, _fbink.ffi
cfg = ffi.new("FBInkConfig *")
lib.fbink_init(lib.FBFD_AUTO, cfg)
```

### Writing to the screen

`fbink_print_raw_data` applies an unwanted coordinate transform due to rotation=3 and cannot be used.
Instead, write the PIL image **directly to `/dev/fb0`** and use FBInk only to trigger the e-ink refresh:

```python
raw = image.tobytes()  # 600×800, 8bpp, no rotation needed
LINE = 608  # physical line_length (600px + 8 padding)

with open("/dev/fb0", "r+b") as fb:
    for row in range(800):
        fb.seek(row * LINE)
        fb.write(raw[row * 600: row * 600 + 600])

cfg = ffi.new("FBInkConfig *")
cfg.wfm_mode = lib.WFM_GC16  # full refresh
lib.fbink_refresh(lib.FBFD_AUTO, 0, 0, 0, 0, cfg)
```

Coordinate mapping: `fb(col, row)` → `display(col, row)` — no transform needed.

### Touch device

`/dev/input/event0` (zforce2). Coordinates are correct out of the box (X: 0–599, Y: 0–799), no calibration needed.

### WiFi SSH

- Connect over WiFi only.
- Do not hardcode the Kindle IP — look it up with `arp -a` each time.
- Use `ssh kindle-buddy` after setting up key login.

---

## Implementation Status

| Phase | Description | Status |
|---|---|---|
| 0 | Jailbreak + Python + USBNet + SSH | ✅ Done |
| 1 | FBInk screen rendering | ✅ Done |
| 2 | Touch input | ✅ Done |
| 3 | state.py + frames.py | ✅ Done |
| 4 | display.py on-device rendering | ✅ Done |
| 5 | buddy.py integrated startup | ✅ Done |
| 6 | transport.py WiFi connection test | ✅ Done |
| 7 | claude_code_bridge.py TCP (`--transport tcp --kindle-ip`) | ✅ Done |
| 8 | KUAL extension (auto-placed to `extensions/ClaudeBuddy` on deploy) | ✅ Done |
| 9 | Approval card countdown (30s→0s, highlights below 10s) | ✅ Done |
| 10 | Multi-session list, tap to switch, auto-switch on approval | ✅ Done |
| 11 | Context usage progress bar + percentage | ✅ Done |

---

## Mac Setup

`tools/claude_code_bridge.py` supports TCP:

```sh
python3 tools/claude_code_bridge.py --transport tcp --kindle-ip KINDLE_WIFI_IP
```

Replace `KINDLE_WIFI_IP` with the actual IP. Do not paste `<...>` placeholders literally into zsh — the angle brackets are interpreted as redirects.

If `OSError: [Errno 48] Address already in use` appears, port `127.0.0.1:9876` is already in use. Start on a different port:

```sh
python3 tools/claude_code_bridge.py --transport tcp --kindle-ip KINDLE_WIFI_IP --http-port 9878
```

When using the Claude Code plugin:

```sh
BUDDY_TRANSPORT=tcp KINDLE_IP=KINDLE_WIFI_IP BUDDY_HTTP_PORT=9878 bash plugin/scripts/start.sh
```

To receive real Claude Code events, install hooks into Claude Code settings:

```sh
cd ~/claude-buddy
tools/install_claude_hooks.py
```

This script backs up `~/.claude/settings.json` and merges the hooks from `plugin/settings/hooks.json`. Restart the Claude Code session for changes to take effect.

If you see `daemon already running`, a previous bridge is still running.
Check status:
```sh
bash plugin/scripts/status.sh
```

Stop and restart:
```sh
bash plugin/scripts/stop.sh
BUDDY_TRANSPORT=tcp KINDLE_IP=KINDLE_WIFI_IP BUDDY_HTTP_PORT=9878 bash plugin/scripts/start.sh
```

View logs:
```sh
tail -f ~/.claude-buddy/daemon.log
```

### Auto-start bridge on Mac login

Use a LaunchAgent to start the bridge automatically at login.
The default Claude Code hooks POST to `127.0.0.1:9876`, so use HTTP port `9876` unless you changed it.

```sh
cd ~/claude-buddy
tools/install_bridge_launch_agent.sh KINDLE_WIFI_IP 9876
```

Example:
```sh
tools/install_bridge_launch_agent.sh 192.168.x.x 9876
```

Check status:
```sh
launchctl print gui/$(id -u)/com.kindle-buddy.bridge
tail -f ~/.claude-buddy/launchd.err.log
```

Remove:
```sh
tools/uninstall_bridge_launch_agent.sh
```

If you start on a port other than `9876`, update the POST destination in the Claude Code hooks to match.

### Test the bridge

Send mock hooks to verify Kindle rendering without a live Claude Code session.
With the bridge running on `--http-port 9878` or `BUDDY_HTTP_PORT=9878`:

```sh
cd ~/claude-buddy
bash tools/test_buddy_hooks.sh dashboard
```

Test an approval card:
```sh
bash tools/test_buddy_hooks.sh approval
```

Test a question card:
```sh
bash tools/test_buddy_hooks.sh question
```

`approval` / `question` cards close when tapped on the Kindle or after 30 seconds.

### Model name display

The bridge reads the model from Claude Code hook payloads or the transcript and shows a short name in the `MODEL` field on the Kindle.

Examples:
- `claude-sonnet-4-5-...` → `Sonnet 4.5`
- `claude-opus-4.1` → `Opus 4.1`
- `claude-3-5-haiku-...` → `Haiku 3.5`

The model name may appear after the assistant message is written to the transcript.

---

## License

GPL-3.0 — see [LICENSE](LICENSE)

This project is a Kindle e-ink port inspired by
[m5-paper-buddy](https://github.com/op7418/m5-paper-buddy) by op7418,
which is also licensed under GPL-3.0.
