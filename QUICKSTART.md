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
- Solar data (SFI and Kp) appears in top right of band panel

## If rigctld did not start automatically

    launchctl stop com.hamlib.rigctld
    launchctl start com.hamlib.rigctld

## Band activity panel

- Cards color-coded: green = high activity, yellow = moderate, orange = low, grey = dead
- Click any band card to QSY to that band FT8 frequency
- SFI above 120 = good HF conditions, below 80 = poor
- Kp green (2 or less) = quiet, yellow (3-4) = unsettled, red (5 or more) = storm
- Data refreshes every 6 minutes automatically
- If all cards show zero, PSKReporter may be rate limiting — wait 30-60 min

## Propagation alerts

Yellow banner appears automatically when:
- A band suddenly opens or closes (50+ spot change)
- 10m or 12m lights up unexpectedly
- Kp spikes above 4.0

Each alert includes a brief Claude explanation of what happened and what to do.
Click Dismiss to clear the banner. Alerts also appear in the AI advisor history.
Cooldown: same condition will not re-alert for 15 minutes.

## AI Band Advisor

Type any question and press Enter or click Ask Claude.

Good questions to ask:
  "What is the best band for DX right now?"
  "Where should I look for JA stations?"
  "How long will 20m stay open to Europe?"
  "QSY me to the best band" (with Auto-QSY checked)

Conversation scrolls within the history box — no page scrolling needed.
Click New Conversation to start fresh.

Auto-QSY: check the Auto-QSY box and use action language.
Green bar confirms what frequency Claude tuned to and why.
Cost: approximately $0.002 to $0.004 per question.

## Meters

RX meter (always visible):
  S-meter showing received signal strength continuously

TX meter (select with buttons):
  PWR  = transmit power output
  SWR  = standing wave ratio (1.0 = perfect)
  ALC  = ALC level during transmit
  COMP = compression level

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
ANF toggle       | Auto notch filter — removes carriers

## Stopping the panel

Press Ctrl+C in the Terminal window running uvicorn.
rigctld keeps running — WSJT-X continues working normally.

## Restarting after a crash

    cd ~/ham-panel && source venv/bin/activate
    uvicorn main:app --host 0.0.0.0 --port 8000
