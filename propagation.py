import asyncio
import httpx
import xml.etree.ElementTree as ET
import traceback
from datetime import datetime, timezone
from typing import Optional

MY_GRID = "DM13"
MY_CALL = "W7TLG"

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

BANDS = ["160m","80m","40m","30m","20m","17m","15m","12m","10m","6m"]

_pskreporter_cache = {}
_solar_cache = {}
_last_psk_fetch = 0.0
_last_solar_fetch = 0.0
PSK_TTL = 180
SOLAR_TTL = 900

def freq_to_band(freq_hz: int) -> Optional[str]:
    for lo, hi, name in BAND_MAP:
        if lo <= freq_hz <= hi:
            return name
    return None

async def fetch_pskreporter() -> dict:
    global _pskreporter_cache, _last_psk_fetch
    now = asyncio.get_event_loop().time()
    if now - _last_psk_fetch < PSK_TTL and _pskreporter_cache:
        return _pskreporter_cache

    url = (
        "https://retrieve.pskreporter.info/query?"
        f"senderGrid={MY_GRID}"
        "&flowStartSeconds=-900"
        "&frange=1800000-54000000"
        "&mode=FT8"
        "&statistics=false"
    )

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            xml_text = resp.text

        root = ET.fromstring(xml_text)
        band_spots = {b: [] for b in BANDS}

        for spot in root.findall("receptionReport"):
            try:
                freq = int(spot.get("frequency", 0))
                band = freq_to_band(freq)
                if not band:
                    continue
                sender = spot.get("senderCallsign", "")
                sender_grid = spot.get("senderLocator", "")
                dxcc = spot.get("senderDXCC", "")
                dxcc_code = spot.get("senderDXCCCode", "")
                snr = int(spot.get("sNR", 0))
                band_spots[band].append({
                    "call": sender,
                    "grid": sender_grid,
                    "dxcc": dxcc,
                    "dxcc_code": dxcc_code,
                    "snr": snr,
                    "freq": freq,
                })
            except:
                continue

        summary = {}
        for band, spots in band_spots.items():
            if not spots:
                summary[band] = {"count": 0, "avg_snr": None, "dxcc": [], "activity": "dead"}
                continue
            avg_snr = sum(s["snr"] for s in spots) / len(spots)
            dxcc_counts = {}
            for s in spots:
                if s["dxcc_code"]:
                    dxcc_counts[s["dxcc_code"]] = dxcc_counts.get(s["dxcc_code"], 0) + 1
            top_dxcc = sorted(dxcc_counts, key=dxcc_counts.get, reverse=True)[:6]
            count = len(spots)
            if count >= 20:
                activity = "high"
            elif count >= 5:
                activity = "moderate"
            else:
                activity = "low"
            summary[band] = {
                "count": count,
                "avg_snr": round(avg_snr, 1),
                "dxcc": top_dxcc,
                "activity": activity,
            }

        _pskreporter_cache = summary
        _last_psk_fetch = now
        return summary

    except Exception as e:
        traceback.print_exc()
        print(f"PSKReporter fetch error: {e}")
        return _pskreporter_cache or {b: {"count": 0, "avg_snr": None, "dxcc": [], "activity": "unknown"} for b in BANDS}

async def fetch_solar() -> dict:
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
            "sfi": sfi,
            "kp": kp,
            "updated": datetime.now(timezone.utc).strftime("%H:%MZ"),
        }
        _solar_cache = result
        _last_solar_fetch = now
        return result

    except Exception as e:
        print(f"Solar fetch error: {e}")
        return _solar_cache or {"sfi": None, "kp": None, "updated": None}

async def get_propagation_state() -> dict:
    bands, solar = await asyncio.gather(
        fetch_pskreporter(),
        fetch_solar()
    )
    return {
        "bands": bands,
        "solar": solar,
        "my_grid": MY_GRID,
        "my_call": MY_CALL,
    }
