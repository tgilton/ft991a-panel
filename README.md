# FT-991A Web Control Panel

A web-based virtual front panel and band activity advisor for the Yaesu FT-991A transceiver, built for W7TLG. Runs alongside WSJT-X, RumlogNG, and other apps without conflict.

## Features

- **Virtual front panel** — VFO display, band/mode switching, step tuning, RF/AF/RF gain sliders, NB/NR/ANF toggles, AGC, preamp cycling
- **Live S-meter, SWR, power, and ALC meters** updating every second
- **VFO A and B display** with mode badges
- **Band activity panel** — real-time FT8 spot counts and DXCC entities heard from DM13, refreshed every 3 minutes from PSKReporter
- **Solar indices** — SFI and Kp from NOAA, color-coded for quick assessment
- **Click any band card to QSY** — jumps rig to that band's FT8 frequency

## Requirements

- Yaesu FT-991A connected via USB (Silicon Labs CP210x driver)
- macOS with Homebrew installed
- Python 3.9+
- rigctld (Hamlib) running on port 4532
- Active internet connection for PSKReporter and NOAA data

## Installation

### 1. Install Hamlib

    brew install hamlib

### 2. Start rigctld

    rigctld -m 1035 -r /dev/tty.SLAB_USBtoUART4 -s 9600 -P RTS -p /dev/tty.SLAB_USBtoUART -C stop_bits=2

To start rigctld automatically at login, install the included launchd plist:

    launchctl load ~/Library/LaunchAgents/com.hamlib.rigctld.plist

### 3. Configure WSJT-X

In WSJT-X Settings -> Radio:
- Rig: Hamlib NET rigctl
- Network server: localhost:4532

This allows WSJT-X and the panel to share rigctld simultaneously.

### 4. Set up Python environment

    cd ~/ham-panel
    python3 -m venv venv
    source venv/bin/activate
    pip install fastapi uvicorn websockets httpx aiohttp

### 5. Configure your callsign and grid

Edit propagation.py and update:

    MY_GRID = "DM13"    # your Maidenhead grid square
    MY_CALL = "W7TLG"   # your callsign

### 6. Start the panel

    cd ~/ham-panel
    source venv/bin/activate
    uvicorn main:app --host 0.0.0.0 --port 8000

Open your browser to http://localhost:8000

## File Structure

    ham-panel/
    ├── main.py           # FastAPI server, REST API, WebSocket broadcast
    ├── rig.py            # rigctld client, all CAT control functions
    ├── propagation.py    # PSKReporter and NOAA data fetching
    ├── static/
    │   └── index.html    # Complete web UI (HTML + CSS + JS)
    ├── README.md         # This file
    ├── DEVELOPER.md      # Guide for adding new controls
    └── QUICKSTART.md     # Day-to-day operating cheat sheet

## Architecture

    Browser <--WebSocket--> main.py <--TCP--> rigctld <--serial--> FT-991A
    Browser <--REST POST--> main.py <--TCP--> rigctld
    Browser <--REST GET---> main.py <--HTTPS--> PSKReporter / NOAA

- rigctld acts as a CAT multiplexer — WSJT-X, RumlogNG, and this panel all connect to it simultaneously without serial port conflicts
- FastAPI serves the UI and handles all rig commands via REST endpoints
- WebSocket pushes rig state every second and propagation data every 3 minutes to all connected browser tabs
- PSKReporter and NOAA are queried on background async tasks and cached to avoid hammering external APIs

## Troubleshooting

**Panel shows no frequency / rig dot is grey**
- Check rigctld is running: ps aux | grep rigctld
- Test connection: rigctl -m 2 f

**Band activity shows all zeros**
- Check internet connection
- PSKReporter may be slow — wait 30 seconds and reload
- Test manually: curl "https://retrieve.pskreporter.info/query?senderGrid=DM13&flowStartSeconds=-900&mode=FT8&statistics=false" | head -20

**WSJT-X loses rig control after panel starts**
- Both apps must connect to rigctld, not directly to the serial port
- Verify WSJT-X Radio settings show Hamlib NET rigctl and localhost:4532
