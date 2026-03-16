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

Add state update in the updateUI(state) function in the script section:

    if (state.sql !== null && document.activeElement !== document.getElementById('sl-sql')) {
      document.getElementById('sl-sql').value = state.sql;
      document.getElementById('v-sql').textContent = Math.round(state.sql * 100) + '%';
    }

## Hamlib Level vs Function

Levels (use l/L commands, float values):
  RFPOWER, AF, RF, SQL, AGC, METER, PREAMP, NOTCHF, COMP, SWR, STRENGTH

Functions (use u/U commands, 0 or 1):
  NB, NR, ANF, TUNER, VOX, COMP, LOCK, RIT, XIT

Use setLevel() in JS for levels, setFunc() for functions.

## Controls NOT available via Hamlib on FT-991A

These require direct CAT serial access which conflicts with rigctld exclusive serial port lock:
- Filter WIDTH (SH command)
- NAR/WIDE toggle (NA command)
- Contour filter settings
- Most MEN menu items

## WebSocket Message Format

Rig state (every 1 second) — plain JSON dict, no type field:
  {"freq": 14074000, "mode": "PKTUSB", "strength": -12.0, ...}

Propagation data (every 3 minutes) — wrapped with type tag:
  {"type": "propagation", "data": {"bands": {...}, "solar": {...}}}

The browser distinguishes them in ws.onmessage by checking msg.type.

## Adding a New External Data Source

1. Add fetch functions to propagation.py following the same async/cache pattern
2. Add the new data to the get_propagation_state() return dict
3. Update updatePropagation() in index.html to display it
