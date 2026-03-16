"""
advisor.py — Claude AI band advisor for the FT-991A panel

This module packages up the current rig state and propagation data into
a structured context and sends it to the Claude API for analysis.

Claude acts as an expert amateur radio operator who understands HF
propagation, FT8 operating practice, and DX strategy. It receives
real-time data about what bands are open, solar conditions, and the
current rig configuration, then provides actionable recommendations.

The advisor is called on demand (when the user clicks "Ask Claude")
rather than on a timer, to keep API costs low and responses relevant.
"""

import os
import anthropic
from typing import Optional

# Initialize the Anthropic client using the ANTHROPIC_API_KEY environment variable
client = anthropic.Anthropic()

# Model to use — Sonnet gives the best balance of quality and speed for this use case
MODEL = "claude-sonnet-4-5"

SYSTEM_PROMPT = """You are an expert amateur radio operator and HF propagation specialist 
assisting W7TLG (Terry), an Amateur Extra class operator located in Indio, California 
(grid square DM13) in the Coachella Valley desert. 

Terry operates a Yaesu FT-991A transceiver and is primarily interested in FT8 DX — 
working as many distant and rare stations as possible. He is not contesting.

You have access to real-time data including:
- Current rig state (frequency, mode, signal strength, power settings)
- Live FT8 band activity from PSKReporter (spot counts and DXCC entities heard)
- Current solar conditions (SFI and Kp index)

When giving advice:
- Be specific and actionable — recommend exact bands and frequencies
- Explain WHY a band is good or bad given current conditions
- Note interesting DX opportunities visible in the spot data
- Consider the time of day and Terry's desert location for propagation paths
- Keep responses concise — 3 to 5 short paragraphs maximum
- If conditions are poor, say so honestly and explain what to expect

Solar flux interpretation:
- SFI below 80: poor, higher bands dead, stick to 40m and 80m
- SFI 80-120: fair, 20m reliable, 15m possible
- SFI 120-150: good, 15m and 17m open, 10m possible
- SFI above 150: excellent, all bands including 10m active

Kp interpretation:
- Kp 0-2: quiet, excellent conditions especially on low bands
- Kp 3-4: unsettled, some high-latitude path degradation
- Kp 5+: storm, significant disruption, avoid polar paths
"""


def format_context(rig_state: dict, prop_state: dict, user_question: Optional[str] = None) -> str:
    """
    Format rig state and propagation data into a clear context string for Claude.

    Args:
        rig_state: Current rig parameters from rig.get_rig_state()
        prop_state: Current propagation data from propagation.get_propagation_state()
        user_question: Optional specific question from the user

    Returns:
        Formatted context string ready to send to Claude
    """
    # Format frequency nicely
    freq_hz = rig_state.get("freq", 0) or 0
    freq_mhz = f"{freq_hz / 1e6:.4f} MHz" if freq_hz else "unknown"

    # Format signal strength as S-units
    strength = rig_state.get("strength")
    if strength is not None:
        if strength <= 0:
            s_unit = f"S{max(0, round((strength + 54) / 6))}"
        else:
            s_unit = f"S9+{round(strength)}dB"
        strength_str = f"{s_unit} ({strength:+.0f}dB)"
    else:
        strength_str = "unknown"

    # Format solar data
    solar = prop_state.get("solar", {})
    sfi = solar.get("sfi")
    kp = solar.get("kp")
    solar_str = f"SFI={sfi}, Kp={kp:.1f}" if sfi and kp else "unavailable"

    # Format band activity — only include bands with spots
    bands = prop_state.get("bands", {})
    band_lines = []
    for band in ["160m", "80m", "40m", "30m", "20m", "17m", "15m", "12m", "10m", "6m"]:
        b = bands.get(band, {})
        count = b.get("count", 0)
        if count > 0:
            avg_snr = b.get("avg_snr")
            dxcc = b.get("dxcc", [])
            snr_str = f"avg SNR {avg_snr:+.0f}dB" if avg_snr is not None else ""
            dxcc_str = f"DXCC heard: {', '.join(dxcc)}" if dxcc else ""
            parts = [p for p in [snr_str, dxcc_str] if p]
            band_lines.append(f"  {band}: {count} spots — {' | '.join(parts)}")
        else:
            band_lines.append(f"  {band}: no spots (dead)")

    context = f"""CURRENT RIG STATE:
Frequency: {freq_mhz}
Mode: {rig_state.get('mode', 'unknown')}
Signal strength: {strength_str}
RF Power: {round((rig_state.get('rfpower') or 0) * 100)}%
Preamp: {['IPO', 'AMP1', 'AMP2'][([0, 10, 20].index(rig_state.get('preamp', 0))) if rig_state.get('preamp', 0) in [0, 10, 20] else 0]}
NB: {'on' if rig_state.get('nb') else 'off'} | NR: {'on' if rig_state.get('nr') else 'off'}

SOLAR CONDITIONS ({solar.get('updated', 'unknown')}):
{solar_str}

FT8 BAND ACTIVITY FROM DM13 (last 15 minutes):
{chr(10).join(band_lines)}
"""

    if user_question:
        context += f"\nUSER QUESTION: {user_question}"
    else:
        context += "\nPlease assess current conditions and recommend the best band and strategy for DX right now."

    return context


async def get_advice(rig_state: dict, prop_state: dict, user_question: Optional[str] = None) -> str:
    """
    Send current state to Claude and return its band recommendation.
    Non-streaming version — used for scheduled/background advice.
    """
    context = format_context(rig_state, prop_state, user_question)

    message = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": context}
        ]
    )

    return message.content[0].text


def stream_advice(rig_state: dict, prop_state: dict,
                  conversation_history: list,
                  user_question: Optional[str] = None):
    """
    Stream Claude's response token by token.
    Uses the synchronous streaming API — FastAPI runs this in a thread.

    Args:
        rig_state: From rig.get_rig_state()
        prop_state: From propagation.get_propagation_state()
        conversation_history: List of prior message dicts for multi-turn context
        user_question: The user's question

    Yields:
        Text chunks as they arrive from Claude
    """
    context = format_context(rig_state, prop_state, user_question)

    # Build message list — prior conversation + new context message
    messages = conversation_history + [
        {"role": "user", "content": context}
    ]

    with client.messages.stream(
        model=MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=messages,
    ) as stream:
        for text in stream.text_stream:
            yield text


# Tool definition for auto-QSY
QSY_TOOL = {
    "name": "qsy_to_band",
    "description": "Command the FT-991A to change to a specific frequency and mode. Use this when you are recommending a band change and the user has auto-QSY enabled.",
    "input_schema": {
        "type": "object",
        "properties": {
            "frequency_hz": {
                "type": "integer",
                "description": "Frequency in Hz, e.g. 14074000 for 20m FT8"
            },
            "mode": {
                "type": "string",
                "description": "Mode string: USB, LSB, CW, PKTUSB (FT8), PKTLSB",
                "enum": ["USB", "LSB", "CW", "CWR", "AM", "FM", "PKTUSB", "PKTLSB"]
            },
            "reason": {
                "type": "string",
                "description": "Brief explanation of why this band change is recommended"
            }
        },
        "required": ["frequency_hz", "mode", "reason"]
    }
}


def stream_advice_with_tools(rig_state: dict, prop_state: dict,
                              conversation_history: list,
                              user_question: Optional[str] = None,
                              auto_qsy: bool = False):
    """
    Stream Claude's response with optional auto-QSY tool support.

    When auto_qsy is True, Claude may call qsy_to_band to command
    the rig directly. Yields tuples of (type, data) where type is
    'text', 'qsy', or 'done'.
    """
    context = format_context(rig_state, prop_state, user_question)
    if auto_qsy:
        context += """

Auto-QSY is ENABLED. You MUST use the qsy_to_band tool to command the rig. 
Do not just describe what frequency to go to — actually call the tool.
Call it with the best frequency and mode for current conditions."""
    else:
        context += "\n\nAuto-QSY is disabled. Do not use the qsy_to_band tool."

    messages = conversation_history + [
        {"role": "user", "content": context}
    ]

    if auto_qsy:
        with client.messages.stream(
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=messages,
            tools=[QSY_TOOL],
            tool_choice={"type": "auto"},
        ) as stream:
            for event in stream:
                if hasattr(event, 'type'):
                    if event.type == 'content_block_delta':
                        if hasattr(event.delta, 'text'):
                            yield ('text', event.delta.text)
            final = stream.get_final_message()
            for block in final.content:
                if block.type == 'tool_use' and block.name == 'qsy_to_band':
                    yield ('qsy', block.input)
    else:
        with client.messages.stream(
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=messages,
        ) as stream:
            for event in stream:
                if hasattr(event, 'type'):
                    if event.type == 'content_block_delta':
                        if hasattr(event.delta, 'text'):
                            yield ('text', event.delta.text)

    yield ('done', None)
