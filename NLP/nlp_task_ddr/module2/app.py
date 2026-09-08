"""
Module 2 - Flask Web Application
NWIS-Sentinel | SIH 2026 | PS SIH26121

Serves:
  GET /                          -> Leaflet map (map.html)
  GET /api/wells                 -> All 159 wells with coordinates + hazard stats
  GET /api/analogs               -> ?well_id=X&hazard=mud_loss -> ranked analog wells
  GET /api/formation/<name>      -> Wells sharing a formation
  GET /api/search/formation      -> ?q=Hordaland -> formation search

Run:  python app.py
URL:  http://localhost:5001
"""

import json
from pathlib import Path
from flask import Flask, jsonify, render_template, request, abort

BASE    = Path(__file__).parent
MODULE1 = BASE.parent / 'results' / 'module1_outputs'
OUTPUTS = BASE / 'outputs'

app = Flask(__name__, template_folder='templates', static_folder='static')

# ---------------------------------------------------------------------------
# Load all data at startup (fast in-memory serving)
# ---------------------------------------------------------------------------
print("Loading data...")

with open(MODULE1 / 'wells_metadata.json', encoding='utf-8') as f:
    WELLS = json.load(f)

events_raw = []
with open(MODULE1 / 'events.jsonl', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if line:
            events_raw.append(json.loads(line))

with open(OUTPUTS / 'analog_wells.json', encoding='utf-8') as f:
    ANALOGS = json.load(f)

with open(OUTPUTS / 'ahp_weights.json', encoding='utf-8') as f:
    AHP_WEIGHTS = json.load(f)

with open(OUTPUTS / 'formation_correlation.json', encoding='utf-8') as f:
    FORMATION_CORR = json.load(f)

# Index: hazard counts per well
from collections import defaultdict, Counter
hazard_counts = defaultdict(Counter)
for e in events_raw:
    if e.get('hazard') and e['hazard'] != 'none':
        hazard_counts[e['well_id']][e['hazard']] += 1

# Build map-ready well list (only fields needed by frontend)
WELLS_MAP = []
for w in WELLS:
    lat = w.get('latitude')
    lon = w.get('longitude')
    if lat is None or lon is None:
        continue
    WELLS_MAP.append({
        'well_id':        w['well_id'],
        'source':         w['source'],
        'is_synthetic':   w['is_synthetic'],
        'latitude':       lat,
        'longitude':      lon,
        'total_depth_m':  w.get('total_depth_m'),
        'bha_type':       w.get('bha_type'),
        'formation_count': w.get('formation_count', 0),
        'hazard_counts':  dict(hazard_counts.get(w['well_id'], {})),
    })

WELLS_INDEX = {w['well_id']: w for w in WELLS}
print(f"Ready - {len(WELLS_MAP)} wells with coordinates, {len(ANALOGS)} wells with similarity data")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    return render_template('map.html')


@app.route('/api/wells')
def api_wells():
    """Return all wells with map coordinates and hazard counts."""
    return jsonify({
        'count': len(WELLS_MAP),
        'wells': WELLS_MAP,
    })


@app.route('/api/analogs')
def api_analogs():
    """
    GET /api/analogs?well_id=7/1-2+S&hazard=mud_loss&top=10
    Returns top-N ranked analog wells for the given well + hazard,
    with full per-feature similarity breakdown.
    """
    well_id = request.args.get('well_id', '').strip()
    hazard  = request.args.get('hazard',  'mud_loss').strip()
    top_n   = int(request.args.get('top', 10))

    if not well_id:
        return jsonify({'error': 'well_id parameter required'}), 400
    if well_id not in ANALOGS:
        return jsonify({'error': f'well_id not found: {well_id}'}), 404
    if hazard not in ANALOGS[well_id]:
        return jsonify({'error': f'hazard not found: {hazard}. Valid: {list(ANALOGS[well_id].keys())}'}), 400

    top_analogs = ANALOGS[well_id][hazard][:top_n]
    return jsonify({
        'target_well':    well_id,
        'hazard':         hazard,
        'ahp_weights':    AHP_WEIGHTS[hazard]['weights'],
        'analogs_shown':  top_n,
        'analogs_total':  len(ANALOGS[well_id][hazard]),
        'analogs':        top_analogs,
        'transparency_note': (
            'Each score = sum of (AHP weight * individual similarity). '
            'feature_breakdown shows each component 0-1. '
            'ahp_weights_used shows the exact weight applied per feature.'
        ),
    })


@app.route('/api/ahp_weights')
def api_ahp_weights():
    """Return AHP pairwise matrices + derived weights for all hazards."""
    return jsonify(AHP_WEIGHTS)


@app.route('/api/formation/<formation_name>')
def api_formation(formation_name):
    """Return all wells that drilled through a given formation."""
    if formation_name not in FORMATION_CORR:
        return jsonify({'error': f'Formation not found: {formation_name}'}), 404
    return jsonify({
        'formation': formation_name,
        'data': FORMATION_CORR[formation_name],
    })


@app.route('/api/search/formation')
def api_search_formation():
    """GET /api/search/formation?q=Hordaland -> list matching formations."""
    q = request.args.get('q', '').strip().lower()
    if not q:
        return jsonify({'error': 'q parameter required'}), 400
    matches = [
        {'formation': name, 'well_count': data['well_count'], 'depth_range_m': data['depth_range_m']}
        for name, data in FORMATION_CORR.items()
        if q in name.lower()
    ]
    return jsonify({'query': q, 'results': matches, 'count': len(matches)})


@app.route('/api/well')
@app.route('/api/well/<path:well_id>')
def api_well_detail(well_id=None):
    """
    Return full well metadata for a given well_id.
    Accepts both:
      GET /api/well/<well_id>         (path param)
      GET /api/well?well_id=<well_id> (query param — safer for IDs with slashes)
    """
    if well_id is None:
        well_id = request.args.get('well_id', '').strip()
    if not well_id:
        return jsonify({'error': 'well_id required'}), 400
    w = WELLS_INDEX.get(well_id)
    if not w:
        return jsonify({'error': f'Well not found: {well_id}'}), 404
    return jsonify(w)


if __name__ == '__main__':
    print("\nStarting NWIS-Sentinel Module 2 Map Server...")
    print("Open:  http://localhost:5001")
    print("Press Ctrl+C to stop\n")
    app.run(host='0.0.0.0', port=5001, debug=False)
