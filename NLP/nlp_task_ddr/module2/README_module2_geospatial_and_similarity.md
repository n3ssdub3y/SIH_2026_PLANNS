# README — Module 2: Geospatial Visualization & Offset-Well Similarity Engine
## NWIS-Sentinel | SIH 2026 | PS SIH26121

---

## What This Module Does

Module 2 consumes Module 1 output files and builds two things:

**Part A — Interactive Geospatial Map**
- Plots all 159 wells on a Leaflet/OpenStreetMap interactive map
- Color-codes pins by data source (Volve = orange, FORCE 2020 = blue, Synthetic = red)
- Radius-based nearby-well search: select any well + radius (km) -> highlights all neighbors
- Click any pin -> popup with well details (depth, BHA type, hazard history)

**Part B — Hazard-Specific Offset-Well Similarity Engine**
- For each of the 5 hazards × 159 wells: ranks all 158 other wells by similarity
- Uses a DIFFERENT weighted feature set per hazard (this is the core novelty)
- AHP-derived weights are fully auditable (Saaty 1980 principal eigenvector method)
- Every similarity score includes per-feature breakdown — no black boxes

---

## Tech Stack

| Component | Tool | Why |
|---|---|---|
| Map frontend | Leaflet.js 1.9.4 + OpenStreetMap tiles (CSS dark filter) | Free, no API key ever required |
| Map backend | Flask 3.x (Python) | Lightweight REST API, easy for P4 to embed |
| Categorical similarity | Jaccard on token sets | Interpretable, standard set-overlap metric |
| Continuous similarity | Gaussian kernel | Smooth falloff, single tunable sigma |
| Trajectory similarity | Dynamic Time Warping (fastdtw) | Handles sequences of different lengths |
| AHP weight derivation | numpy eigenvector | Fully auditable, standard operations-research method |
| Data loading | Python stdlib json | No extra deps beyond numpy/scipy |

---

## Input Files (from Module 1)

Read from: `../results/module1_outputs/`

| File | Schema fields used |
|---|---|
| `wells_metadata.json` | well_id, source, latitude, longitude, is_synthetic, formation_tops, bha_type, mud_program, trajectory, total_depth_m |
| `events.jsonl` | well_id, mud_weight_ppg, hazard |

---

## Output Files (Module 3 + Module 4 consume these)

All in: `module2/outputs/`

### 1. `analog_wells.json` (75 MB)

Structure:
```json
{
  "<well_id>": {
    "<hazard>": [           // sorted by weighted_score descending
      {
        "well_id": "...",
        "source": "real_force2020",
        "is_synthetic": false,
        "latitude": 58.3,
        "longitude": 2.1,
        "weighted_score": 0.7234,
        "feature_breakdown": {
          "formation_sim":  0.667,
          "mud_weight_sim": 0.500,
          "bha_sim":        1.000,
          "mud_type_sim":   1.000,
          "trajectory_sim": 0.907
        },
        "ahp_weights_used": {
          "formation":  0.497,
          "mud_weight": 0.245,
          "bha_type":   0.105,
          "mud_type":   0.105,
          "trajectory": 0.047
        }
      }
    ]
  }
}
```

- **5 hazard keys per well:** `mud_loss`, `stuck_pipe`, `overpressure`, `torque_spike`, `cementing`
- **158 analogs per hazard** (all other wells), ranked descending
- **P3 usage:** Use the top-K analogs' historical event sequences for sequence alignment
- **P4 usage:** Display the feature breakdown table in the dashboard

### 2. `ahp_weights.json`

Structure:
```json
{
  "<hazard>": {
    "engineering_rationale": "...",
    "features": ["formation","mud_weight","bha_type","mud_type","trajectory"],
    "matrix_note": "Row i / Col j = how much more important feature_i is vs feature_j",
    "pairwise_matrix": [[...], ...],
    "weights": {"formation": 0.497, "mud_weight": 0.245, ...},
    "weights_vector": [0.497, 0.245, 0.105, 0.105, 0.047],
    "consistency_ratio": 0.028,
    "consistency_acceptable": true,
    "consistency_threshold": 0.10
  }
}
```

AHP Summary (all CR < 0.10 = acceptable per Saaty 1980):

| Hazard | Dominant Feature | CR |
|---|---|---|
| mud_loss | formation (49.7%) | 0.028 |
| stuck_pipe | trajectory (49.7%) | 0.028 |
| overpressure | mud_weight (52.1%) | 0.041 |
| torque_spike | trajectory (44.8%) | 0.048 |
| cementing | mud_type (49.7%) | 0.028 |

### 3. `formation_correlation.json`

Structure:
```json
{
  "<formation_name>": {
    "well_count": 53,
    "depth_range_m": {"min": 755.0, "max": 4374.0},
    "wells": [
      {"well_id":"...", "source":"...", "is_synthetic":false,
       "depth_md_m":2806.0, "tvd_m":-2745.15, "latitude":..., "longitude":...}
    ]
  }
}
```

- 59 unique formations indexed
- All wells sorted by ascending depth_md_m per formation
- **P3 usage:** Formation correlation context for risk model features
- **P4 usage:** Formation drill-through query in the dashboard

---

## How to Run

### Step 1 — Generate similarity outputs (run ONCE, takes ~2 minutes)
```bash
cd NLP/nlp_task_ddr
python module2/compute_similarity.py
```
Produces the 3 JSON files in `module2/outputs/`.

### Step 2 — Start the map server
```bash
python module2/app.py
```
Open: http://localhost:5001

### Step 3 — Use the map
- Select any well from the dropdown or click a pin
- Adjust the radius slider to highlight nearby wells
- Click a hazard pill (Mud Loss / Stuck Pipe / etc.) to see similarity rankings
- Each analog card shows the full per-feature breakdown

---

## Flask API Reference (for P4 integration)

| Endpoint | Method | Params | Returns |
|---|---|---|---|
| `/api/wells` | GET | — | All 159 wells with lat/lon + hazard counts |
| `/api/analogs` | GET | `well_id`, `hazard`, `top` (int) | Ranked analogs with feature breakdown |
| `/api/ahp_weights` | GET | — | Full AHP matrices + weights for all hazards |
| `/api/formation/<name>` | GET | — | All wells in that formation with depths |
| `/api/search/formation` | GET | `q` (string) | Formation name search |
| `/api/well/<well_id>` | GET | — | Full well metadata record |

**P4 Integration note:** The map runs at `localhost:5001`. Embed it as an iframe or migrate the templates/map.html directly into the P4 dashboard. All APIs are stateless JSON REST — no auth needed.

---

## Real vs Synthetic Data (Global Rule 4 Compliance)

| Data used | Source | Type |
|---|---|---|
| 118 FORCE 2020 wells | Zenodo #4351156 | REAL |
| ~9 Volve wellbores | Equinor / HuggingFace | REAL |
| 40 synthetic wells | Module 1 template generation | SYNTHETIC |
| All similarity scores | Computed from above | Derived |

The `is_synthetic` field is propagated through every analog entry and visible on every map pin (color-coded). Synthetic wells always show in red.

---

## AHP Engineering Rationale Summary

All AHP pairwise matrices were constructed from documented drilling-engineering references:

- **Mud Loss:** Formation fracture gradient is the dominant control on loss magnitude (Bourgoyne et al., SPE-171915)
- **Stuck Pipe:** Wellbore trajectory geometry (inclination, dogleg) drives differential sticking (Maidla & Wojtanowicz 1990, SPE-179005)
- **Overpressure:** Mud weight vs pore pressure gradient is the primary kick indicator (Fertl 1976, Zhang 2011)
- **Torque Spike:** Trajectory shape and BHA configuration control drag and torque (Johancsik et al. 1984, SPE-163420)
- **Cementing:** Mud type (OBM contamination) is the primary degrader of cement bond quality (Nelson & Guillot, SPE-77771)

---

## Known Limitations

- FORCE 2020 wells have formation-depth data but no real-time telemetry -> trajectory DTW uses formation-depth sequence as proxy; similarity scores for these wells rely more on categorical features
- Synthetic wells have no real GPS coordinates -> coordinates are approximate NCS-region values, always flagged `is_synthetic: true`
- Mud weight similarity uses mean event mud weight per well; a depth-segmented version would be more precise with more time
- With real OIL India WCR/DDR data: BHA and mud program fields would be richer, improving similarity precision significantly

---

## Files Produced by This Module

```
module2/
├── compute_similarity.py          # Run once to generate outputs
├── app.py                         # Flask server — run to start map
├── templates/map.html             # Leaflet map UI
├── outputs/
│   ├── analog_wells.json          # 75 MB — P3 + P4 consume this
│   ├── ahp_weights.json           # Fully auditable AHP data
│   └── formation_correlation.json # 59 formations indexed
└── README_module2_geospatial_and_similarity.md  (this file)
```

---

## Changelog (Post-Initial-Build Fixes)

| Date | Fix | Files Changed |
|---|---|---|
| 2026-09-08 | **Volve UTM zone bug** — `15/9-F-9A` longitude was projected using Zone 32N instead of Zone 31N, placing it ~6° too far east (inland Norway instead of North Sea). Corrected lon from `7.93482` → `1.93482`. | `wells_metadata.json`, `analog_wells.json` (790 entries patched) |
| 2026-09-08 | **Map tile provider** — Switched from CARTO (started requiring API key) to OpenStreetMap + CSS dark filter. No API key needed. | `templates/map.html` |
| 2026-09-08 | **Dropdown UI** — Replaced native OS `<select>` (white box, unreadable) with fully themed custom dropdown with live search. | `templates/map.html` |
| 2026-09-08 | **JS crash on well select** — `selectWell()` referenced deleted `<select id="well-select">` element, crashing before similarity panel could load. Fixed to update custom dropdown label instead. | `templates/map.html` |

---

## Impact on P3's Work

> **Short answer: P3's core work is completely safe. No action required from P3.**

| Change | Does P3 use this? | Impact |
|---|---|---|
| `map.html` UI fixes (dropdown, tiles, JS crash) | ❌ No — P3 doesn't use the frontend | Zero impact |
| `app.py` API fixes | ❌ No — P3 reads JSON files directly | Zero impact |
| `wells_metadata.json` Volve lon fix | ⚠️ Possibly — if P3 reads coords for display | Display-only. P3's similarity lookups use `well_id`, not coordinates |
| `analog_wells.json` coord patch (790 entries) | ⚠️ Possibly — coords embedded per analog | Display-only. P3's sequence alignment uses `well_id` + `weighted_score`, not lat/lon |
| Similarity scores in `analog_wells.json` | ✅ Untouched — not recomputed | Zero impact — all 125,610 scores identical |
| AHP weights in `ahp_weights.json` | ✅ Untouched | Zero impact |
| `formation_correlation.json` | ✅ Untouched | Zero impact |
| P1 files (`events.jsonl`, `flagged_real_incidents.json`) | ✅ Untouched | Zero impact |

**P3 can continue using all output files exactly as before.** The only thing that changed is the display coordinate for one well (`15/9-F-9A`), which does not affect sequence alignment, hazard prediction, or the backtest.

---

*Generated: 2026-09-08 | Updated: 2026-09-08 | P2 Owner | Module handoff: Ready for P3*
