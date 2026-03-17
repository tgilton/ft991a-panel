# Developer Guide — Adding New Controls

This guide explains how to add a new rig control to the panel.
The process always involves three files: rig.py, main.py, and static/index.html.

## Example: Adding a Squelch slider

### Step 1 — Add the function to rig.py

First check if Hamlib supports the control:

    rigctl -m 2 l '?'   # lists supported levels
    rigctl -m 2 u '?'   # lists supported functions

SQL (squelch) appears in the level list, so add to rig.py:

    def get_sql():
        return get_level("SQL")

    def set_sql(value):
        return set_level("SQL", value)

Also add it to get_rig_state() so it updates automatically every second:

    sql = get_level("SQL")
    # add to return dict:
    "sql": sql,

### Step 2 — Add a REST endpoint to main.py

For a standard level control reuse the existing /api/level endpoint.
The browser POSTs {"level": "SQL", "value": 0.5}.

For a custom endpoint:

    class SqlRequest(BaseModel):
        value: float

    @app.post("/api/sql")
    def set_sql(req: SqlRequest):
        ok = rig.set_sql(req.value)
        return {"ok": ok}

### Step 3 — Add the UI control to static/index.html

Add a slider in the appropriate card:

    <div class="slider-block">
      <div class="slider-header">
        <span class="slider-name">SQUELCH</span>
        <span class="slider-val" id="v-sql">--</span>
      </div>
      <input type="range" min="0" max="1" step="0.01" id="sl-sql"
        oninput="setLevel('SQL',this.value);
                 document.getElementById('v-sql').textContent=
                 Math.round(this.value*100)+'%'">
    </div>

Add state update in the updateUI(state) function:

    if (state.sql !== null && document.activeElement !== document.getElementById('sl-sql')) {
      document.getElementById('sl-sql').value = state.sql;
      document.getElementById('v-sql').textContent = Math.round(state.sql * 100) + '%';
    }

## Known FT-991A Hamlib value mappings

AGC: 0=OFF, 2=FAST, 3=SLOW, 5=MED, 6=AUTO
METER: 1=SWR, 2=COMP, 4=ALC, 8=IDD, 32=PO(power), 64=VDD
PREAMP: 0=IPO, 10=AMP1, 20=AMP2

Supported levels: PREAMP, ATT, AF, RF, SQL, RFPOWER, MICGAIN, NOTCHF,
  COMP, AGC, METER, SWR, ALC, STRENGTH, NB, MONITOR_GAIN, BAND_SELECT

Supported functions: NB, COMP, VOX, TONE, TSQL, FBKIN, ANF, NR, APF,
  MON, MN, LOCK, RIT, TUNER, XIT, CSQL

## Controls NOT available via Hamlib on FT-991A

These require direct CAT serial access which conflicts with rigctld:
- Filter WIDTH (SH command)
- NAR/WIDE toggle (NA command)
- Contour filter settings
- Most MEN menu items

## Adding a new propagation alert condition

Edit monitor.py and add detection logic in detect_changes():

    if (some_condition and not _on_cooldown("my_alert_key")):
        alerts.append({
            "type": "my_type",
            "message": "Description of what happened",
            ... other fields ...
        })
        _set_cooldown("my_alert_key")

Add a label for the new type in ALERT_ICONS in static/index.html:

    var ALERT_ICONS = {
      ...
      my_type: 'My Alert Label'
    };

## Adding a new Claude tool for auto-QSY style features

1. Define the tool schema in advisor.py following the QSY_TOOL pattern
2. Add it to the tools list in stream_advice_with_tools()
3. Handle the tool_use block in the event loop
4. Yield a new event type tuple e.g. ('my_action', block.input)
5. Handle the new event type in generate() in main.py
6. Execute the rig command and notify the UI

## WebSocket message types

Rig state (every 1 second) — plain JSON dict, no type field:
  {"freq": 14074000, "mode": "PKTUSB", "strength": -12.0, ...}

Propagation data (every 6 minutes):
  {"type": "propagation", "data": {"bands": {...}, "solar": {...}}}

Alert (when triggered):
  {"type": "alert", "alert": {...}, "explanation": "Claude explanation"}

SSE stream tokens (advisor):
  data: <text chunk>
  data: [QSY]{"freq": 14074000, "mode": "PKTUSB", "reason": "..."}
  data: [DONE]

## PSKReporter cache

Propagation data is cached both in memory and on disk at .propagation_cache.json.
The disk cache survives server restarts. TTL is 6 minutes.
Do not delete the cache file while PSKReporter is rate-limiting your IP.
