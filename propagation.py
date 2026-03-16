"""
propagation.py — Band activity and solar propagation data

Fetches two data sources on a background schedule:

1. PSKReporter (https://pskreporter.info)
   Queries FT8 spots sent from grid square DM13 in the last 15 minutes.
   This tells us which bands are carrying traffic from our region right now
   and which DXCC entities are being heard by stations around the world.
   API docs: https://pskreporter.info/pskquery5.htm
   Cache TTL: 3 minutes (PSKReporter requests no more than every 5 min)

2. NOAA Space Weather (https://services.swpc.noaa.gov)
   Fetches current Solar Flux Index (SFI) and planetary K-index (Kp).
   SFI > 150 = excellent HF conditions, < 80 = poor.
   Kp < 2 = quiet geomagnetic conditions (good DX), > 5 = storm (bad).
   Cache TTL: 15 minutes (solar indices change slowly)

Band activity summary per band:
  count     — number of FT8 spots in last 15 minutes
  avg_snr   — average signal-to-noise ratio in dB
  dxcc      — list of up to 6 DXCC entity codes being heard (e.g. "DL", "JA")
  activity  — "high" (>=20 spots), "moderate" (>=5), "low" (<5), "dead" (0)

To change the grid square or callsign, edit MY_GRID and MY_CALL below.
"""

import asyncio
import httpx
import xml.etree.ElementTree as ET
import traceback
from datetime import datetime, timezone
from typing import Optional

# ── Configuration ──────────────────────────────────────────────────────────────
MY_GRID = "DM13"    # Maidenhead grid square for Indio, CA
MY_CALL = "W7TLG"   # Used for future TX spot queries

# ── Band frequency boundaries (Hz) ─────────────────────────────────────────────
BAND_MAP = [
    (1800000,   2000000,  "160m"),
    (3500000,   4000000,  "80m"),
    (7000000,   7300000,  "40m"),
    (10100000,  10150000, "30m"),
    (14000000,  14350000, "20m"),
    (18068000,  18168000, "17m"),
    (21000000,  21450000, "15m"),
    (24890000,  24990000, "12m"),
    (28000000,  29700000, "10m"),
    (50000000,  54000000, "6m"),
]

BANDS = ["160m", "80m", "40m", "30m", "20m", "17m", "15m", "12m", "10m", "6m"]

# ── Cache state ────────────────────────────────────────────────────────────────
_pskreporter_cache: dict = {}
_solar_cache: dict = {}
_last_psk_fetch: float = 0.0
_last_solar_fetch: float = 0.0
PSK_TTL = 180     # seconds between PSKReporter fetches
SOLAR_TTL = 900   # seconds between NOAA fetches


def freq_to_band(freq_hz: int) -> Optional[str]:
    """Map a frequency in Hz to a band name, or None if out of range."""
    for lo, hi, name in BAND_MAP:
        if lo <= freq_hz <= hi:
            return name
    return None


async def fetch_pskreporter() -> dict:
    """
    Fetch recent FT8 spots from PSKReporter for stations sending from MY_GRID.

    Uses the senderGrid parameter which returns spots where the *transmitting*
    station is located in our grid square. This gives us a picture of what
    the world is hearing from our region — i.e., which bands have open paths.

    Returns a dict keyed by band name with activity summary dicts.
    Returns cached data if within TTL, or last good cache on error.
    """
    global _pskreporter_cache, _last_psk_fetch
    now = asyncio.get_event_loop().time()

    # Return cached data if still fresh
    if now - _last_psk_fetch < PSK_TTL and _pskreporter_cache:
        return _pskreporter_cache

    url = (
        "https://retrieve.pskreporter.info/query?"
        f"senderGrid={MY_GRID}"
        "&flowStartSeconds=-900"        # last 15 minutes
        "&frange=1800000-54000000"      # 160m through 6m
        "&mode=FT8"
        "&statistics=false"
    )

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            xml_text = resp.text

        # PSKReporter returns XML regardless of format parameter
        root = ET.fromstring(xml_text)
        band_spots: dict = {b: [] for b in BANDS}

        for spot in root.findall("receptionReport"):
            try:
                freq = int(spot.get("frequency", 0))
                band = freq_to_band(freq)
                if not band:
                    continue
                band_spots[band].append({
                    "call":      spot.get("senderCallsign", ""),
                    "grid":      spot.get("senderLocator", ""),
                    "dxcc":      spot.get("senderDXCC", ""),
                    "dxcc_code": spot.get("senderDXCCCode", ""),
                    "snr":       int(spot.get("sNR", 0)),
                    "freq":      freq,
                })
            except:
                continue  # skip malformed spots silently

        # Build per-band summary
        summary = {}
        for band, spots in band_spots.items():
            if not spots:
                summary[band] = {
                    "count": 0, "avg_snr": None,
                    "dxcc": [], "activity": "dead"
                }
                continue

            avg_snr = sum(s["snr"] for s in spots) / len(spots)

            # Count spots per DXCC entity and return top 6
            dxcc_counts: dict = {}
            for s in spots:
                if s["dxcc_code"]:
                    dxcc_counts[s["dxcc_code"]] = dxcc_counts.get(s["dxcc_code"], 0) + 1
            top_dxcc = sorted(dxcc_counts, key=dxcc_counts.get, reverse=True)[:6]

            count = len(spots)
            activity = "high" if count >= 20 else "moderate" if count >= 5 else "low"

            summary[band] = {
                "count":    count,
                "avg_snr":  round(avg_snr, 1),
                "dxcc":     top_dxcc,
                "activity": activity,
            }

        _pskreporter_cache = summary
        _last_psk_fetch = now
        return summary

    except Exception as e:
        print(f"PSKReporter unavailable: {type(e).__name__}")
        # Return last good cache, or empty structure if no cache yet
        return _pskreporter_cache or {
            b: {"count": 0, "avg_snr": None, "dxcc": [], "activity": "unknown"}
            for b in BANDS
        }


async def fetch_solar() -> dict:
    """
    Fetch current solar propagation indices from NOAA Space Weather.

    Solar Flux Index (SFI): measures solar radio emissions at 10.7cm.
      < 80  = poor HF conditions
      80-120 = fair
      120-150 = good
      > 150  = excellent

    Planetary K-index (Kp): measures geomagnetic disturbance (0-9 scale).
      0-2 = quiet, good for DX especially on low bands
      3-4 = unsettled, some polar path degradation
      5+  = storm, significant HF disruption possible

    Returns cached data if within TTL.
    """
    global _solar_cache, _last_solar_fetch
    now = asyncio.get_event_loop().time()

    if now - _last_solar_fetch < SOLAR_TTL and _solar_cache:
        return _solar_cache

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            geomag = await client.get(
                "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json"
            )
            flux = await client.get(
                "https://services.swpc.noaa.gov/products/summary/10cm-flux.json"
            )

        sfi = None
        kp = None

        try:
            sfi = float(flux.json().get("Flux", 0))
        except:
            pass

        try:
            kp_data = geomag.json()
            if len(kp_data) > 1:
                kp = float(kp_data[-1][1])
        except:
            pass

        result = {
            "sfi":     sfi,
            "kp":      kp,
            "updated": datetime.now(timezone.utc).strftime("%H:%MZ"),
        }
        _solar_cache = result
        _last_solar_fetch = now
        return result

    except Exception as e:
        print(f"Solar fetch error: {e}")
        return _solar_cache or {"sfi": None, "kp": None, "updated": None}


async def get_propagation_state() -> dict:
    """
    Return combined propagation data — band activity plus solar indices.

    This is the top-level function called by main.py. It runs both fetches
    concurrently using asyncio.gather for efficiency.

    Returns:
        {
          "bands": { "20m": { "count": 1127, "avg_snr": -9.4, ... }, ... },
          "solar": { "sfi": 109.0, "kp": 3.33, "updated": "16:31Z" },
          "my_grid": "DM13",
          "my_call": "W7TLG"
        }
    """
    bands, solar = await asyncio.gather(
        fetch_pskreporter(),
        fetch_solar()
    )
    return {
        "bands":   bands,
        "solar":   solar,
        "my_grid": MY_GRID,
        "my_call": MY_CALL,
    }
