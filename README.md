# FT-991A Web Control Panel

A web-based virtual front panel and AI-assisted band advisor for the Yaesu FT-991A transceiver, built for W7TLG. Runs alongside WSJT-X, RumlogNG, and other apps without conflict.

## Features

- **Virtual front panel** — VFO A/B display, band/mode switching, step tuning, RF/AF/RF gain sliders, NB/NR/ANF toggles, AGC, preamp cycling
- **Live meters** — S-meter, TX power, SWR, and ALC updating every second via WebSocket
- **Band activity panel** — real-time FT8 spot counts and DXCC entities heard from DM13, refreshed every 3 minutes from PSKReporter
- **Solar indices** — SFI and Kp from NOAA, color-coded for quick assessment
- **Click any band card to QSY** — jumps rig to that band FT8 frequency
- **AI Band Advisor** — ask Claude anything about propagation, bands, and DX strategy
- **Streaming responses** — Claude's advice appears word by word in real time
- **Multi-turn conversation** — ask follow-up questions with full context retained
- **Auto-QSY** — Claude can command the rig to change bands autonomously using tool calls

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

### 2. Start rigctld

    rigctld -m 1035 -r /dev/tty.usbserial-01A3286E0 -s 9600 -P RTS -p /dev/tty.SLAB_USBtoUART -C stop_bits=2

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
    ├── main.py           # FastAPI server, REST API, WebSocket broadcast
    ├── rig.py            # rigctld client, all CAT control functions
    ├── propagation.py    # PSKReporter and NOAA data fetching
    ├── advisor.py        # Claude AI band advisor, streaming, auto-QSY tool
    ├── static/
    │   └── index.html    # Complete web UI (HTML + CSS + JS, single file)
    ├── README.md         # This file
    ├── DEVELOPER.md      # Guide for adding new controls
    └── QUICKSTART.md     # Day-to-day operating cheat sheet

## Architecture

    Browser <--WebSocket--> main.py <--TCP--> rigctld <--serial--> FT-991A
    Browser <--REST POST--> main.py <--TCP--> rigctld
    Browser <--REST GET---> main.py <--HTTPS--> PSKReporter / NOAA
    Browser <--SSE Stream-> main.py <--HTTPS--> Claude API

- rigctld acts as a CAT multiplexer — WSJT-X, RumlogNG, and this panel all connect simultaneously without serial port conflicts
- FastAPI serves the UI and handles all rig commands via REST endpoints
- WebSocket pushes rig state every second and propagation data every 3 minutes
- Claude API is called on demand via Server-Sent Events for streaming responses
- Auto-QSY uses Claude tool calls — Claude decides to change bands and the server executes the CAT command

## AI Band Advisor

The advisor panel at the bottom of the page connects to Claude with full context:
- Current rig state (frequency, mode, signal strength, power, DSP settings)
- Live FT8 band activity from PSKReporter (spot counts and DXCC entities)
- Current solar conditions (SFI and Kp)

Claude acts as an expert operator who understands HF propagation, FT8 practice, and DX strategy. It gives specific, actionable advice grounded in real-time data.

Multi-turn conversation is supported — ask follow-up questions and Claude remembers the context of the current session. Click New Conversation to start fresh.

Auto-QSY: when the Auto-QSY checkbox is enabled and you ask Claude to change bands, it will use a tool call to command the rig directly. A green notification bar confirms what frequency and mode it tuned to and why.

Approximate API cost: $0.002 to $0.004 per query (Claude Sonnet).

## Troubleshooting

**Panel shows no frequency / rig dot is grey**
- Check rigctld is running: ps aux | grep rigctld
- Test connection: rigctl -m 2 f
- Make sure rig is powered on before rigctld starts

**Band activity shows all zeros**
- PSKReporter occasionally returns 503 errors — wait a few minutes and reload
- Test manually: curl "https://retrieve.pskreporter.info/query?senderGrid=DM13&flowStartSeconds=-900&mode=FT8&statistics=false" | head -5
- Restarting uvicorn clears the stale cache

**Claude advisor shows no response**
- Check ANTHROPIC_API_KEY is set: echo $ANTHROPIC_API_KEY
- Make sure uvicorn was started in a shell where the key is loaded
- Check uvicorn terminal for error messages

**Auto-QSY does nothing**
- Make sure the Auto-QSY checkbox is checked
- Use explicit action language: "QSY me to the best band" or "Move me to 40m"
- Check uvicorn terminal for "QSY event received" print statement

**WSJT-X loses rig control**
- Verify WSJT-X Radio settings show Hamlib NET rigctl and localhost:4532
- Both apps must connect through rigctld, not directly to the serial port
