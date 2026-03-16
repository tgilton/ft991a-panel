# Developer Guide — Adding New Controls

This guide explains how to add a new rig control to the panel. The process always involves three files: rig.py, main.py, and static/index.html.

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

For a standard level control you can reuse the existing /api/level endpoint — no new endpoint needed. The browser POSTs {"level": "SQL", "value": 0.5}.

For a custom endpoint (e.g. a multi-step cycle):

    class SqlRequest(BaseModel):
        value: float

    @app.post("/api/sql")
    def set_sql(req: SqlRequest):
        ok = rig.set_sql(req.value)
        return {"ok": ok}

### Step 3 — Add the UI control to static/index.html

Add a slider in the appropriate card section:

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

Add state update in the updateUI(state) function in the script section:

    if (state.sql !== null && document.activeElement !== document.getElementById('sl-sql')) {
      document.getElementById('sl-sql').value = state.sql;
      document.getElementById('v-sql').textContent = Math.round(state.sql * 100) + '%';
    }

## Hamlib Level vs Function

Levels (use l/L commands, float values):
  PREAMP, ATT, AF, RF, SQL, RFPOWER, MICGAIN, NOTCHF, COMP,
  AGC, METER, SWR, ALC, STRENGTH, NB, MONITOR_GAIN, BAND_SELECT

Functions (use u/U commands, 0 or 1):
  NB, COMP, VOX, TONE, TSQL, FBKIN, ANF, NR, APF, MON, MN, LOCK, RIT, TUNER, XIT, CSQL

Use setLevel() in JS for levels, setFunc() for functions.

Known value mappings for FT-991A:
  AGC: 0=OFF, 2=FAST, 3=SLOW, 5=MED, 6=AUTO
  METER: 1=SWR, 2=COMP, 4=ALC, 8=IDD, 32=PO(power), 64=VDD
  PREAMP: 0=IPO, 10=AMP1, 20=AMP2

## Controls NOT available via Hamlib on FT-991A

These require direct CAT serial access which conflicts with rigctld exclusive serial port lock:
- Filter WIDTH (SH command)
- NAR/WIDE toggle (NA command)
- Contour filter settings
- Most MEN menu items

## Adding a New Claude Tool (for Auto-QSY style features)

Claude can be given tools it can call during a conversation. The existing qsy_to_band tool in advisor.py is an example. To add a new tool:

1. Define the tool schema in advisor.py following the QSY_TOOL pattern
2. Add it to the tools list in stream_advice_with_tools()
3. Handle the tool_use block in the event loop
4. Yield a new event type tuple e.g. ('filter_change', block.input)
5. Handle the new event type in the generate() function in main.py
6. Execute the rig command and optionally notify the UI

## WebSocket Message Format

Rig state (every 1 second) — plain JSON dict, no type field:
  {"freq": 14074000, "mode": "PKTUSB", "strength": -12.0, ...}

Propagation data (every 3 minutes) — wrapped with type tag:
  {"type": "propagation", "data": {"bands": {...}, "solar": {...}}}

The browser distinguishes them in ws.onmessage by checking msg.type.

## Server-Sent Events for AI Streaming

The /api/advisor/stream endpoint returns a text/event-stream response.
Each line is formatted as: data: <content>

Special tokens:
  data: [DONE]          — stream complete, move response to history
  data: [QSY]{...json}  — auto-QSY was executed, show notification

The browser reads the stream with a ReadableStream reader, accumulating
chunks until [DONE] is received, then renders the full response.

## Adding a New External Data Source

1. Add async fetch functions to propagation.py following the cache pattern
2. Add the new data to the get_propagation_state() return dict
3. The data will automatically be included in Claude advisor context
4. Update updatePropagation() in index.html to display it in the UI
