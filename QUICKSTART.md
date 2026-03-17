# Quick-Start Cheat Sheet — W7TLG FT-991A Panel

## Starting a radio session

1. Power on the FT-991A (USB cable connected)
2. Log in to MacBook — rigctld starts automatically via launchd
3. Open Terminal and run:

    cd ~/ham-panel && source venv/bin/activate
    uvicorn main:app --host 0.0.0.0 --port 8000

4. Open browser to http://localhost:8000
5. Launch WSJT-X and/or RumlogNG as normal

## Checking everything is working

- WS dot (top right) green = browser connected to panel
- RIG dot green = panel connected to rigctld and rig responding
- VFO display matches rig front panel
- Band activity panel populates within about 10 seconds
- Solar data (SFI and Kp) appears in top right of band activity panel

## If rigctld did not start automatically

    launchctl stop com.hamlib.rigctld
    launchctl start com.hamlib.rigctld

Or start manually (rig must be powered on and USB connected first):

    rigctld -m 1035 -r /dev/tty.usbserial-01A3286E0 -s 9600 -P RTS -p /dev/tty.SLAB_USBtoUART -C stop_bits=2

## Band activity panel

- Cards color-coded: green = high activity, yellow = moderate, orange = low, grey = dead
- Click any band card to QSY to that band FT8 frequency
- SFI above 120 = good HF conditions, below 80 = poor
- Kp green (2 or less) = quiet, yellow (3-4) = unsettled, red (5 or more) = geomagnetic storm
- Data refreshes every 3 minutes automatically
- If all cards show zero, PSKReporter may be down — restart uvicorn to clear cache

## AI Band Advisor

The advisor panel is at the bottom of the page. Type any question and press Enter or click Ask Claude.

Good questions to ask:
  "What is the best band for DX right now?"
  "Where should I look for JA stations?"
  "How long will 20m stay open to Europe?"
  "What is causing the poor conditions on 15m?"
  "Find me some rare DX in the current spot data"

Multi-turn conversation: ask follow-up questions without clicking New Conversation.
Claude remembers the context of the current session.
Click New Conversation to start fresh with a clean context.

Auto-QSY: check the Auto-QSY box and ask Claude to change bands.
Use action language: "QSY me to the best band" or "Move me to 40m FT8".
A green bar at the bottom confirms what frequency Claude tuned to and why.
The rig will actually change frequency when auto-QSY executes.

API cost: approximately $0.002 to $0.004 per question (about 300 questions per dollar).

## Common controls

Control          | What it does
-----------------|--------------------------------------------------
Band buttons     | Jump to FT8 frequency for that band
Step + arrows    | Tune VFO in precise increments
Go box           | Type frequency in MHz (14.225) or Hz (14225000)
AGC MED          | Good default for FT8 operating
Preamp IPO       | Best for strong signals and low noise floor
Preamp AMP1      | Use when signals are weak
NR toggle        | Noise reduction — helps on noisy bands
NB toggle        | Noise blanker — helps with impulse noise
ANF toggle       | Auto notch filter — removes carriers and heterodynes

## Meter modes

Button | Shows
-------|-----------------------------------------------
SIG    | Received signal strength (S-meter), always active
PWR    | Transmit power output
SWR    | Standing wave ratio (1.0 = perfect match)
ALC    | ALC level during transmit

## Stopping the panel

Press Ctrl+C in the Terminal window running uvicorn.
rigctld keeps running in the background — WSJT-X continues working normally.

## Restarting after a crash

    cd ~/ham-panel && source venv/bin/activate
    uvicorn main:app --host 0.0.0.0 --port 8000
