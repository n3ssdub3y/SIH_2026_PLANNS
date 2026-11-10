"""
Module 1 — hybrid NLP engine (keyword/regex + MiniLM semantic event typing).

Augments, never replaces, the deterministic rules in nlp_rules.py:

  1. Keyword pass    nlp_rules.matched_keyword() per sentence (high precision),
                     plus negation ("no tight spots") and known keyword traps
                     ("fishing neck", "kick off plug", "torque test").
  2. Semantic pass   all-MiniLM-L6-v2 sentence embedding, cosine against the
                     per-class prototypes in event_prototypes.py. A semantic-only
                     event is accepted when the best hazard class beats the
                     routine prototypes by >= SEMANTIC_MARGIN (0.19). This is
                     the precision-oriented point of the operating curve that
                     eval_model_selection.py prints (screening-set recall ~0.61,
                     0 routine false alarms, fires on ~2.5% of Volve sentences).
                     Real DDRs are mostly routine lines, so precision is favoured;
                     the curve was inspected with the full screening set visible,
                     so a gold set is still needed for an unbiased estimate.
  3. Fields          units.py parsers (ft->m, SG/pcf->ppg, m3->bbl) on the
                     event's own sentence, then its neighbours, then the report
                     header (e.g. "Measured Depth (ft): 128").

The only language model in this pipeline is all-MiniLM-L6-v2 (22.7M params;
the same model Modules 4/5 already use). It runs on the GPU if torch sees one,
otherwise on the CPU (~9 s for a 93-page report, small next to OCR time).
Why MiniLM: see eval_model_selection.py and Walkthrough.md. It beat zero-shot
BERT, RoBERTa, DeBERTa-v3 and GLiNER on event typing; GLiNER also added nothing
over the unit-aware regex for entity fields, so GLiNER is not part of the
pipeline (it is only an optional candidate in the evaluation script).

Output records use exactly nlp_rules.EVENT_RECORD_KEYS (the events.jsonl
schema). Provenance goes in a parallel `evidence` list, not in the records.
"""
import re
from datetime import datetime

from nlp_rules import EVENT_VOCAB, EVENT_RECORD_KEYS, matched_keyword
from event_prototypes import EVENT_PROTOTYPES, expand_abbreviations
from units import (parse_depths, parse_mud_weight_ppg, parse_volume_bbl,
                   parse_npt_hours, sum_npt_hours, parse_formation, FT_TO_M)

ROUTINE = "EVT_ROUTINE_DRILLING"
SEMANTIC_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
SEMANTIC_MARGIN = 0.19

# Keyword hits that are not events in context (seen in Volve / Utah FORGE text).
KEYWORD_TRAPS = [
    re.compile(p, re.I) for p in (
        r"fishing\s+neck", r"kick\s*-?\s*off", r"torque\s+(test|setting|wrench|gauge|tong|sub|motor)",
        r"(high|low)\s+torque\s+(motor|setting)",
        r"\btorqued\b", r"torque\s*turn", r"make\s*-?\s*up\s+torque", r"kick\s+pad",
        r"\btorque\s+(all|each|every|the)\b", r"junk\s+basket\b(?!.*(recovered|retrieved|fish))",
        r"(drilling|hydraulic|mechanical)\s+jar\b", r"jar\s+(test|and)", r"shut\s*-?\s*in\s+pressure\s+build",
        r"stuck\s+(lock|adjustable|sub)", r"lcm\s+(tank|hopper|inventory)",
        r"well\s+control\s+(drill|equipment|training|certificate)", r"(bop|well)\s+test",
    )
]
NEGATION = re.compile(r"\b(no|not|nil|without|zero|0)\b(?:\s+\w+){0,3}\s*$", re.I)
# Sentence-level negation for semantic-only hits ("no losses", "without overpull").
SEM_NEGATION = re.compile(
    r"(no|not|nil|without|zero)\s+(\w+\s+){0,2}(loss(es)?|returns? lost|gas|kick|influx|flow|problems?|"
    r"issues?|incidents?|accidents?|tight|drag|overpull|torque|fill|cavings|anomal\w*)", re.I)
BOILERPLATE = re.compile(
    r"^(safety summary|first aid|lost time incidents|days since lti|meetings/drills|equipment problems|"
    r"bulk inventory|drill pipe inventory|shaker no|screen sizes|weather information|sky condition|"
    r"air temperature|wind speed|printed:|pers/hrs|jets:)", re.I)

DATE_FORMATS = ["%d-%b-%y", "%d-%b-%Y", "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d.%m.%Y",
                "%B %d, %Y", "%B %d,%Y", "%b %d, %Y", "%d %B %Y", "%d %b %Y"]
_DATE_TOKEN = (r"(\d{4}-\d{2}-\d{2}|\d{1,2}-[A-Za-z]{3}-\d{2,4}|\d{1,2}[/.]\d{1,2}[/.]\d{4}|"
               r"[A-Z][a-z]+ \d{1,2},\s?\d{4}|\d{1,2} [A-Z][a-z]+ \d{4})")


def to_iso(s):
    s = s.strip().rstrip(".")
    for f in DATE_FORMATS:
        try:
            return datetime.strptime(s, f).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


# ─── Report header parsing ─────────────────────────────────────────────────
def _grab(rx, text, flags=re.I):
    m = re.search(rx, text, flags)
    return m.group(1).strip(" .:-") if m else None


def parse_header(text):
    h = {}
    h["well_id"] = _grab(r"Well\s*ID\s*[:.]\s*(.+?)(?:\s{2,}|\s+Well\s*Name|\n|$)", text)
    h["well_name"] = _grab(r"Well\s*Name\s*[:.]\s*([A-Za-z0-9][\w\-/\. ]{0,30}?)(?:\s{2,}|\s+[A-Z][a-z]+:|\n|$)", text)
    if not h["well_id"]:
        h["well_id"] = _grab(r"\bWell(?:bore)?\s*[:.]\s*([A-Z0-9][\w\-/\. ]{1,30}?)(?:\s{2,}|\s+[A-Z][a-z]+\s*:|\n|$)",
                             text, 0)
    h["operator"] = _grab(r"Operator\s*:\s*([A-Za-z][\w&,\.\- ]{2,50}?)(?:\s{2,}|\s+Rig\s*:|\n|$)", text)
    h["field"] = _grab(r"Field\s*:\s*([A-Za-z0-9][\w\- ]{1,30}?)(?:\s{2,}|\s+[A-Z][a-z]+\s*:|\n|$)", text)
    h["rig"] = _grab(r"\bRig\s*:\s*([A-Za-z0-9][\w#\- ]{1,30}?)(?:\s{2,}|\s+[A-Z][a-z]+\s*(?:Date)?\s*:|\n|$)", text)
    county = _grab(r"County\s*:\s*([A-Za-z ]{2,30}?)(?:\s+State|\n|$)", text)
    state = _grab(r"State\s*:\s*([A-Z]{2})\b", text, 0)
    if county or state:
        h["location"] = ", ".join(x for x in (county and f"{county} County", state) if x)
    sd = _grab(r"Spud\s*Date\s*:\s*" + _DATE_TOKEN, text)
    h["spud_date"] = to_iso(sd) if sd else None
    rd = (_grab(r"Report\s*(?:For|Date)\s*:?\s*" + _DATE_TOKEN, text)
          or _grab(r"\bDate\s*:\s*" + _DATE_TOKEN, text))
    h["report_date"] = to_iso(rd) if rd else None
    md = re.search(r"Measured\s*Depth\s*\((ft|m)\)\s*:\s*([\d,\.]+)", text, re.I) \
        or re.search(r"\b(?:MD|Depth)\s*\((ft|m)\)\s*:\s*([\d,\.]+)", text, re.I)
    if md:
        try:
            v = float(md.group(2).replace(",", ""))
            h["md_m"] = round(v * FT_TO_M, 1) if md.group(1).lower() == "ft" else v
            h["md_ft"] = v if md.group(1).lower() == "ft" else None
        except ValueError:
            pass
    h["mud_weight_ppg"] = parse_mud_weight_ppg(
        _grab(r"(?:MW|Mud\s*Weight|Density)\s*[:=]\s*([\d\.,]+\s*(?:ppg|sg|pcf|lb/gal))", text) or "")
    return {k: v for k, v in h.items() if v}


# ─── Segmentation ──────────────────────────────────────────────────────────
_REPORT_KEY = re.compile(r"Report\s*(?:For|Date)\s*:?\s*" + _DATE_TOKEN + r"|\bDate\s*:\s*" + _DATE_TOKEN, re.I)


def segment_document(pages):
    """Group pages into report units by their header date. Pages without a header
    continue the previous report; a document with no headers -> one unit per page."""
    keys = []
    for p in pages:
        m = _REPORT_KEY.search(p[:600])
        keys.append(to_iso(m.group(1) or m.group(2)) if m else None)
    if not any(keys):
        return [{"pages": [i], "text": t} for i, t in enumerate(pages)]
    units = []
    for i, (t, k) in enumerate(zip(pages, keys)):
        if units and (k is None or k == units[-1]["key"]):
            units[-1]["pages"].append(i)
            units[-1]["text"] += "\n" + t
        else:
            units.append({"key": k, "pages": [i], "text": t})
    return units


def _norm_line(ln):
    return re.sub(r"\s+", " ", re.sub(r"[\d\W_]+", " ", ln.lower())).strip()


def template_lines(pages, min_pages=3, min_frac=0.3):
    """Normalised lines that recur across pages (form labels, table headers, page
    headers/footers). Only meaningful for multi-page documents."""
    if len(pages) < min_pages:
        return set()
    cnt = {}
    for p in pages:
        for k in {_norm_line(ln) for ln in p.splitlines() if ln.strip()}:
            if k:
                cnt[k] = cnt.get(k, 0) + 1
    need = max(min_pages, int(min_frac * len(pages)))
    return {k for k, c in cnt.items() if c >= need}


def is_heading(ln):
    """Form labels ("Slow Circulation Data:") and capitalised table-header rows."""
    s = ln.strip()
    if s.endswith(":") and len(s) < 60:
        return True
    if len(re.findall(r"\([^)]{1,12}\)", s)) >= 3:       # "Depth (ft) ROP (ft/hr) WOB (lbs) ..."
        return True
    toks = re.findall(r"[A-Za-z][A-Za-z.\-/]*", s)
    if len(toks) >= 5 and not s.endswith("."):
        caps = sum(t[0].isupper() for t in toks)
        if caps / len(toks) >= 0.75:
            return True
    return False


_SENT_SPLIT = re.compile(r"(?<=[.;!?])\s+(?=[A-Z0-9\-\"(])")
_TIME_ROW = re.compile(r"^\d{1,2}:\d{2}\s+\d{1,2}:\d{2}\s+[\d.]+\s+\S+\s*")


def split_sentences(text, template=frozenset()):
    """Rule-based splitter (Punkt fragments technical DDR text — Dimeski & Rahimi 2022).
    Recurring template lines and headings are dropped first."""
    lines = [ln.strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln and _norm_line(ln) not in template and not is_heading(ln)]
    merged = []
    for ln in lines:
        if not ln:
            continue
        ln = re.sub(r"^[-•*]\s*", "", ln)
        if merged and (merged[-1][-1:] in ",&/" or (ln[:1].islower() and merged[-1][-1:] not in ".;:!?")):
            merged[-1] += " " + ln
        else:
            merged.append(ln)
    out = []
    for ln in merged:
        if BOILERPLATE.match(ln):
            continue
        ln = _TIME_ROW.sub("", ln)          # "6:00 9:00 3.00 128RIGU  Pre-Spud ..." -> description
        for s in _SENT_SPLIT.split(ln):
            s = s.strip()
            alpha = sum(c.isalpha() for c in s)
            if len(s) >= 12 and alpha >= 0.45 * len(s):
                out.append(s)
    return out


def _keyword_hit(sentence):
    """Keyword pass with negation + trap handling. Returns (keyword, evt) or None."""
    hit = matched_keyword(sentence)
    if not hit:
        return None
    kw, _ = hit
    low = sentence.lower()
    pos = low.find(kw)
    end = pos + len(kw)
    for t in KEYWORD_TRAPS:                        # trap must overlap the matched keyword
        for m in t.finditer(sentence):
            if m.start() <= end and pos <= m.end():
                return None
    if NEGATION.search(low[:pos]):
        return None
    return hit


# ─── Engine ────────────────────────────────────────────────────────────────
class HybridEngine:
    def __init__(self, load_models=True, log=None, device=None, margin=SEMANTIC_MARGIN):
        self.log = log or (lambda m: None)
        self.margin = margin
        self.st = None
        self.device = "n/a"
        self.load_error = None
        if load_models:
            try:
                import torch
                from sentence_transformers import SentenceTransformer
                self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
                self.st = SentenceTransformer(SEMANTIC_MODEL, device=self.device)
                self._labels, protos = [], []
                for evt, phrases in EVENT_PROTOTYPES.items():
                    for p in phrases:
                        self._labels.append(evt)
                        protos.append(p)
                self._proto = self.st.encode(protos, convert_to_tensor=True,
                                             normalize_embeddings=True, show_progress_bar=False)
                self.log(f"[nlp_engine] {SEMANTIC_MODEL} loaded on {self.device}")
            except Exception as e:                    # noqa: BLE001
                self.st = None
                self.load_error = f"{type(e).__name__}: {e}"
                self.log(f"[nlp_engine] semantic model unavailable, keyword-only: {self.load_error}")

    def model_info(self):
        return {
            "mode": "hybrid" if self.st is not None else "keyword",
            "keyword_rules": f"nlp_rules.KEYWORD_EVT ({len(EVENT_VOCAB['event_types'])} classes) "
                             f"+ negation/trap filters",
            "semantic_model": SEMANTIC_MODEL if self.st is not None else None,
            "semantic_margin": self.margin if self.st is not None else None,
            "field_extraction": "unit-aware regex (units.py)",
            "device": self.device if self.st is not None else "cpu",
            "load_error": self.load_error,
        }

    # -- sentence classification ---------------------------------------------
    def _semantic(self, sents):
        if self.st is None or not sents:
            return [None] * len(sents)
        emb = self.st.encode([expand_abbreviations(s) for s in sents], convert_to_tensor=True, normalize_embeddings=True,
                             batch_size=64, show_progress_bar=False)
        sims = (emb @ self._proto.T).cpu().tolist()
        out = []
        for row in sims:
            best = {}
            for j, evt in enumerate(self._labels):
                if row[j] > best.get(evt, -9):
                    best[evt] = row[j]
            haz = {k: v for k, v in best.items() if k != ROUTINE}
            top = max(haz, key=lambda k: haz[k])
            out.append({"top": top, "sim": round(haz[top], 4),
                        "margin": round(haz[top] - best[ROUTINE], 4)})
        return out

    def classify_sentences(self, sents):
        """[(event_type_id, method, info)] — method in keyword|semantic|both|routine."""
        sem = self._semantic(sents)
        res = []
        for s, sm in zip(sents, sem):
            kw = _keyword_hit(s)
            sem_ok = sm is not None and sm["margin"] >= self.margin
            if kw and kw[1] != ROUTINE:
                agree = sem_ok and sm["top"] == kw[1]
                res.append((kw[1], "both" if agree else "keyword",
                            {"keyword": kw[0], "semantic": sm}))
            elif sem_ok and not SEM_NEGATION.search(s):
                res.append((sm["top"], "semantic", {"keyword": None, "semantic": sm}))
            else:
                res.append((ROUTINE, "routine", {"keyword": None, "semantic": sm}))
        return res

    @staticmethod
    def _confidence(method, info):
        if method == "both":
            return 0.92
        if method == "keyword":
            return 0.85
        if method == "semantic":
            m = info["semantic"]["margin"]
            return round(min(0.80, 0.55 + (m - SEMANTIC_MARGIN) * 1.25), 2)
        return 0.95

    # -- one report unit -----------------------------------------------------
    def _extract_unit(self, text, well_id, date, source, header, template=frozenset()):
        sents = split_sentences(text, template)
        cls = self.classify_sentences(sents)
        unit_fm = parse_formation(text)
        best = {}                                     # evt -> (conf, idx, method, info)
        for i, (evt, method, info) in enumerate(cls):
            if evt == ROUTINE:
                continue
            c = self._confidence(method, info)
            if evt not in best or c > best[evt][0]:
                best[evt] = (c, i, method, info)
        records, evidence = [], []
        for evt, (conf, i, method, info) in sorted(best.items(), key=lambda kv: kv[1][1]):
            s = sents[i]
            ctx = " ".join(sents[max(0, i - 1):i + 2])
            d = parse_depths(s) or parse_depths(ctx)
            depth = d[0][0] if d else header.get("md_m", 0.0)
            vol = parse_volume_bbl(s) or 0.0
            npt = parse_npt_hours(s) or parse_npt_hours(ctx) or 0.0
            info_v = EVENT_VOCAB["event_types"][evt]
            rec = dict(zip(EVENT_RECORD_KEYS, (
                well_id, f"{well_id}_{date}_{evt}", date, float(depth or 0.0),
                parse_formation(s) or unit_fm or "Unknown",
                parse_mud_weight_ppg(s) or header.get("mud_weight_ppg"),
                float(npt), float(vol), evt, info_v["hazard"], info_v["severity"], source,
                source == "synthetic", conf, (s if len(s) >= 120 else ctx)[:400],
            )))
            records.append(rec)
            evidence.append({"method": method, "sentence": s, "keyword": info.get("keyword"),
                             "semantic": info.get("semantic")})
        if not records:
            # Prefer the report's own narrative ("Current Operations: ..."), then the
            # first sentence that is not a "Label: value" form field.
            co = re.search(r"Current\s+Operations?\s*:\s*(.+(?:\n(?![A-Z][\w /()]{2,30}:).+){0,2})", text)
            first = (re.sub(r"\s+", " ", co.group(1)).strip() if co else None) or next(
                (x for x in sents if len(x) > 25 and not re.match(r"^[\w /().#-]{2,30}:", x)),
                sents[0] if sents else text[:200])
            rec = dict(zip(EVENT_RECORD_KEYS, (
                well_id, f"{well_id}_{date}_{ROUTINE}", date, float(header.get("md_m", 0.0)),
                unit_fm or "Unknown", header.get("mud_weight_ppg"), float(sum_npt_hours(text)), 0.0, ROUTINE,
                "none", "none", source, source == "synthetic", 0.95, first[:400],
            )))
            records.append(rec)
            evidence.append({"method": "routine", "sentence": first, "keyword": None, "semantic": None})
        return records, evidence, len(sents)

    def extract_report(self, text, well_id, date, source):
        """Single already-segmented report (used by p1_full_pipeline --nlp hybrid)."""
        header = parse_header(text)
        recs, ev, _ = self._extract_unit(text, well_id, date, source, header)
        return {"records": recs, "evidence": ev}

    # -- whole uploaded document ---------------------------------------------
    def extract_document(self, pages, default_well="UPLOAD", source="uploaded_pdf_ocr", progress=None):
        progress = progress or (lambda kind, **kw: None)
        units = segment_document(pages)
        template = template_lines(pages)
        doc_header = parse_header("\n".join(pages[:2]))
        well_id = doc_header.get("well_id") or doc_header.get("well_name") or default_well
        info = self.model_info()
        progress("log", cls="info",
                 msg=f"[NLP]     Hybrid engine: keyword/regex + "
                     f"{info['semantic_model'] or 'NO semantic model'}"
                     + (f" (margin {self.margin}) on {info['device']}" if info["semantic_model"] else ""))
        progress("log", cls="ok",
                 msg=f"[EXTRACT] Segmented {len(pages)} pages -> {len(units)} report(s); well_id={well_id}")
        progress("units", n=len(units))
        records, evidence, dates, mds, n_sent = [], [], [], [], 0
        for k, u in enumerate(units, 1):
            h = parse_header(u["text"])
            date = h.get("report_date") or u.get("key") or "UNKNOWN"
            if date != "UNKNOWN":
                dates.append(date)
            if h.get("md_m"):
                mds.append((h["md_m"], h.get("md_ft")))
            recs, ev, ns = self._extract_unit(u["text"], well_id, date, source, h, template)
            n_sent += ns
            records += recs
            evidence += ev
            ents = []
            for r, e in zip(recs, ev):
                if r["hazard"] == "none":
                    continue
                ents.append({"tag": "EVENT", "cls": "tag-event", "val": r["event_type_id"], "conf": r["confidence"]})
                ents.append({"tag": "HAZARD", "cls": "tag-hazard", "val": r["hazard"], "conf": r["confidence"]})
                if r["depth_m"]:
                    ents.append({"tag": "DEPTH", "cls": "tag-depth", "val": f"{r['depth_m']:,.1f} m", "conf": None})
                if r["formation_id"] != "Unknown":
                    ents.append({"tag": "FORM.", "cls": "tag-form", "val": r["formation_id"], "conf": None})
                if r["mud_weight_ppg"]:
                    ents.append({"tag": "MUD WT", "cls": "tag-mw", "val": f"{r['mud_weight_ppg']} ppg", "conf": None})
                if r["npt_hours"]:
                    ents.append({"tag": "NPT", "cls": "tag-npt", "val": f"{r['npt_hours']} h", "conf": None})
                progress("log", cls="ok",
                         msg=f"[NLP]     {date}: {r['event_type_id']} @ depth_m={r['depth_m']:.1f} "
                             f"({e['method']}, conf {r['confidence']:.2f})")
            progress("unit", i=k, n=len(units), entities=ents)
        n_haz = sum(r["hazard"] != "none" for r in records)
        progress("log", cls="ok",
                 msg=f"[NLP]     {n_sent} sentences classified -> {n_haz} hazard events, "
                     f"{len(records) - n_haz} routine reports")
        md_max = max(mds, key=lambda x: x[0]) if mds else (None, None)
        well = {
            "well_id": well_id, "well_name": doc_header.get("well_name"),
            "operator": doc_header.get("operator"), "field": doc_header.get("field"),
            "rig": doc_header.get("rig"), "location": doc_header.get("location"),
            "spud_date": doc_header.get("spud_date"),
            "first_report_date": min(dates) if dates else None,
            "last_report_date": max(dates) if dates else None,
            "max_md_m": md_max[0], "max_md_ft": md_max[1],
        }
        return {"records": records, "evidence": evidence, "well": well,
                "n_units": len(units), "n_sentences": n_sent, "model_info": info}
