# FT-991A Web Control Panel

A web-based virtual front panel and AI-assisted band advisor for the Yaesu FT-991A transceiver, built for W7TLG. Runs alongside WSJT-X, RumlogNG, and other apps without conflict.

## Features

- **Virtual front panel** — VFO A/B display, band/mode switching, step tuning, RF/AF/RF gain sliders, NB/NR/ANF toggles, AGC, preamp cycling
- **Dual meters** — RX S-meter always visible, TX meter switchable between PWR/SWR/ALC/COMP
- **Band activity panel** — real-time FT8 spot counts and DXCC entities heard from DM13, refreshed every 6 minutes from PSKReporter
- **Solar indices** — SFI and Kp from NOAA, color-coded for quick assessment
- **Click any band card to QSY** — jumps rig to that band FT8 frequency
- **Propagation alerts** — automatic yellow banner when bands open or close, Kp spikes, or 10m/12m light up unexpectedly
- **AI Band Advisor** — ask Claude anything about propagation, bands, and DX strategy
- **Streaming responses** — Claude response appears word by word in real time
- **Multi-turn conversation** — scrollable conversation history with full context retained
- **Auto-QSY** — Claude can command the rig to change bands autonomously using tool calls
- **Disk cache** — PSKReporter data survives server restarts, preventing rate limiting

## Requirements

- Yaesu FT-991A connected via USB (Silicon Labs CP210x driver)
- macOS with Homebrew installed
- Python 3.9+
- rigctld (Hamlib) running on port 4532
- Anthropic API key (from console.anthropic.com)
- Active internet connection for PSKReporter, NOAA, and Claude API

## Installation

### 1. Install Hamlib

    brew install hamlib

### 2. Start rigctld automatically at login

The included launchd plist handles this. Load it once:

    launchctl load ~/Library/LaunchAgents/com.hamlib.rigctld.plist

The plist uses the persistent device name /dev/tty.usbserial-01A3286E0 which does not change on replug.

To restart rigctld manually if needed:

    launchctl stop com.hamlib.rigctld
    launchctl start com.hamlib.rigctld

### 3. Configure WSJT-X

In WSJT-X Settings -> Radio:
- Rig: Hamlib NET rigctl
- Network server: localhost:4532

This allows WSJT-X and the panel to share rigctld simultaneously.

### 4. Set up Python environment

    cd ~/ham-panel
    python3 -m venv venv
    source venv/bin/activate
    pip install fastapi uvicorn websockets httpx aiohttp anthropic

### 5. Set your Anthropic API key

    echo 'export ANTHROPIC_API_KEY="sk-ant-..."' >> ~/.zshrc
    source ~/.zshrc

### 6. Configure your callsign and grid

Edit propagation.py and update:

    MY_GRID = "DM13"    # your Maidenhead grid square
    MY_CALL = "W7TLG"   # your callsign

### 7. Start the panel

    cd ~/ham-panel
    source venv/bin/activate
    uvicorn main:app --host 0.0.0.0 --port 8000

Open your browser to http://localhost:8000

## File Structure

    ham-panel/
    ├── main.py              # FastAPI server, REST API, WebSocket, alert dispatch
    ├── rig.py               # rigctld client, all CAT control functions
    ├── propagation.py       # PSKReporter and NOAA data fetching with disk cache
    ├── advisor.py           # Claude AI band advisor, streaming, auto-QSY tool
    ├── monitor.py           # Propagation change detection and alert generation
    ├── static/
    │   └── index.html       # Complete web UI (HTML + CSS + JS, single file)
    ├── .propagation_cache.json  # Disk cache — auto-generated, survives restarts
    ├── README.md            # This file
    ├── DEVELOPER.md         # Guide for adding new controls
    └── QUICKSTART.md        # Day-to-day operating cheat sheet

## Architecture

    Browser <--WebSocket--> main.py <--TCP--> rigctld <--serial--> FT-991A
    Browser <--REST POST--> main.py <--TCP--> rigctld
    Browser <--REST GET---> main.py <--HTTPS--> PSKReporter / NOAA
    Browser <--SSE Stream-> main.py <--HTTPS--> Claude API

- rigctld acts as a CAT multiplexer — WSJT-X, RumlogNG, and this panel all connect simultaneously
- FastAPI serves the UI and handles all rig commands via REST endpoints
- WebSocket pushes rig state every second and propagation data every 6 minutes
- Propagation monitor compares successive snapshots and fires alerts on significant changes
- Claude API is called on demand via Server-Sent Events for streaming responses
- Auto-QSY uses Claude tool calls — Claude decides to change bands and server executes CAT command
- PSKReporter data is cached to disk so restarts do not trigger rate limiting

## Propagation Alerts

The monitor runs every 6 minutes alongside the propagation refresh and detects:
- Band opening: spot count jumps by 50+ and crosses activity threshold
- Band closing: spot count drops by 50+ and falls below activity threshold
- 10m or 12m lighting up: these bands going from dead/low to moderate/high
- Kp spike: Kp crosses above 4.0

When triggered, a yellow banner appears at the top of the page with a brief Claude explanation. The alert is also added to the AI advisor conversation history so you can ask follow-up questions.

Alert cooldown: 15 minutes minimum between alerts for the same condition.

## AI Band Advisor

The advisor panel at the bottom of the page connects to Claude with full context:
- Current rig state (frequency, mode, signal strength, power, DSP settings)
- Live FT8 band activity from PSKReporter (spot counts and DXCC entities)
- Current solar conditions (SFI and Kp)
- Recent propagation alerts (automatically added to conversation context)

Multi-turn conversation is supported with a scrollable history window.
Click New Conversation to start fresh.

Auto-QSY: check the Auto-QSY box and use action language like "QSY me to the best band".
A green notification bar confirms what frequency and mode Claude tuned to and why.

Approximate API cost: $0.002 to $0.004 per query (Claude Sonnet).

## PSKReporter Rate Limiting

PSKReporter asks clients not to query more than once every 5 minutes.
The app enforces a 6-minute TTL and persists the cache to disk.
If you see "PSKReporter unavailable: HTTPStatusError" repeatedly, your IP
has been temporarily banned — wait 30-60 minutes without restarting uvicorn.

## Serial Port Note

The FT-991A USB cable uses a Silicon Labs CP210x chip. On macOS the device
appears as both /dev/tty.SLAB_USBtoUARTx (where x increments on replug)
and /dev/tty.usbserial-XXXXXXXX (persistent, tied to cable serial number).
The launchd plist uses the persistent usbserial name to avoid port number issues.

## Troubleshooting

**Panel shows no frequency / rig dot is grey**
- Check rigctld is running: ps aux | grep rigctld
- Test connection: rigctl -m 2 f
- If rigctld is using wrong port: launchctl stop com.hamlib.rigctld then launchctl start com.hamlib.rigctld

**Band activity shows all zeros**
- PSKReporter may be rate limiting your IP — wait 30-60 minutes
- Check: curl -s -o /dev/null -w "%{http_code}" "https://retrieve.pskreporter.info/query?senderGrid=DM13&flowStartSeconds=-900&mode=FT8&statistics=false"
- 200 = OK, 503 = rate limited

**Claude advisor shows no response**
- Check ANTHROPIC_API_KEY is set: echo $ANTHROPIC_API_KEY
- Make sure uvicorn was started in a shell where the key is loaded

**Auto-QSY does nothing**
- Make sure the Auto-QSY checkbox is checked
- Use explicit action language: "QSY me to the best band" or "Move me to 40m"
