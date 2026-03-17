"""
logger.py — Conversation and session logger

Logs all AI advisor exchanges, auto-alerts, and auto-QSY events to a
timestamped text file in ~/ham-panel/logs/.

Filename format: session_YYYY-MM-DD_HH-MM-SS.txt
One file per uvicorn session — a new file is created each time the server starts.

Log format:
  [HH:MM:SS UTC] ROLE: content
  [HH:MM:SS UTC] AUTO-ALERT: message | explanation
  [HH:MM:SS UTC] AUTO-QSY: freq MHz mode — reason
"""

import os
from datetime import datetime, timezone

LOG_DIR = os.path.expanduser("~/ham-panel/logs")
_log_file = None
_log_path = None


def _get_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S UTC")


def _get_datestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def init():
    """
    Initialize the log file for this session.
    Called once at server startup.
    """
    global _log_file, _log_path
    os.makedirs(LOG_DIR, exist_ok=True)
    filename = "session_" + datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S") + ".txt"
    _log_path = os.path.join(LOG_DIR, filename)
    _log_file = open(_log_path, "w", buffering=1)  # line buffered
    _log_file.write(f"FT-991A Ham Panel Session Log\n")
    _log_file.write(f"Started: {_get_datestamp()}\n")
    _log_file.write("=" * 60 + "\n\n")
    print(f"Session log: {_log_path}")


def log_question(question: str):
    """Log a user question to the advisor."""
    if _log_file:
        _log_file.write(f"[{_get_timestamp()}] YOU: {question}\n\n")


def log_response(response: str):
    """Log Claude's full response after streaming completes."""
    if _log_file:
        _log_file.write(f"[{_get_timestamp()}] CLAUDE: {response}\n\n")
        _log_file.write("-" * 40 + "\n\n")


def log_alert(alert: dict, explanation: str):
    """Log a propagation alert and Claude's explanation."""
    if _log_file:
        msg = alert.get("message", "unknown")
        _log_file.write(f"[{_get_timestamp()}] AUTO-ALERT: {msg}\n")
        _log_file.write(f"  {explanation}\n\n")


def log_qsy(freq: int, mode: str, reason: str):
    """Log an auto-QSY event."""
    if _log_file:
        mhz = freq / 1e6
        _log_file.write(f"[{_get_timestamp()}] AUTO-QSY: {mhz:.4f} MHz {mode} — {reason}\n\n")


def log_rig_state(freq: int, mode: str, band: str):
    """Log rig state at the start of each question for context."""
    if _log_file:
        _log_file.write(f"[{_get_timestamp()}] RIG STATE: {freq/1e6:.4f} MHz {mode} ({band})\n")


def close():
    """Close the log file cleanly."""
    if _log_file:
        _log_file.write(f"\nSession ended: {_get_datestamp()}\n")
        _log_file.close()


def get_log_path() -> str:
    return _log_path or ""
