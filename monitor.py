"""
monitor.py — Propagation change detection and alert generation

Compares successive propagation snapshots to detect significant changes
in band conditions. When a change is detected, generates a brief alert
message via Claude explaining what happened and what to do.

Alert conditions monitored:
  - Band opening: spot count increases by 50+ and crosses activity threshold
  - Band closing: spot count drops by 50+ and falls below activity threshold
  - 10m/12m lighting up: these bands going from dead/low to moderate/high
  - Kp spike: Kp crosses above KP_ALERT_THRESHOLD

Alert cooldown: each band/condition has a minimum time between alerts
to avoid repeated notifications for the same event.
"""

import asyncio
import time
from typing import Optional
import anthropic

client = anthropic.Anthropic()
MODEL = "claude-sonnet-4-5"

# Thresholds
SPOT_JUMP_THRESHOLD = 50       # spots gained to trigger opening alert
SPOT_DROP_THRESHOLD = 50       # spots lost to trigger closing alert
KP_ALERT_THRESHOLD = 4.0       # Kp above this triggers geomagnetic alert
HIGH_BANDS = ["10m", "12m"]    # bands that get special attention when opening

# Cooldown — minimum seconds between alerts for same condition
ALERT_COOLDOWN = 900  # 15 minutes

# State
_previous_bands: dict = {}
_previous_kp: Optional[float] = None
_alert_cooldowns: dict = {}  # key -> last alert timestamp


def _on_cooldown(key: str) -> bool:
    """Check if an alert key is still in cooldown."""
    last = _alert_cooldowns.get(key, 0)
    return (time.time() - last) < ALERT_COOLDOWN


def _set_cooldown(key: str):
    """Mark an alert key as just fired."""
    _alert_cooldowns[key] = time.time()


def detect_changes(new_bands: dict, new_kp: Optional[float]) -> list:
    """
    Compare new propagation data against previous snapshot.
    Returns a list of alert dicts describing what changed.

    Each alert dict has:
      type: 'opening', 'closing', 'highband', 'kp_spike'
      band: band name (where applicable)
      old_count: previous spot count
      new_count: new spot count
      old_kp: previous Kp (for kp_spike)
      new_kp: new Kp (for kp_spike)
      message: human readable description
    """
    global _previous_bands, _previous_kp
    alerts = []

    for band, new_data in new_bands.items():
        old_data = _previous_bands.get(band, {})
        old_count = old_data.get("count", 0)
        new_count = new_data.get("count", 0)
        old_activity = old_data.get("activity", "dead")
        new_activity = new_data.get("activity", "dead")

        # Special alert for 10m and 12m lighting up
        if band in HIGH_BANDS:
            if (old_activity in ["dead", "low", "unknown"] and
                new_activity in ["moderate", "high"] and
                not _on_cooldown(f"highband_{band}")):
                alerts.append({
                    "type": "highband",
                    "band": band,
                    "old_count": old_count,
                    "new_count": new_count,
                    "message": f"{band} is lighting up with {new_count} spots"
                })
                _set_cooldown(f"highband_{band}")
                continue

        # Band opening alert
        gain = new_count - old_count
        if (gain >= SPOT_JUMP_THRESHOLD and
            new_activity in ["moderate", "high"] and
            old_activity in ["dead", "low", "unknown"] and
            not _on_cooldown(f"opening_{band}")):
            alerts.append({
                "type": "opening",
                "band": band,
                "old_count": old_count,
                "new_count": new_count,
                "dxcc": new_data.get("dxcc", []),
                "message": f"{band} opening — gained {gain} spots"
            })
            _set_cooldown(f"opening_{band}")

        # Band closing alert
        drop = old_count - new_count
        if (drop >= SPOT_DROP_THRESHOLD and
            old_activity in ["moderate", "high"] and
            new_activity in ["dead", "low"] and
            not _on_cooldown(f"closing_{band}")):
            alerts.append({
                "type": "closing",
                "band": band,
                "old_count": old_count,
                "new_count": new_count,
                "message": f"{band} closing — lost {drop} spots"
            })
            _set_cooldown(f"closing_{band}")

    # Kp spike alert
    if (new_kp is not None and
        _previous_kp is not None and
        new_kp >= KP_ALERT_THRESHOLD and
        _previous_kp < KP_ALERT_THRESHOLD and
        not _on_cooldown("kp_spike")):
        alerts.append({
            "type": "kp_spike",
            "old_kp": _previous_kp,
            "new_kp": new_kp,
            "message": f"Kp spiked to {new_kp:.1f} — geomagnetic disturbance"
        })
        _set_cooldown("kp_spike")

    # Update state
    _previous_bands = new_bands
    _previous_kp = new_kp

    return alerts


def explain_alert(alert: dict, prop_state: dict) -> str:
    """
    Ask Claude for a brief explanation of the alert and what to do.
    Returns a short 2-3 sentence response.
    """
    solar = prop_state.get("solar", {})
    bands = prop_state.get("bands", {})

    # Build a compact band summary
    active_bands = []
    for b in ["160m","80m","40m","30m","20m","17m","15m","12m","10m","6m"]:
        bd = bands.get(b, {})
        if bd.get("count", 0) > 0:
            active_bands.append(f"{b}:{bd['count']}spots")

    context = f"""Propagation alert for W7TLG (DM13, Indio CA):

Alert: {alert['message']}
Solar: SFI={solar.get('sfi')}, Kp={solar.get('kp')}
Active bands: {', '.join(active_bands)}
"""

    if alert["type"] in ["opening", "highband"]:
        dxcc = alert.get("dxcc", [])
        if dxcc:
            context += f"DXCC entities now heard on {alert['band']}: {', '.join(dxcc)}\n"
        context += f"\nIn 2-3 sentences: explain why this opening is significant for DX from Southern California, what entities are reachable, and whether W7TLG should QSY there now."

    elif alert["type"] == "closing":
        context += f"\nIn 2-3 sentences: explain what caused {alert['band']} to close, what to expect next, and which band to move to instead."

    elif alert["type"] == "kp_spike":
        context += f"\nIn 2-3 sentences: explain what this Kp spike means for HF conditions from Southern California, which bands are most affected, and what strategy to use."

    message = client.messages.create(
        model=MODEL,
        max_tokens=200,
        system="You are an expert amateur radio operator and HF propagation specialist. Give brief, specific, actionable advice. No preamble.",
        messages=[{"role": "user", "content": context}]
    )

    return message.content[0].text
