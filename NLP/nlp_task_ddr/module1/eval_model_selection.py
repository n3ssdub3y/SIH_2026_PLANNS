"""
Module 1 — zero-shot model-selection evaluation for the hybrid NLP layer.

Question: which language model, used zero-shot (no labelled training data
exists yet), best augments the keyword/regex extractor for 18-class DDR
event typing?

Candidates (all zero-shot):
  keyword      nlp_rules.classify_event (the current production baseline)
  bert         bert-base-uncased, mean-pooled embeddings + prototype cosine
  roberta      roberta-base,      mean-pooled embeddings + prototype cosine
  deberta      microsoft/deberta-v3-base, mean-pooled + prototype cosine
  minilm       sentence-transformers/all-MiniLM-L6-v2 + prototype cosine
  gliner       urchade/gliner_medium-v2.1 (DeBERTa-v3 backbone), event types
               given as natural-language span labels

Prototype classifiers predict argmax over all 18 classes (EVT_ROUTINE_DRILLING
has its own prototypes), so no per-model threshold is tuned on the test set.
GLiNER predicts the label of its highest-scoring span (threshold 0.3, the
library default); no span -> routine.

Every model is also scored as a *hybrid* with the keyword pass, exactly as it
would be deployed: keyword decides when it fires, the model fills in when the
keyword pass says routine.

Eval set: 60 sentences (43 hazard, 17 routine; 33 Volve, 27 authored). `volve` = verbatim sentences from the Equinor Volve
DDR corpus (datasets/volve_data). `authored` = paraphrase-heavy edge cases
written for this evaluation (e.g. "packed off", "pit gain", "pulled 40k over")
because Volve has few or no examples of some classes (kick, overpressure,
torque spike). Labels were assigned by the author; this is NOT a gold set with
inter-annotator agreement — treat the numbers as a model-selection screen.

Usage (project venv; uses the GPU if torch sees one):
    python module1/eval_model_selection.py [--out module1/outputs/model_selection.json]

GLiNER and DeBERTa-v3 are evaluation-only candidates and are NOT installed by
requirements.txt (neither is used by the pipeline). Without them those two rows
are skipped with a message. To reproduce the full table:
    pip install gliner==0.2.30 sentencepiece==0.2.0
"""
import argparse
import json
import os
import sys
import time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from nlp_rules import EVENT_VOCAB, classify_event          # noqa: E402
from event_prototypes import EVENT_PROTOTYPES, expand_abbreviations  # noqa: E402

ROUTINE = "EVT_ROUTINE_DRILLING"

# Natural-language labels used when the GLiNER candidate types an event span.
GLINER_EVENT_LABELS = {
    "partial mud losses":            "EVT_MUD_LOSS_PARTIAL",
    "total loss of returns":         "EVT_MUD_LOSS_TOTAL",
    "lost circulation material pill": "EVT_LCM_APPLIED",
    "circulation restored":          "EVT_CIRC_RESTORED",
    "stuck pipe":                    "EVT_STUCK_PIPE",
    "differential sticking":         "EVT_DIFF_STICKING",
    "tight hole or overpull":        "EVT_TIGHT_HOLE",
    "jarring":                       "EVT_JARRING",
    "fishing operation":             "EVT_FISHING",
    "well kick or influx":           "EVT_KICK",
    "gas in mud":                    "EVT_GAS_INFLUX",
    "well shut in":                  "EVT_BOP_SHUTIN",
    "abnormal pore pressure":        "EVT_OVERPRESSURE_DETECTED",
    "high torque":                   "EVT_TORQUE_UP",
    "torque spike":                  "EVT_TORQUE_SPIKE",
    "cement job failure":            "EVT_CEMENTING_FAILURE",
    "waiting on cement":             "EVT_WOC",
}
CLASSES = list(EVENT_VOCAB["event_types"].keys())

# (sentence, gold event_type_id, origin)
EVAL_SET = [
    # mud loss partial
    ("Flowchecked well and initial loss 12 m/ HR, reduced to 1,1 m3/ HR.", "EVT_MUD_LOSS_PARTIAL", "volve"),
    ("Took loss rate at 840m 540 LPM.", "EVT_MUD_LOSS_PARTIAL", "volve"),
    ("Partial returns observed while drilling at 2,310 m, approx. 4 m3/hr seeping to formation.", "EVT_MUD_LOSS_PARTIAL", "authored"),
    # mud loss total
    ("MU BHA for side track, RIH to 1266m, lost returns.", "EVT_MUD_LOSS_TOTAL", "volve"),
    ("Lost standpipe pressure and returns.", "EVT_MUD_LOSS_TOTAL", "volve"),
    ("No returns at surface after drilling into fractured zone at 3,105 m; well taking all fluid.", "EVT_MUD_LOSS_TOTAL", "authored"),
    # LCM
    ("Pumped 38m3 LCM pill from 2495m to 2351m.", "EVT_LCM_APPLIED", "volve"),
    ("Bled in LCM mix while drilling ty fm.", "EVT_LCM_APPLIED", "volve"),
    ("Spotted 20 bbl nut plug and mica sweep across thief zone to cure seepage.", "EVT_LCM_APPLIED", "authored"),
    # circulation restored
    ("Full returns regained after second pill; circulation re-established at 1,800 lpm.", "EVT_CIRC_RESTORED", "authored"),
    ("Losses healed, well static and circulating with full returns.", "EVT_CIRC_RESTORED", "authored"),
    # stuck pipe
    ("While reaming down from 3680m string became stuck momentarily at 3772m and 3842m.", "EVT_STUCK_PIPE", "volve"),
    ("Not able to come free with tool with 5 MT overpull.", "EVT_STUCK_PIPE", "volve"),
    ("String packed off at 2,045 m while pulling out, unable to rotate or circulate.", "EVT_STUCK_PIPE", "authored"),
    # differential sticking
    ("Attmepted to RIH with casing negative casing was differential stuck.", "EVT_DIFF_STICKING", "volve"),
    ("Pipe held against permeable sand after 15 min stationary survey; free with spotting fluid.", "EVT_DIFF_STICKING", "authored"),
    # tight hole
    ("Attemted to POOH, had to work tight spots at 4515m, 4454m and 4415m.", "EVT_TIGHT_HOLE", "volve"),
    ("Circulated bottoms up due to high drag.", "EVT_TIGHT_HOLE", "volve"),
    ("Pulled 40k over string weight at 1,620 m on trip out, backreamed through.", "EVT_TIGHT_HOLE", "authored"),
    ("Took weight at 2,210 m running in, worked string down.", "EVT_TIGHT_HOLE", "authored"),
    # jarring
    ("Worked and jarred pipe to 3241 where no further progress could be made.", "EVT_JARRING", "volve"),
    ("Fired jars two times and came free.", "EVT_JARRING", "volve"),
    # fishing
    ("Washed and reamed to top of fish.", "EVT_FISHING", "volve"),
    ("RIH with overshot to retrieve parted BHA left in hole at 2,980 m.", "EVT_FISHING", "authored"),
    # kick
    ("Got influx when testing BOP with spring loaded tool.", "EVT_KICK", "volve"),
    ("Pit gain of 12 bbl observed while drilling at 3,410 m, flow check positive.", "EVT_KICK", "authored"),
    ("Well flowing on connection, trip tank increasing.", "EVT_KICK", "authored"),
    # gas influx
    ("Background gas rose to 18% with connection gas peaks of 35% at 3,500 m.", "EVT_GAS_INFLUX", "authored"),
    ("Gas-cut mud at shakers, mud weight out reduced from 1.45 to 1.38 SG.", "EVT_GAS_INFLUX", "authored"),
    # BOP shut-in
    ("Closed annular preventer and recorded SIDPP 320 psi, SICP 450 psi.", "EVT_BOP_SHUTIN", "authored"),
    ("Shut well in on upper pipe rams and circulated out influx through choke.", "EVT_BOP_SHUTIN", "authored"),
    # overpressure
    ("Pore pressure indicators rising, d-exponent trending down and splintery cavings at shakers.", "EVT_OVERPRESSURE_DETECTED", "authored"),
    ("Abnormal formation pressure encountered at 3,850 m, raised mud weight to 1.62 SG.", "EVT_OVERPRESSURE_DETECTED", "authored"),
    # torque up
    ("Erratic torque 18-26 kft-lbs while drilling the interbedded sandstone.", "EVT_TORQUE_UP", "authored"),
    ("Rotary torque increasing steadily over the last stand, reduced WOB.", "EVT_TORQUE_UP", "authored"),
    # torque spike
    ("Top drive stalled out when torque spiked to the 35 kft-lbs limit at 2,744 m.", "EVT_TORQUE_SPIKE", "authored"),
    ("Sudden torque jump tripped the top drive at 1,960 m.", "EVT_TORQUE_SPIKE", "authored"),
    # cementing failure
    ("Attempted to perform cement job, but got problems with bulk transfer system.", "EVT_CEMENTING_FAILURE", "volve"),
    ("Lost returns during cement displacement, plug did not bump; squeeze job required.", "EVT_CEMENTING_FAILURE", "authored"),
    ("Top of cement found 300 m lower than planned on CBL, poor bond across shoe.", "EVT_CEMENTING_FAILURE", "authored"),
    # WOC
    ("WOC prior to bullheading b-annulus to brine.", "EVT_WOC", "volve"),
    ("Waited on cement for 8 hrs before testing casing.", "EVT_WOC", "authored"),
    # routine (incl. keyword traps from the real corpus)
    ("Circulated and conditioned mud.", ROUTINE, "volve"),
    ("RIH with stinger to set kickoff plug.", ROUTINE, "volve"),
    ("Pressure tested BOP/HPDR against BOP test plug and closed pipe rams.", ROUTINE, "volve"),
    ("Backreamed from 2850m to 2608m.", ROUTINE, "volve"),
    ("Drilled from 978 m to 1083 m, performed wiper trip to the shoe and back to TD, no tight spots.", ROUTINE, "volve"),
    ("Investigated faulty torque setting on casing tong.", ROUTINE, "volve"),
    ("Circulated well clean and flow checked well.", ROUTINE, "volve"),
    ("Tested production packer from above.", ROUTINE, "volve"),
    ("Waited on handover of well f-14.", ROUTINE, "volve"),
    ("Released liner hanger running tool and circulated out excess cement.", ROUTINE, "volve"),
    ("Circulated btms up to clean hole before POOH to take pressure points.", ROUTINE, "volve"),
    ("Washed/reamed down from 4393 m to 4911 m MD.", ROUTINE, "volve"),
    ("Waited one weather, not able to discharge cuttings to vessel due to bad weather.", ROUTINE, "volve"),
    ("Changed to back-up xceed and drilling jar.", ROUTINE, "volve"),
    ("Performed torque test on drilling jar and xceed.", ROUTINE, "volve"),
    ("Rigged up for cut and thread fishing.", "EVT_FISHING", "volve"),
    ("Drilled 8 1/2\" section from 3,250 m to 3,412 m, ROP 18 m/hr, no problems.", ROUTINE, "authored"),
    ("Made up BHA and RIH to 1,200 m.", ROUTINE, "authored"),
]


# ─── Candidates ────────────────────────────────────────────────────────────
class KeywordModel:
    name, hf_id, params_m = "keyword", "nlp_rules.KEYWORD_EVT", 0

    def predict(self, sents):
        return [classify_event(s) for s in sents]


class PrototypeModel:
    """Embedding + nearest-class-centroid (max cosine over each class's prototypes)."""

    def __init__(self, name, hf_id, device, sentence_transformer=False):
        import torch
        from transformers import AutoModel, AutoTokenizer  # always imported for type narrowing
        self.name, self.hf_id, self.device = name, hf_id, device
        self.torch = torch
        self.tok: AutoTokenizer | None = None
        self.model: AutoModel | None = None
        if sentence_transformer:
            from sentence_transformers import SentenceTransformer
            self.st: SentenceTransformer | None = SentenceTransformer(hf_id, device=device)
            self.params_m = sum(p.numel() for p in self.st.parameters()) / 1e6
        else:
            self.st = None
            self.tok = AutoTokenizer.from_pretrained(hf_id)
            try:
                self.model = AutoModel.from_pretrained(hf_id)
            except (ValueError, OSError) as e:
                if "torch.load" not in str(e) and "safetensors" not in str(e):
                    raise
                # Repo ships only pytorch_model.bin and transformers refuses torch.load on
                # torch<2.6. Load the (trusted, Microsoft) state dict with weights_only=True.
                from huggingface_hub import hf_hub_download
                from transformers import AutoConfig
                self.model = AutoModel.from_config(AutoConfig.from_pretrained(hf_id))
                sd = torch.load(hf_hub_download(hf_id, "pytorch_model.bin"),
                                map_location="cpu", weights_only=True)
                prefix = self.model.base_model_prefix + "."
                sd = {k[len(prefix):] if k.startswith(prefix) else k: v for k, v in sd.items()}
                missing, _ = self.model.load_state_dict(sd, strict=False)
                if len(missing) > 5:
                    raise RuntimeError(f"manual load: {len(missing)} missing keys")
            self.model = self.model.to(device).eval()
            self.params_m = sum(p.numel() for p in self.model.parameters()) / 1e6
        self.labels, protos = [], []
        for evt, phrases in EVENT_PROTOTYPES.items():
            for p in phrases:
                self.labels.append(evt)
                protos.append(p)
        self.proto_emb = self._embed(protos)

    def _embed(self, texts):
        torch = self.torch
        if self.st is not None:
            return self.st.encode(texts, convert_to_tensor=True, normalize_embeddings=True,
                                  batch_size=32, show_progress_bar=False)
        assert self.tok is not None and self.model is not None, "_embed: no tokenizer/model loaded"
        with torch.no_grad():
            enc = self.tok(texts, padding=True, truncation=True, max_length=128,
                           return_tensors="pt").to(self.device)
            out = self.model(**enc).last_hidden_state
            mask = enc["attention_mask"].unsqueeze(-1).float()
            emb = (out * mask).sum(1) / mask.sum(1).clamp(min=1e-6)
            return torch.nn.functional.normalize(emb, dim=-1)

    def class_scores(self, sents):
        """Per sentence: {event_type_id: max cosine over that class's prototypes}."""
        sims = self._embed([expand_abbreviations(s) for s in sents]) @ self.proto_emb.T  # [n, n_protos]
        out = []
        for row in sims:
            best = {}
            for j, evt in enumerate(self.labels):
                v = float(row[j])
                if v > best.get(evt, -9):
                    best[evt] = v
            out.append(best)
        return out 

    @staticmethod
    def decide(scores, margin=0.0):
        """Best hazard class if it beats the routine prototypes by >= margin, else routine."""
        haz = {k: v for k, v in scores.items() if k != ROUTINE}
        top = max(haz, key=lambda k: haz[k])
        return top if haz[top] - scores[ROUTINE] >= margin else ROUTINE

    def predict(self, sents, margin=0.0):
        return [self.decide(sc, margin) for sc in self.class_scores(sents)]


class GlinerModel:
    def __init__(self, device, hf_id="urchade/gliner_medium-v2.1", threshold=0.3):
        from gliner import GLiNER  # type: ignore[import-not-found]
        self.name, self.hf_id, self.threshold = "gliner", hf_id, threshold
        self.model = GLiNER.from_pretrained(hf_id).to(device)
        self.params_m = sum(p.numel() for p in self.model.parameters()) / 1e6
        self.labels = list(GLINER_EVENT_LABELS.keys())

    def predict(self, sents):
        preds = []
        for s in sents:
            ents = self.model.predict_entities(expand_abbreviations(s), self.labels, threshold=self.threshold)
            if not ents:
                preds.append(ROUTINE)
            else:
                top = max(ents, key=lambda e: e["score"])
                preds.append(GLINER_EVENT_LABELS[top["label"]])
        return preds


# ─── Metrics ───────────────────────────────────────────────────────────────
def score(gold, pred):
    per = {}
    for c in CLASSES:
        tp = sum(g == c and p == c for g, p in zip(gold, pred))
        fp = sum(g != c and p == c for g, p in zip(gold, pred))
        fn = sum(g == c and p != c for g, p in zip(gold, pred))
        P = tp / (tp + fp) if tp + fp else 0.0
        R = tp / (tp + fn) if tp + fn else 0.0
        F = 2 * P * R / (P + R) if P + R else 0.0
        per[c] = {"precision": round(P, 3), "recall": round(R, 3), "f1": round(F, 3),
                  "support": sum(g == c for g in gold)}
    present = [c for c in CLASSES if per[c]["support"]]
    hz = [(g, p) for g, p in zip(gold, pred) if g != ROUTINE]
    rt = [(g, p) for g, p in zip(gold, pred) if g == ROUTINE]
    hz_gold_haz = [EVENT_VOCAB["event_types"][g]["hazard"] for g, _ in hz]
    hz_pred_haz = [EVENT_VOCAB["event_types"][p]["hazard"] for _, p in hz]
    return {
        "accuracy": round(sum(g == p for g, p in zip(gold, pred)) / len(gold), 3),
        "macro_f1": round(sum(per[c]["f1"] for c in present) / len(present), 3),
        # event detected at all (any non-routine label) on hazard sentences
        "hazard_detection_recall": round(sum(p != ROUTINE for _, p in hz) / len(hz), 3),
        # right hazard family (mud_loss / stuck_pipe / kick / ...)
        "hazard_family_accuracy": round(sum(a == b for a, b in zip(hz_gold_haz, hz_pred_haz)) / len(hz), 3),
        "routine_false_alarm_rate": round(sum(p != ROUTINE for _, p in rt) / len(rt), 3),
        "per_class": per,
    }


def hybrid(kw_pred, model_pred):
    """Keyword decides when it fires; model fills in when keyword says routine."""
    return [k if k != ROUTINE else m for k, m in zip(kw_pred, model_pred)]


def hybrid_veto(kw_pred, model_pred):
    """As hybrid(), but the model may also veto a keyword hit it judges routine
    (targets keyword traps such as 'kick off plug', 'no tight spots')."""
    return [(ROUTINE if m == ROUTINE else k) if k != ROUTINE else m
            for k, m in zip(kw_pred, model_pred)]


# ─── Margin calibration (dev/test split, no tuning on the reported half) ───
MARGIN_GRID = [round(0.01 * i, 2) for i in range(0, 31)]


def dev_test_split():
    """Deterministic stratified split: alternate sentences of each class into dev / test."""
    seen, dev, test = defaultdict(int), [], []
    for i, (_, g, _) in enumerate(EVAL_SET):
        (dev if seen[g] % 2 == 0 else test).append(i)
        seen[g] += 1
    return dev, test


def calibrate(model, kw_pred_all):
    dev, test = dev_test_split()
    sents = [s for s, _, _ in EVAL_SET]
    gold = [g for _, g, _ in EVAL_SET]
    scores = model.class_scores(sents)
    best = None
    for m in MARGIN_GRID:
        pred = [model.decide(sc, m) for sc in scores]
        f = score([gold[i] for i in dev],
                  hybrid([kw_pred_all[i] for i in dev], [pred[i] for i in dev]))["macro_f1"]
        if best is None or f > best[1]:
            best = (m, f)
    # Precision-constrained operating point (objective fixed before looking at test):
    # smallest margin whose *semantic-only* routine false-alarm rate on dev is <= 10%.
    dev_rt = [i for i in dev if gold[i] == ROUTINE]
    m_prec = MARGIN_GRID[-1]
    for mm in MARGIN_GRID:
        fa = sum(model.decide(scores[i], mm) != ROUTINE for i in dev_rt) / max(len(dev_rt), 1)
        if fa <= 0.10:
            m_prec = mm
            break
    pred_p = [model.decide(sc, m_prec) for sc in scores]
    assert best is not None, "calibrate: no margins evaluated"
    m = best[0]
    pred = [model.decide(sc, m) for sc in scores]
    tg = [gold[i] for i in test]
    return {
        "precision_margin": m_prec,
        "test_hybrid_precision_margin": score(tg, hybrid([kw_pred_all[i] for i in test],
                                                         [pred_p[i] for i in test])),
        "test_standalone_precision_margin": score(tg, [pred_p[i] for i in test]),
        "full_set_hybrid_precision_margin": score(gold, hybrid(kw_pred_all, pred_p)),
        "margin": m, "dev_macro_f1": best[1], "n_dev": len(dev), "n_test": len(test),
        "test_uncalibrated_hybrid": score(tg, hybrid([kw_pred_all[i] for i in test],
                                                     [model.decide(scores[i], 0.0) for i in test])),
        "test_standalone": score(tg, [pred[i] for i in test]),
        "test_hybrid": score(tg, hybrid([kw_pred_all[i] for i in test], [pred[i] for i in test])),
        "test_keyword": score(tg, [kw_pred_all[i] for i in test]),
    }


_MINILM = {}


def operating_curve(results, margins=(0.10, 0.13, 0.16, 0.19, 0.22, 0.25, 0.28)):
    """Semantic-only firing vs margin for MiniLM: recall on hazard sentences, false
    alarms on routine sentences, and firing rate on all real Volve DDR sentences
    (a proxy for how noisy it is on real, mostly-routine reports)."""
    m = _MINILM.get("model")
    if m is None:
        return None
    sents = [s for s, _, _ in EVAL_SET]
    gold = [g for _, g, _ in EVAL_SET]
    sc = m.class_scores(sents)

    def mg(d):
        haz = {k: v for k, v in d.items() if k != ROUTINE}
        return max(haz.values()) - d[ROUTINE]
    pos = [mg(d) for d, g in zip(sc, gold) if g != ROUTINE]
    neg = [mg(d) for d, g in zip(sc, gold) if g == ROUTINE]
    volve = None
    vdir = os.path.join(HERE, "..", "..", "..", "datasets", "volve_data")
    try:
        import re as _re
        import pandas as pd
        df = pd.concat([pd.read_csv(os.path.join(vdir, f)) for f in
                        ("volve_ddrs_train.csv", "volve_ddrs_test.csv")])
        vs = [x.strip() for t in df["output"].fillna("").tolist()
              for x in _re.split(r"(?<=[.;])\s+", str(t)) if len(x.strip()) >= 12]
        volve = [mg(d) for d in m.class_scores(vs)]
    except Exception as e:                            # noqa: BLE001
        print(f"   (Volve corpus unavailable for fire-rate: {e})")
    return [{"margin": t,
             "hazard_recall": sum(v >= t for v in pos) / len(pos),
             "routine_fa": sum(v >= t for v in neg) / len(neg),
             "volve_fire_rate": (sum(v >= t for v in volve) / len(volve)) if volve else None}
            for t in margins]


# ─── Entity-field evaluation: original regex vs unit-aware regex vs + GLiNER ──
# gold: depth_m (first depth), mud_weight_ppg, volume_lost_bbl, formation (None = not stated)
ENTITY_SET = [
    ("Pumped 38m3 LCM pill from 2495m to 2351m.", 2495.0, None, 239.0, None),
    ("Took loss rate at 840m 540 LPM.", 840.0, None, None, None),
    ("While reaming down from 3680m string became stuck momentarily at 3772m and 3842m.", 3680.0, None, None, None),
    ("Pumped and spotted a third 5 m3 LCM pill at TD due to heavy losses of 36 m3/hr.", None, None, 31.4, None),
    ("Bled in LCM mix while drilling ty fm.", None, None, None, "Ty"),
    ("Washed/reamed down from 4393 m to 4911 m MD.", 4393.0, None, None, None),
    ("Finished drilling 22 in hole to 421 ft", 128.3, None, None, None),
    ("Drill 36\" hole from surface to 100'. All material was alluvium (decomposed granite).", 30.5, None, None, "Alluvium"),
    ("Lost 45 bbl to formation at 6,043 ft in Precambrian granite, MW 9.8 ppg.", 1841.9, 9.8, 45.0, "Precambrian Granite"),
    ("Severe losses at 1842 m in Precambrian granite fracture zone, mud density 1.18 SG.", 1842.0, 9.83, None, "Precambrian Granite"),
    ("Tight hole at 1,756 m while tripping out; reamed 1754-1760 m.", 1756.0, None, None, None),
    ("Overpull 40 klbs at 2210 m in Hordaland claystone, MW 1.35 sg.", 2210.0, 11.25, None, "Hordaland"),
    ("Gas-cut mud at shakers, mud weight out reduced from 1.45 to 1.38 SG.", None, 11.5, None, None),
    ("Pit gain of 12 bbl observed while drilling at 3,410 m, flow check positive.", 3410.0, None, 12.0, None),
    ("Drilled 12 1/4\" hole from 2,890 ft to 3,412 ft in the Milford Volcanics, 9.4 ppg WBM.", 880.9, 9.4, None, "Milford Volcanics"),
    ("Partial losses (35 bbl/hr) while drilling at 2,310 m in the Draupne Fm.", 2310.0, None, None, "Draupne"),
    ("Spotted 20 bbl nut plug pill across thief zone at 7,850'.", 2392.7, None, 20.0, None),
    ("Losses of 4 m3 to formation while drilling Utsira sand at 875 m, mud 1.20 sg.", 875.0, 10.0, 25.2, "Utsira"),
    ("Circulated bottoms up at 6,512 ft MD, mud weight 72 pcf.", 1984.9, 9.62, None, None),
    ("Stuck at 3,105 m in the Shetland Group chalk, jarred free.", 3105.0, None, None, "Shetland"),
]


def _close(a, b, tol=0.02):
    if a is None or b is None:
        return a is None and b is None
    return abs(a - b) <= max(0.6, tol * abs(b))


def entity_eval(device, gliner_model=None):
    from units import parse_depths, parse_mud_weight_ppg, parse_volume_bbl, parse_formation
    from nlp_rules import extract_entities

    def regex_old(t):
        r = extract_entities(t, "W", "D", "eval")
        return (r["depth_m"] or None, r["mud_weight_ppg"], r["volume_lost_bbl"] or None,
                None if r["formation_id"] == "Unknown" else r["formation_id"])

    def regex_units(t):
        d = parse_depths(t)
        return (d[0][0] if d else None, parse_mud_weight_ppg(t), parse_volume_bbl(t), parse_formation(t))

    labels = {"depth": 0, "mud weight": 1, "fluid volume": 2, "geological formation": 3}

    def with_gliner(t):
        assert gliner_model is not None, "with_gliner called but gliner_model is None"
        base = list(regex_units(t))
        ents = gliner_model.predict_entities(t, list(labels), threshold=0.4)
        for e in sorted(ents, key=lambda e: -e["score"]):
            k = labels[e["label"]]
            if base[k] is not None:
                continue                                    # regex wins when present
            span = e["text"]
            if k == 0:
                d = parse_depths(span)
                base[k] = d[0][0] if d else None
            elif k == 1:
                base[k] = parse_mud_weight_ppg(span)
            elif k == 2:
                base[k] = parse_volume_bbl(span)
            else:
                base[k] = span.strip().title()
        return tuple(base)

    fields = ["depth_m", "mud_weight_ppg", "volume_lost_bbl", "formation"]
    systems = {"regex_original": regex_old, "regex_unit_aware": regex_units}
    if gliner_model is not None:
        systems["unit_aware+gliner"] = with_gliner
    res = {}
    for name, fn in systems.items():
        correct = defaultdict(int)
        t0 = time.time()
        for t, *gold in ENTITY_SET:
            pred = fn(t)
            for i, f in enumerate(fields):
                g, p = gold[i], pred[i]
                if f == "formation":
                    ok = (g is None and p is None) or (g is not None and p is not None
                                                       and str(g).lower() == str(p).lower())
                else:
                    ok = _close(p, g)
                correct[f] += ok
        n = len(ENTITY_SET)
        res[name] = {f: round(correct[f] / n, 3) for f in fields}
        res[name]["all_fields"] = round(sum(correct.values()) / (n * len(fields)), 3)
        res[name]["ms_per_sentence"] = round((time.time() - t0) * 1000 / n, 2)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None,
                    help="default: outputs/model_selection.json, or outputs/model_selection_partial.json "
                         "if any candidate was skipped (so the committed full table is not overwritten)")
    ap.add_argument("--skip", nargs="*", default=[], help="candidate names to skip")
    args = ap.parse_args()

    try:
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        device = "cpu"

    sents = [s for s, _, _ in EVAL_SET]
    gold = [g for _, g, _ in EVAL_SET]
    print(f"Eval set: {len(sents)} sentences "
          f"({sum(o == 'volve' for *_, o in EVAL_SET)} Volve, "
          f"{sum(o == 'authored' for *_, o in EVAL_SET)} authored), "
          f"{len(set(gold))} classes, device={device}")

    builders = [
        ("keyword", lambda: KeywordModel()),
        ("bert",    lambda: PrototypeModel("bert", "bert-base-uncased", device)),
        ("roberta", lambda: PrototypeModel("roberta", "roberta-base", device)),
        ("deberta", lambda: PrototypeModel("deberta", "microsoft/deberta-v3-base", device)),
        ("minilm",  lambda: PrototypeModel("minilm", "sentence-transformers/all-MiniLM-L6-v2",
                                           device, sentence_transformer=True)),
        ("gliner",  lambda: GlinerModel(device)),
    ]
    results, kw_pred, gliner_obj = {}, None, None
    for name, build in builders:
        if name in args.skip:
            continue
        print(f"\n── {name}")
        try:
            t0 = time.time()
            m = build()
            load_s = time.time() - t0
            m.predict(sents[:2])                     # warm-up
            t0 = time.time()
            pred = m.predict(sents)
            ms = (time.time() - t0) * 1000 / len(sents)
        except Exception as e:                       # report, keep going
            if name in ("gliner", "deberta"):
                hint = "gliner==0.2.30" if name == "gliner" else "sentencepiece==0.2.0"
                print(f"   SKIPPED (optional eval-only candidate; `pip install {hint}` to include): "
                      f"{type(e).__name__}: {str(e)[:120]}")
                results[name] = {"skipped": f"optional dependency missing ({hint})"}
            else:
                print(f"   FAILED: {e}")
                results[name] = {"error": str(e)}
            continue
        if name == "keyword":
            kw_pred = pred
        r = {"hf_id": m.hf_id, "params_m": round(m.params_m, 1),
             "load_s": round(load_s, 1), "ms_per_sentence": round(ms, 2),
             "standalone": score(gold, pred), "predictions": pred}
        if kw_pred is not None and name != "keyword":
            r["hybrid_with_keyword"] = score(gold, hybrid(kw_pred, pred))
            r["hybrid_with_keyword_veto"] = score(gold, hybrid_veto(kw_pred, pred))
        if hasattr(m, "class_scores") and kw_pred is not None:
            r["calibrated"] = calibrate(m, kw_pred)
        if name == "gliner":
            gliner_obj = m.model
        if name == "minilm":
            _MINILM["model"] = m
        results[name] = r
        s = r["standalone"]
        line = (f"   standalone: macroF1={s['macro_f1']:.3f} acc={s['accuracy']:.3f} "
                f"detect={s['hazard_detection_recall']:.3f} family={s['hazard_family_accuracy']:.3f} "
                f"routineFA={s['routine_false_alarm_rate']:.3f}  ({ms:.1f} ms/sent)")
        print(line)
        if "hybrid_with_keyword" in r:
            h = r["hybrid_with_keyword"]
            print(f"   +keyword  : macroF1={h['macro_f1']:.3f} acc={h['accuracy']:.3f} "
                  f"detect={h['hazard_detection_recall']:.3f} family={h['hazard_family_accuracy']:.3f} "
                  f"routineFA={h['routine_false_alarm_rate']:.3f}")
            v = r["hybrid_with_keyword_veto"]
            print(f"   +kw veto  : macroF1={v['macro_f1']:.3f} acc={v['accuracy']:.3f} "
                  f"detect={v['hazard_detection_recall']:.3f} family={v['hazard_family_accuracy']:.3f} "
                  f"routineFA={v['routine_false_alarm_rate']:.3f}")

    # Summary table
    print("\n" + "=" * 96)
    print(f"{'model':9} {'params':>7} {'ms/s':>6} | {'macroF1':>7} {'detect':>6} {'family':>6} {'rFA':>5} "
          f"| hybrid: {'macroF1':>7} {'detect':>6} {'family':>6} {'rFA':>5}")
    for name, r in results.items():
        if "error" in r or "skipped" in r:
            print(f"{name:9} {'ERROR ' + r['error'][:70] if 'error' in r else 'skipped: ' + r['skipped']}")
            continue
        s = r["standalone"]
        h = r.get("hybrid_with_keyword", s)
        print(f"{name:9} {r['params_m']:>6}M {r['ms_per_sentence']:>6} | {s['macro_f1']:>7} "
              f"{s['hazard_detection_recall']:>6} {s['hazard_family_accuracy']:>6} {s['routine_false_alarm_rate']:>5} "
              f"| {'':8}{h['macro_f1']:>7} {h['hazard_detection_recall']:>6} "
              f"{h['hazard_family_accuracy']:>6} {h['routine_false_alarm_rate']:>5}")

    print("\nMargin-calibrated prototype classifiers (margin tuned on dev half, reported on test half):")
    print(f"{'model':9} {'margin':>6} | test: {'kw F1':>6} {'hyb F1 m=0':>10} {'hyb F1':>7} {'detect':>6} {'family':>6} {'rFA':>5}")
    for name, r in results.items():
        c = r.get("calibrated") if isinstance(r, dict) else None
        if not c:
            continue
        h = c["test_hybrid"]
        print(f"{name:9} {c['margin']:>6} | {'':6}{c['test_keyword']['macro_f1']:>6} "
              f"{c['test_uncalibrated_hybrid']['macro_f1']:>10} {h['macro_f1']:>7} "
              f"{h['hazard_detection_recall']:>6} {h['hazard_family_accuracy']:>6} {h['routine_false_alarm_rate']:>5}")
        hp = c["test_hybrid_precision_margin"]
        print(f"{'':9} {c['precision_margin']:>6} | precision-constrained (dev semantic rFA<=10%): "
              f"hyb F1={hp['macro_f1']} detect={hp['hazard_detection_recall']} "
              f"family={hp['hazard_family_accuracy']} rFA={hp['routine_false_alarm_rate']}")

    curve = operating_curve(results)
    if curve:
        print("\nMiniLM deployment operating curve (semantic-only firing; full screening set + Volve corpus):")
        print(f"  {'margin':>6} {'hazard recall':>13} {'routine FA':>10} {'Volve fire-rate':>15}")
        for row in curve:
            vf = f"{row['volve_fire_rate']:.3f}" if row["volve_fire_rate"] is not None else "n/a"
            print(f"  {row['margin']:>6} {row['hazard_recall']:>13.3f} {row['routine_fa']:>10.3f} {vf:>15}")

    print(f"\nEntity fields (exact or within 2 pct; None must stay None), n={len(ENTITY_SET)}:")
    ent = entity_eval(device, gliner_obj)
    for k, v in ent.items():
        print(f"  {k:20} " + "  ".join(f"{f}={v[f]:.2f}" for f in
                                         ["depth_m", "mud_weight_ppg", "volume_lost_bbl", "formation", "all_fields"])
              + f"  ({v['ms_per_sentence']} ms/sent)")

    if args.out is None:
        partial = any("skipped" in r or "error" in r for r in results.values()) or bool(args.skip)
        args.out = os.path.join(HERE, "outputs",
                                "model_selection_partial.json" if partial else "model_selection.json")
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"device": device, "n_sentences": len(sents),
                   "eval_set": [{"sentence": s, "gold": g, "origin": o} for s, g, o in EVAL_SET],
                   "results": results, "entity_eval": ent, "minilm_operating_curve": curve,
                   "entity_set": [{"sentence": t, "depth_m": d, "mud_weight_ppg": w,
                                   "volume_lost_bbl": v, "formation": f} for t, d, w, v, f in ENTITY_SET]},
                  f, indent=2)
    print(f"\nSaved -> {args.out}")


if __name__ == "__main__":
    main()
