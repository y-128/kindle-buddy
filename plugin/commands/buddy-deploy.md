---
description: Deploy buddy app to Kindle via SSH (USBNet rsync).
---

Deploys `kindle/app/` and `kindle/kual-extension/` to the Kindle at
`$KINDLE_IP` (default `192.168.15.244`) via `rsync` over USBNet SSH.

Prerequisites:
- USBNet enabled on Kindle (SSH accessible)
- Python 3 + Pillow + pyfbink installed on Kindle
- Fonts placed in `kindle/app/fonts/` (see README.txt there)

!`KINDLE_IP="${KINDLE_IP:-192.168.15.244}" bash "$CLAUDE_PLUGIN_ROOT/../kindle/install/deploy.sh"`
