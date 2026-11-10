"""
Module 1 tests — rules parity, schema contract, unit parsing, segmentation,
keyword traps/negation, and a jargon-recall smoke check for the semantic layer.

Run from NLP/nlp_task_ddr:   python -m pytest module1/
Model-dependent tests are skipped if sentence-transformers / the MiniLM weights
are unavailable. The jargon set is a regression smoke check, NOT a gold-set
evaluation (see eval_model_selection.py for the model-selection screen).
"""
import json
import os
import re
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import nlp_rules                                            # noqa: E402
from nlp_rules import EVENT_RECORD_KEYS, extract_entities   # noqa: E402
import units                                                # noqa: E402
import nlp_engine                                           # noqa: E402
from nlp_engine import HybridEngine, segment_document, parse_header, split_sentences, _keyword_hit  # noqa: E402

VOLVE_DIR = os.path.join(BASE, "..", "..", "datasets", "volve_data")
EVENTS = os.path.join(BASE, "results", "module1_outputs", "events.jsonl")


# ─── 1. refactor parity: committed corpus reproducible from nlp_rules ──────
@pytest.mark.skipif(not os.path.exists(os.path.join(VOLVE_DIR, "volve_ddrs_train.csv")),
                    reason="Volve DDR CSVs not present")
def test_rules_reproduce_committed_volve_events():
    import pandas as pd
    df = pd.concat([pd.read_csv(os.path.join(VOLVE_DIR, f))
                    for f in ("volve_ddrs_train.csv", "volve_ddrs_test.csv")], ignore_index=True)
    committed = [json.loads(l) for l in open(EVENTS, encoding="utf-8")]
    real = [e for e in committed if e["source"] == "real_volve"]
    mine = []
    for _, row in df.iterrows():
        out_t = str(row.get("output", "") or "")
        instr = str(row.get("instruction", ""))
        dm = re.search(r"(\d{4}-\d{2}-\d{2})", instr)
        wm = re.search(r"well\s+([A-Z0-9/_\-\.]+)", instr, re.I)
        mine.append(extract_entities(out_t, wm.group(1).strip() if wm else "VOLVE",
                                     dm.group(1) if dm else "UNKNOWN", "real_volve"))
    assert len(real) == len(mine) == 1759
    assert real == mine


def test_p1_pipeline_import_has_no_side_effects(tmp_path, monkeypatch):
    """Importing p1_full_pipeline must not run the pipeline (it used to)."""
    sys.path.insert(0, BASE)
    before = os.path.getmtime(EVENTS) if os.path.exists(EVENTS) else None
    import importlib
    p1 = importlib.import_module("p1_full_pipeline")
    assert callable(p1.main)
    assert p1.extract_entities is nlp_rules.extract_entities
    if before is not None:
        assert os.path.getmtime(EVENTS) == before


def test_p1_hybrid_defaults_to_separate_output_dir():
    sys.path.insert(0, BASE)
    import p1_full_pipeline as p1
    assert os.path.abspath(p1.parse_args(["--nlp", "hybrid"]).out) == os.path.abspath(p1.HYBRID_OUT)
    assert os.path.abspath(p1.parse_args([]).out) == os.path.abspath(p1.CANONICAL_OUT)


# ─── 2. schema contract ────────────────────────────────────────────────────
PAGES = [
    "Daily Drilling Report Acme Drilling\nWell ID: TEST-1  Well Name: T1\nReport For 01-Jun-21\n"
    "Measured Depth (ft): 6,000\nOperations Summary\n"
    "Drilled 8-1/2\" hole from 5,800' to 6,000'.\nTight hole encountered at 5,950', backreamed.\n"
    "Lost 45 bbl to formation at 6,000 ft, MW 9.8 ppg. Pumped LCM pill.\n",
    "Daily Drilling Report Acme Drilling\nWell ID: TEST-1  Well Name: T1\nReport For 01-Jun-21\n"
    "Comments: Total hours of NPT on daily report due to losses 3.5 HRS.\n",
    "Daily Drilling Report Acme Drilling\nWell ID: TEST-1  Well Name: T1\nReport For 02-Jun-21\n"
    "Measured Depth (ft): 6,400\nCurrent Operations: Drilling ahead at 6,400 ft.\n"
    "Drilled from 6,000' to 6,400' with no problems.\n",
]


def _check_record(r):
    assert tuple(r.keys()) == EVENT_RECORD_KEYS
    assert isinstance(r["depth_m"], float) and isinstance(r["npt_hours"], float)
    assert isinstance(r["volume_lost_bbl"], float) and isinstance(r["confidence"], float)
    assert r["mud_weight_ppg"] is None or isinstance(r["mud_weight_ppg"], float)
    assert r["event_type_id"] in nlp_rules.EVENT_VOCAB["event_types"]
    assert r["hazard"] == nlp_rules.EVENT_VOCAB["event_types"][r["event_type_id"]]["hazard"]
    assert r["is_synthetic"] is False and len(r["raw_text"]) <= 400


def test_keyword_only_engine_schema_and_segmentation():
    eng = HybridEngine(load_models=False)
    res = eng.extract_document(PAGES, default_well="fallback", source="uploaded_pdf_ocr")
    assert res["n_units"] == 2                                # 2 pages share 01-Jun-21
    assert res["well"]["well_id"] == "TEST-1"
    recs = res["records"]
    assert len(recs) == len(res["evidence"])
    for r in recs:
        _check_record(r)
    types = {(r["report_date"], r["event_type_id"]) for r in recs}
    assert ("2021-06-01", "EVT_TIGHT_HOLE") in types
    assert ("2021-06-01", "EVT_LCM_APPLIED") in types
    assert ("2021-06-02", "EVT_ROUTINE_DRILLING") in types
    tight = next(r for r in recs if r["event_type_id"] == "EVT_TIGHT_HOLE")
    assert tight["depth_m"] == pytest.approx(5950 * 0.3048, abs=0.2)     # from its own sentence, ft->m
    routine = next(r for r in recs if r["report_date"] == "2021-06-02")
    assert routine["depth_m"] == pytest.approx(6400 * 0.3048, abs=0.2)   # header MD
    assert routine["raw_text"].startswith("Drilling ahead")              # Current Operations narrative


# ─── 3. units ──────────────────────────────────────────────────────────────
@pytest.mark.parametrize("text,expected", [
    ("tight at 6,043 ft", 1841.9), ("losses at 7,850'", 2392.7), ("at 1842 m", 1842.0),
    ("to 4911 m MD", 4911.0), ("from 2,890 ftMD", 880.9),
])
def test_depth_units(text, expected):
    assert units.parse_depths(text)[0][0] == pytest.approx(expected, abs=0.2)


def test_depth_ignores_rates():
    assert units.parse_depths("losses of 36 m3/hr") == []


@pytest.mark.parametrize("text,ppg", [("MW 9.8 ppg", 9.8), ("1.18 SG", 9.83), ("72 pcf", 9.62),
                                      ("density 1,20 sg", 10.0)])
def test_mud_weight(text, ppg):
    assert units.parse_mud_weight_ppg(text) == pytest.approx(ppg, abs=0.02)


def test_volume_and_npt():
    assert units.parse_volume_bbl("Pumped 38m3 LCM pill") == pytest.approx(239.0, abs=0.5)
    assert units.parse_volume_bbl("lost 45 bbl") == 45.0
    assert units.parse_npt_hours("NPT 8.5 hrs") == 8.5
    assert units.parse_npt_hours("Total hours of NPT on daily report 13 due to Schlumberger 12.0 HRS.") == 12.0


def test_formation_gazetteer_and_no_company_names():
    assert units.parse_formation("in Precambrian granite") == "Precambrian Granite"
    assert units.parse_formation("drilling the Draupne Fm") == "Draupne"
    assert units.parse_formation("Geothermal Resource Group, Inc.") is None


# ─── 4. keyword traps / negation (hybrid layer only) ───────────────────────
@pytest.mark.parametrize("s", [
    "Strapped, OD, ID and Fishing Neck of HwDP.", "RIH with stinger to set kickoff plug.",
    "Drilled to 1083 m, no tight spots.", "Torque all 5.5\" drill pipe to 42K.",
    "Torqued all flanges.", "Investigated faulty torque setting on casing tong.",
])
def test_keyword_traps_suppressed(s):
    assert nlp_rules.classify_event(s) != "EVT_ROUTINE_DRILLING"   # the raw rule fires...
    assert _keyword_hit(s) is None                                 # ...the hybrid layer suppresses it


@pytest.mark.parametrize("s,evt", [
    ("Tight hole at 1,756 m; torqued connections afterwards.", "EVT_TIGHT_HOLE"),
    ("WOC prior to bullheading b-annulus to brine.", "EVT_WOC"),
    ("Once on bottom when filling pipe got pipe stuck.", "EVT_STUCK_PIPE"),
])
def test_keyword_true_hits_kept(s, evt):
    hit = _keyword_hit(s)
    assert hit is not None and hit[1] == evt


def test_template_lines_and_headings_dropped():
    pages = [f"Daily Drilling Report X Inc.\nPage {i}\nSlow Circulation Data:\nDrilled ahead {i} m." for i in range(4)]
    tpl = nlp_engine.template_lines(pages)
    sents = split_sentences(pages[0], tpl)
    assert not any("Daily Drilling Report" in s for s in sents)
    assert not any(s.startswith("Slow Circulation") for s in sents)
    assert nlp_engine.is_heading("Depth (ft) ROP (ft/hr) WOB (lbs) RPM Torque (ft lbs)")


# ─── 5. semantic layer (needs MiniLM) ──────────────────────────────────────
# Phrasings the keyword list misses; NOT taken from eval_model_selection.EVAL_SET.
JARGON = [
    "Pit volume up 8 bbl while drilling, flow check showed the well flowing.",
    "Well taking mud, losing around 6 m3 per hour to the formation.",
    "No returns at the flowline after entering the fractured zone.",
    "Pulled 50k over on the trip out at 2,400 m, worked through.",
    "String packed off and could not rotate or circulate.",
    "Hole packing off on connections, high drag observed.",
    "Connection gas peaked at 22 percent at 3,100 m.",
    "Spotted calcium carbonate bridging pill across the thief zone.",
    "Full returns regained after the second pill was spotted.",
    "Fired the jar down several times to free the string.",
    "Ran overshot and recovered the lost logging tool.",
    "Top drive stalled when torque jumped above the limit.",
    "Erratic rotary torque while drilling the interbedded section.",
    "Plug failed to bump and cement losses seen during displacement.",
    "Waited on cement to set for eight hours.",
    "Closed the annular and recorded shut-in pressures.",
    "Pore pressure increasing, splintery cavings over the shakers.",
    "Took weight running in at 1,950 m and reamed down.",
    "Seepage losses continued at a low rate while drilling ahead.",
    "Background gas increased sharply with gas-cut mud at surface.",
]
ROUTINE_SENTS = [
    "Circulated bottoms up and conditioned mud.", "Made up BHA and ran in hole to 1,200 m.",
    "Pressure tested casing to 3,000 psi, test OK.", "Held pre-job safety meeting with all crews.",
    "Laid down drill pipe and rigged down.", "Drilled ahead from 2,100 m to 2,250 m.",
    "Waited on weather.", "Changed out shaker screens.", "Nippled up BOP and tested.",
    "Performed FIT to 12.5 ppg EMW.",
]


@pytest.fixture(scope="module")
def engine():
    eng = HybridEngine(load_models=True)
    if eng.st is None:
        pytest.skip(f"MiniLM unavailable: {eng.load_error}")
    return eng


def test_semantic_layer_recovers_keyword_misses(engine):
    kw_hits = [nlp_rules.classify_event(s) != "EVT_ROUTINE_DRILLING" for s in JARGON]
    hyb_hits = [evt != "EVT_ROUTINE_DRILLING" for evt, _, _ in engine.classify_sentences(JARGON)]
    kw_recall, hyb_recall = sum(kw_hits) / len(JARGON), sum(hyb_hits) / len(JARGON)
    assert hyb_recall >= kw_recall + 0.30, (kw_recall, hyb_recall)
    assert hyb_recall >= 0.60, hyb_recall


def test_semantic_layer_no_routine_false_alarms(engine):
    fa = [s for s, (evt, _, _) in zip(ROUTINE_SENTS, engine.classify_sentences(ROUTINE_SENTS))
          if evt != "EVT_ROUTINE_DRILLING"]
    assert len(fa) <= 1, fa


def test_hybrid_engine_schema_with_models(engine):
    res = engine.extract_document(PAGES, default_well="fallback")
    assert res["model_info"]["mode"] == "hybrid"
    for r in res["records"]:
        _check_record(r)
