"""
rig.py — FT-991A CAT control via rigctld

This module provides all rig control functions for the FT-991A transceiver.
It communicates with rigctld (Hamlib's CAT daemon) over a local TCP socket
on port 4532. All other apps (WSJT-X, RumlogNG, etc.) share the same
rigctld instance, so there is no serial port conflict.

Hamlib command reference:
  f / F <hz>          — get / set VFO frequency
  m / M <mode> <bw>   — get / set mode and passband
  l <LEVEL>           — get a named level (STRENGTH, RFPOWER, AF, etc.)
  L <LEVEL> <val>     — set a named level
  u <FUNC>            — get a named function (NB, NR, ANF, etc.) as 0/1
  U <FUNC> <0|1>      — set a named function on or off

Supported levels on FT-991A (from `rigctl -m 2 l '?'`):
  PREAMP, ATT, AF, RF, SQL, RFPOWER, MICGAIN, NOTCHF, COMP,
  AGC, METER, SWR, ALC, STRENGTH, NB, MONITOR_GAIN, BAND_SELECT

Supported functions on FT-991A (from `rigctl -m 2 u '?'`):
  NB, COMP, VOX, TONE, TSQL, FBKIN, ANF, NR, APF, MON,
  MN, LOCK, RIT, TUNER, XIT, CSQL

AGC values:  0=OFF, 2=FAST, 3=SLOW, 5=MED, 6=AUTO
METER values: 1=SWR, 2=COMP, 4=ALC, 8=IDD, 32=PO(power), 64=VDD
PREAMP values: 0=IPO, 10=AMP1, 20=AMP2
"""

import socket
from typing import Optional

# rigctld connection settings — change only if running rigctld on a different host/port
RIGCTLD_HOST = "localhost"
RIGCTLD_PORT = 4532

# Preamp state machine — FT-991A cycles through these three values
PREAMP_STATES = [0, 10, 20]
PREAMP_LABELS = {0: "IPO", 10: "AMP1", 20: "AMP2"}


def send_command(command: str) -> str:
    """
    Send a single Hamlib command to rigctld and return the response string.

    Opens a fresh TCP connection for each command. This is intentionally
    stateless — rigctld handles multiplexing across all clients.

    Args:
        command: A Hamlib shorthand command string, e.g. "f", "F 14074000",
                 "l STRENGTH", "U NR 1"

    Returns:
        The response string from rigctld, stripped of whitespace.
        Returns empty string on timeout or connection error.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(3.0)
        s.connect((RIGCTLD_HOST, RIGCTLD_PORT))
        s.sendall((command + "\n").encode())
        response = b""
        while True:
            chunk = s.recv(1024)
            if not chunk:
                break
            response += chunk
            # rigctld terminates responses with RPRT <code>
            if b"RPRT" in chunk or len(response) > 0:
                break
    return response.decode().strip()


def get_freq() -> Optional[float]:
    """Return VFO A frequency in Hz, or None on error."""
    resp = send_command("f")
    try:
        return float(resp.split("\n")[0])
    except ValueError:
        return None


def set_freq(freq_hz: int) -> bool:
    """
    Set VFO A frequency.

    Args:
        freq_hz: Frequency in Hz, e.g. 14074000 for 20m FT8

    Returns:
        True if rigctld acknowledged with RPRT 0 (success)
    """
    resp = send_command(f"F {freq_hz}")
    return "RPRT 0" in resp


def get_mode() -> tuple:
    """
    Return current mode and passband bandwidth as a tuple.

    Returns:
        (mode_string, bandwidth_hz) e.g. ("PKTUSB", 3000)
        Mode strings include: USB, LSB, CW, CWR, AM, FM, PKTUSB, PKTLSB
    """
    resp = send_command("m")
    lines = resp.split("\n")
    mode = lines[0].strip() if len(lines) > 0 else "UNKNOWN"
    bw = int(lines[1].strip()) if len(lines) > 1 else 0
    return mode, bw


def set_mode(mode: str, bandwidth: int = 0) -> bool:
    """
    Set operating mode and optional passband width.

    Args:
        mode: Mode string — USB, LSB, CW, CWR, AM, FM, PKTUSB, PKTLSB
        bandwidth: Passband in Hz. 0 lets the rig use its default for the mode.

    Returns:
        True on success
    """
    resp = send_command(f"M {mode} {bandwidth}")
    return "RPRT 0" in resp


def get_level(level: str) -> Optional[float]:
    """
    Get a named Hamlib level value.

    Args:
        level: Level name e.g. "STRENGTH", "RFPOWER", "AF", "RF", "AGC"

    Returns:
        Float value, or None if the rig/Hamlib doesn't support this level.
        Note: RFPOWER and AF return 0.0–1.0 (normalized).
              STRENGTH returns dB relative to S9 (negative = below S9).
              SWR returns ratio (1.0 = perfect).
    """
    resp = send_command(f"l {level}")
    try:
        return float(resp.split("\n")[0])
    except ValueError:
        return None


def set_level(level: str, value: float) -> bool:
    """
    Set a named Hamlib level.

    Args:
        level: Level name e.g. "RFPOWER", "AF", "AGC", "METER"
        value: New value. Normalized 0.0–1.0 for RFPOWER/AF/RF.
               Integer codes for AGC and METER (see module docstring).

    Returns:
        True on success
    """
    resp = send_command(f"L {level} {value}")
    return "RPRT 0" in resp


def get_func(func: str) -> Optional[bool]:
    """
    Get a named Hamlib function state (on/off).

    Args:
        func: Function name e.g. "NB", "NR", "ANF", "TUNER"

    Returns:
        True if active, False if inactive, None on error
    """
    resp = send_command(f"u {func}")
    try:
        return bool(int(resp.split("\n")[0]))
    except ValueError:
        return None


def set_func(func: str, value: bool) -> bool:
    """
    Set a named Hamlib function on or off.

    Args:
        func: Function name e.g. "NB", "NR", "ANF"
        value: True to enable, False to disable

    Returns:
        True on success
    """
    resp = send_command(f"U {func} {1 if value else 0}")
    return "RPRT 0" in resp


def get_preamp() -> int:
    """
    Return current preamp state as an integer.

    Returns:
        0 = IPO (bypass), 10 = AMP1 (low noise), 20 = AMP2 (high gain)
    """
    resp = send_command("l PREAMP")
    try:
        return int(float(resp.split("\n")[0]))
    except ValueError:
        return 0


def set_preamp(value: int) -> bool:
    """
    Set preamp state directly.

    Args:
        value: 0 (IPO), 10 (AMP1), or 20 (AMP2)

    Returns:
        True on success
    """
    resp = send_command(f"L PREAMP {value}")
    return "RPRT 0" in resp


def cycle_preamp() -> int:
    """
    Cycle preamp through IPO → AMP1 → AMP2 → IPO.

    Returns:
        The new preamp value (0, 10, or 20)
    """
    current = get_preamp()
    idx = PREAMP_STATES.index(current) if current in PREAMP_STATES else 0
    next_val = PREAMP_STATES[(idx + 1) % len(PREAMP_STATES)]
    set_preamp(next_val)
    return next_val


def get_freqb() -> float:
    """
    Return VFO B frequency in Hz using Hamlib's extended VFO info command.

    Returns:
        Frequency in Hz, or 0.0 if VFO B is unavailable or command fails.
    """
    resp = send_command("\\get_vfo_info VFOB")
    try:
        for line in resp.split("\n"):
            if line.startswith("Freq:"):
                return float(line.split(":")[1].strip())
    except:
        pass
    return 0.0


def get_modeb() -> str:
    """
    Return VFO B mode string.

    Returns:
        Mode string e.g. "USB", or empty string on failure.
    """
    resp = send_command("\\get_vfo_info VFOB")
    try:
        for line in resp.split("\n"):
            if line.startswith("Mode:"):
                return line.split(":")[1].strip()
    except:
        pass
    return ""


def get_rig_state() -> dict:
    """
    Poll all key rig parameters in a single call and return as a dict.

    This is called every second by the FastAPI poll loop and pushed to
    all connected browser clients via WebSocket. Keep this lean — every
    item here costs a separate rigctld round-trip.

    Returns:
        Dict with keys: freq, mode, bandwidth, strength, rfpower, af, rf,
        nb, nr, anf, preamp, swr, freqb, modeb
    """
    freq = get_freq()
    mode, bw = get_mode()
    strength = get_level("STRENGTH")   # dB re S9, range approx -54 to +60
    rfpower = get_level("RFPOWER")     # normalized 0.0–1.0
    afvol = get_level("AF")            # normalized 0.0–1.0
    rfgain = get_level("RF")           # normalized 0.0–1.0
    nb = get_func("NB")                # noise blanker on/off
    nr = get_func("NR")                # noise reduction on/off
    anf = get_func("ANF")              # auto notch filter on/off
    preamp = get_preamp()              # 0, 10, or 20
    swr = get_level("SWR")
    comp = get_level("COMP")             # SWR ratio, 1.0 = perfect
    try:
        freqb = get_freqb()
        modeb = get_modeb()
    except:
        freqb = 0.0
        modeb = ""
    return {
        "freq": freq,
        "mode": mode,
        "bandwidth": bw,
        "strength": strength,
        "rfpower": rfpower,
        "af": afvol,
        "rf": rfgain,
        "nb": nb,
        "nr": nr,
        "anf": anf,
        "preamp": preamp,
        "swr": swr,
        "comp": comp,
        "freqb": freqb,
        "modeb": modeb,
    }
