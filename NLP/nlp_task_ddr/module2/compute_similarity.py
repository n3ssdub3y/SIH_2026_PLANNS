"""
Module 2 - Hazard-Specific Offset-Well Similarity Engine
NWIS-Sentinel | SIH 2026 | PS SIH26121

GLOBAL RULES COMPLIANCE:
  Rule 1: No hardcoded results - every score is computed from real data
  Rule 3: Full transparency - per-feature breakdown + AHP weights in every record
  Rule 4: README_module2_geospatial_and_similarity.md produced separately
  Rule 6: Runs end-to-end on real P1 data

INPUTS  (from Module 1):
  ../results/module1_outputs/wells_metadata.json
  ../results/module1_outputs/events.jsonl

OUTPUTS (for Module 3 + Module 4):
  outputs/analog_wells.json           ranked analogs per well x hazard
  outputs/ahp_weights.json            AHP pairwise matrices + eigenvector weights
  outputs/formation_correlation.json  cross-well formation/depth table

Similarity formula (per spec Section 5, Step 2):
  Similarity(well_i, hazard_h) = sum_k [ w_(h,k) * sim_k(well_i, target_well) ]
"""

import json, math
import numpy as np
from pathlib import Path
from collections import defaultdict

BASE    = Path(__file__).parent
MODULE1 = BASE.parent / 'results' / 'module1_outputs'
OUTPUTS = BASE / 'outputs'
OUTPUTS.mkdir(exist_ok=True)

print("=" * 65)
print("NWIS-Sentinel  Module 2 - Offset-Well Similarity Engine")
print("=" * 65)
print("\n[1/5] Loading Module 1 data...")

with open(MODULE1 / 'wells_metadata.json', encoding='utf-8') as f:
    wells = json.load(f)

events_raw = []
with open(MODULE1 / 'events.jsonl', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if line:
            events_raw.append(json.loads(line))

events_by_well = defaultdict(list)
for e in events_raw:
    events_by_well[e['well_id']].append(e)

print(f"   Wells loaded  : {len(wells)}")
print(f"   Events loaded : {len(events_raw)}")


# ---------------------------------------------------------------------------
# AHP PAIRWISE COMPARISON MATRICES
# Features: formation | mud_weight | bha_type | mud_type | trajectory
# Scale: 1=equal, 3=moderate, 5=strong, 7=very strong importance
# ---------------------------------------------------------------------------

FEATURE_NAMES = ['formation', 'mud_weight', 'bha_type', 'mud_type', 'trajectory']

AHP_MATRICES = {
    'mud_loss': np.array([
        [1,    3,    5,    5,    7   ],
        [1/3,  1,    3,    3,    5   ],
        [1/5,  1/3,  1,    1,    3   ],
        [1/5,  1/3,  1,    1,    3   ],
        [1/7,  1/5,  1/3,  1/3,  1   ],
    ], dtype=float),
    'stuck_pipe': np.array([
        [1,    1/3,  1/5,  1/3,  1/7 ],
        [3,    1,    1/3,  1,    1/5  ],
        [5,    3,    1,    3,    1/3  ],
        [3,    1,    1/3,  1,    1/5  ],
        [7,    5,    3,    5,    1    ],
    ], dtype=float),
    'overpressure': np.array([
        [1,    1/3,  5,    5,    7   ],
        [3,    1,    7,    7,    9   ],
        [1/5,  1/7,  1,    1,    3   ],
        [1/5,  1/7,  1,    1,    3   ],
        [1/7,  1/9,  1/3,  1/3,  1   ],
    ], dtype=float),
    'torque_spike': np.array([
        [1,    1/3,  1/5,  1/3,  1/5 ],
        [3,    1,    1/3,  1,    1/3  ],
        [5,    3,    1,    3,    1/3  ],
        [3,    1,    1/3,  1,    1/5  ],
        [5,    3,    3,    5,    1    ],
    ], dtype=float),
    'cementing': np.array([
        [1,    3,    3,    1/3,  5   ],
        [1/3,  1,    1,    1/5,  3   ],
        [1/3,  1,    1,    1/5,  3   ],
        [3,    5,    5,    1,    7   ],
        [1/5,  1/3,  1/3,  1/7,  1   ],
    ], dtype=float),
}

HAZARD_TYPES = list(AHP_MATRICES.keys())

ENGINEERING_RATIONALE = {
    'mud_loss':    'Formation fracture gradient + porosity dominate loss magnitude; mud weight is secondary control. Ref: Bourgoyne et al.; SPE-171915.',
    'stuck_pipe':  'Wellbore trajectory (inclination, dogleg severity) governs differential pressure sticking; BHA determines contact area. Ref: Maidla & Wojtanowicz 1990; SPE-179005.',
    'overpressure':'Mud weight vs pore pressure gradient is primary kick indicator; formation lithology sets pore pressure regime. Ref: Fertl 1976; Zhang 2011.',
    'torque_spike':'Trajectory shape (dogleg, build rate) and BHA drive friction torque and drag; mud type affects lubricity. Ref: Johancsik et al. 1984; SPE-163420.',
    'cementing':   'Mud type is dominant - OBM contamination severely degrades cement bond. Formation type determines bond strength. Ref: Nelson & Guillot; SPE-77771.',
}

RI = {1:0.00, 2:0.00, 3:0.58, 4:0.90, 5:1.12, 6:1.24, 7:1.32, 8:1.41, 9:1.45}

def ahp_weights(matrix):
    col_sums = matrix.sum(axis=0)
    normalised = matrix / col_sums
    w = normalised.mean(axis=1)
    return w / w.sum()

def ahp_consistency_ratio(matrix, weights):
    n = matrix.shape[0]
    lambda_max = float(np.mean((matrix @ weights) / weights))
    ci = (lambda_max - n) / (n - 1)
    return ci / RI[n]

print("\n[2/5] Computing AHP weights per hazard...")
ahp_results = {}
for hazard, matrix in AHP_MATRICES.items():
    w  = ahp_weights(matrix)
    cr = ahp_consistency_ratio(matrix, w)
    ahp_results[hazard] = {
        'features':              FEATURE_NAMES,
        'pairwise_matrix':       matrix.tolist(),
        'weights':               {f: round(float(w[i]), 4) for i, f in enumerate(FEATURE_NAMES)},
        'weights_vector':        [round(float(x), 4) for x in w],
        'consistency_ratio':     round(float(cr), 4),
        'consistency_acceptable': bool(cr < 0.10),
        'engineering_rationale': ENGINEERING_RATIONALE[hazard],
    }
    status = 'OK' if cr < 0.10 else 'WARN CR>0.10'
    print(f"   {hazard:<16}  weights={[round(x,3) for x in w]}  CR={cr:.3f}  {status}")


# ---------------------------------------------------------------------------
# FEATURE HELPERS
# ---------------------------------------------------------------------------

def formation_set(well):
    return {ft['formation'] for ft in (well.get('formation_tops') or [])}

def jaccard(sa, sb):
    if not sa and not sb: return 1.0
    if not sa or not sb:  return 0.0
    return len(sa & sb) / len(sa | sb)

def tokenise(s):
    for ch in ('-','/',  '(',')', ',', '_'):
        s = s.replace(ch, ' ')
    return {t for t in s.lower().split() if len(t) > 1}

def bha_tokens(well):
    return tokenise(str(well.get('bha_type') or ''))

def mud_tokens(well):
    mp = well.get('mud_program') or {}
    if isinstance(mp, dict):
        text = ' '.join([mp.get('mud_system','') or '', mp.get('base_fluid','') or ''])
    else:
        text = str(mp)
    return tokenise(text)

def _avg_mw(well_id):
    vals = [e['mud_weight_ppg'] for e in events_by_well.get(well_id,[]) if e.get('mud_weight_ppg') is not None]
    return float(np.mean(vals)) if vals else None

mud_weights_map = {w['well_id']: _avg_mw(w['well_id']) for w in wells}
_mw_vals  = [v for v in mud_weights_map.values() if v is not None]
_MW_MIN   = float(min(_mw_vals)) if _mw_vals else 8.0
_MW_MAX   = float(max(_mw_vals)) if _mw_vals else 18.0
_MW_RANGE = _MW_MAX - _MW_MIN or 1.0

def mud_weight_sim(aid, bid):
    a, b = mud_weights_map.get(aid), mud_weights_map.get(bid)
    if a is None or b is None: return 0.5
    dn = abs(a - b) / _MW_RANGE
    return float(math.exp(-(dn**2) / (2*0.30**2)))

def _inclination(well):
    traj = well.get('trajectory') or []
    return [pt.get('inclination_deg', 0.0) for pt in traj if (pt.get('md_m') or 0) > 0]

def trajectory_sim(wa, wb):
    sa, sb = _inclination(wa), _inclination(wb)
    if len(sa) < 2 or len(sb) < 2: return 0.5
    try:
        from fastdtw import fastdtw
        from scipy.spatial.distance import euclidean
        def sub(seq, n=50):
            step = max(1, len(seq)//n)
            return seq[::step]
        a2 = [[v] for v in sub(sa)]
        b2 = [[v] for v in sub(sb)]
        dist, _ = fastdtw(a2, b2, dist=euclidean)
        max_dtw = 90.0 * max(len(a2), len(b2))
        return float(1.0 - min(dist / max_dtw, 1.0)) if max_dtw > 0 else 1.0
    except ImportError:
        diff = abs(float(np.mean(sa)) - float(np.mean(sb)))
        return float(max(0.0, 1.0 - diff/90.0))


# ---------------------------------------------------------------------------
# PAIRWISE SIMILARITY
# ---------------------------------------------------------------------------
print("\n[3/5] Computing pairwise similarities (may take 1-3 mins)...")

_form_sets = {w['well_id']: formation_set(w) for w in wells}
_bha_sets  = {w['well_id']: bha_tokens(w)    for w in wells}
_mud_sets  = {w['well_id']: mud_tokens(w)    for w in wells}

analog_wells = {}
for i, target in enumerate(wells, 1):
    tid = target['well_id']
    analog_wells[tid] = {}
    for hazard in HAZARD_TYPES:
        wv = ahp_results[hazard]['weights_vector']
        analogs = []
        for candidate in wells:
            cid = candidate['well_id']
            if cid == tid: continue
            f_s  = jaccard(_form_sets[tid], _form_sets[cid])
            mw_s = mud_weight_sim(tid, cid)
            b_s  = jaccard(_bha_sets[tid], _bha_sets[cid])
            mt_s = jaccard(_mud_sets[tid], _mud_sets[cid])
            tr_s = trajectory_sim(target, candidate)
            sv   = [f_s, mw_s, b_s, mt_s, tr_s]
            score = sum(w*s for w,s in zip(wv, sv))
            analogs.append({
                'well_id':        cid,
                'source':         candidate['source'],
                'is_synthetic':   candidate['is_synthetic'],
                'latitude':       candidate.get('latitude'),
                'longitude':      candidate.get('longitude'),
                'weighted_score': round(score, 4),
                'feature_breakdown': {
                    'formation_sim':  round(f_s,  4),
                    'mud_weight_sim': round(mw_s, 4),
                    'bha_sim':        round(b_s,  4),
                    'mud_type_sim':   round(mt_s, 4),
                    'trajectory_sim': round(tr_s, 4),
                },
                'ahp_weights_used': {f: round(wv[j],4) for j,f in enumerate(FEATURE_NAMES)},
            })
        analogs.sort(key=lambda x: x['weighted_score'], reverse=True)
        analog_wells[tid][hazard] = analogs
    if i % 20 == 0 or i == len(wells):
        print(f"   Progress: {i}/{len(wells)} wells done")


# ---------------------------------------------------------------------------
# FORMATION CORRELATION
# ---------------------------------------------------------------------------
print("\n[4/5] Building formation correlation table...")
_fi = defaultdict(list)
for w in wells:
    for ft in (w.get('formation_tops') or []):
        _fi[ft['formation']].append({
            'well_id':     w['well_id'],
            'source':      w['source'],
            'is_synthetic': w['is_synthetic'],
            'depth_md_m':  ft.get('depth_md_m'),
            'tvd_m':       ft.get('tvd_m'),
            'latitude':    w.get('latitude'),
            'longitude':   w.get('longitude'),
        })

formation_correlation = {}
for formation, entries in sorted(_fi.items()):
    vd = [e['depth_md_m'] for e in entries if e.get('depth_md_m') is not None]
    formation_correlation[formation] = {
        'well_count':    len(entries),
        'depth_range_m': {'min': round(min(vd),1) if vd else None, 'max': round(max(vd),1) if vd else None},
        'wells':         sorted(entries, key=lambda x: x.get('depth_md_m') or 0),
    }
print(f"   {len(formation_correlation)} unique formations indexed")


# ---------------------------------------------------------------------------
# SAVE OUTPUTS
# ---------------------------------------------------------------------------
print("\n[5/5] Saving output files...")

with open(OUTPUTS/'analog_wells.json', 'w', encoding='utf-8') as f:
    json.dump(analog_wells, f, indent=2)
size_mb = (OUTPUTS/'analog_wells.json').stat().st_size / 1_048_576
print(f"   OK analog_wells.json          {size_mb:.1f} MB  ({len(analog_wells)} wells x {len(HAZARD_TYPES)} hazards)")

ahp_export = {}
for hazard, data in ahp_results.items():
    ahp_export[hazard] = {
        'engineering_rationale':  data['engineering_rationale'],
        'features':               data['features'],
        'matrix_note':            'Row i / Col j = how much more important feature_i is vs feature_j (Saaty 1980)',
        'pairwise_matrix':        data['pairwise_matrix'],
        'weights':                data['weights'],
        'weights_vector':         data['weights_vector'],
        'consistency_ratio':      data['consistency_ratio'],
        'consistency_acceptable': data['consistency_acceptable'],
        'consistency_threshold':  0.10,
    }
with open(OUTPUTS/'ahp_weights.json', 'w', encoding='utf-8') as f:
    json.dump(ahp_export, f, indent=2)
print("   OK ahp_weights.json           (5 hazards, fully auditable)")

with open(OUTPUTS/'formation_correlation.json', 'w', encoding='utf-8') as f:
    json.dump(formation_correlation, f, indent=2)
print(f"   OK formation_correlation.json ({len(formation_correlation)} formations)")

print("\n" + "="*65)
print("Module 2 similarity engine - COMPLETE")
print("All 3 output files ready for Module 3 consumption.")
print("="*65)
