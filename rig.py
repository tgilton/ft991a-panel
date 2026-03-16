import socket
from typing import Optional

RIGCTLD_HOST = "localhost"
RIGCTLD_PORT = 4532

PREAMP_STATES = [0, 10, 20]
PREAMP_LABELS = {0: "IPO", 10: "AMP1", 20: "AMP2"}

def send_command(command: str) -> str:
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
            if b"RPRT" in chunk or len(response) > 0:
                break
    return response.decode().strip()

def get_freq() -> Optional[float]:
    resp = send_command("f")
    try:
        return float(resp.split("\n")[0])
    except ValueError:
        return None

def set_freq(freq_hz: int) -> bool:
    resp = send_command(f"F {freq_hz}")
    return "RPRT 0" in resp

def get_mode() -> tuple:
    resp = send_command("m")
    lines = resp.split("\n")
    mode = lines[0].strip() if len(lines) > 0 else "UNKNOWN"
    bw = int(lines[1].strip()) if len(lines) > 1 else 0
    return mode, bw

def set_mode(mode: str, bandwidth: int = 0) -> bool:
    resp = send_command(f"M {mode} {bandwidth}")
    return "RPRT 0" in resp

def get_level(level: str) -> Optional[float]:
    resp = send_command(f"l {level}")
    try:
        return float(resp.split("\n")[0])
    except ValueError:
        return None

def set_level(level: str, value: float) -> bool:
    resp = send_command(f"L {level} {value}")
    return "RPRT 0" in resp

def get_func(func: str) -> Optional[bool]:
    resp = send_command(f"u {func}")
    try:
        return bool(int(resp.split("\n")[0]))
    except ValueError:
        return None

def set_func(func: str, value: bool) -> bool:
    resp = send_command(f"U {func} {1 if value else 0}")
    return "RPRT 0" in resp

def get_preamp() -> int:
    resp = send_command("l PREAMP")
    try:
        return int(float(resp.split("\n")[0]))
    except ValueError:
        return 0

def set_preamp(value: int) -> bool:
    resp = send_command(f"L PREAMP {value}")
    return "RPRT 0" in resp

def cycle_preamp() -> int:
    current = get_preamp()
    idx = PREAMP_STATES.index(current) if current in PREAMP_STATES else 0
    next_val = PREAMP_STATES[(idx + 1) % len(PREAMP_STATES)]
    set_preamp(next_val)
    return next_val

def get_freqb() -> float:
    resp = send_command("\\get_vfo_info VFOB")
    try:
        for line in resp.split("\n"):
            if line.startswith("Freq:"):
                return float(line.split(":")[1].strip())
    except:
        pass
    return 0.0

def get_modeb() -> str:
    resp = send_command("\\get_vfo_info VFOB")
    try:
        for line in resp.split("\n"):
            if line.startswith("Mode:"):
                return line.split(":")[1].strip()
    except:
        pass
    return ""

def get_rig_state() -> dict:
    freq = get_freq()
    mode, bw = get_mode()
    strength = get_level("STRENGTH")
    rfpower = get_level("RFPOWER")
    afvol = get_level("AF")
    rfgain = get_level("RF")
    nb = get_func("NB")
    nr = get_func("NR")
    anf = get_func("ANF")
    preamp = get_preamp()
    swr = get_level("SWR")
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
        "freqb": freqb,
        "modeb": modeb,
    }
