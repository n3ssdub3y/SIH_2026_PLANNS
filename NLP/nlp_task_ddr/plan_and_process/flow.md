# NWIS-Sentinel — Full Technical Deep-Dive & Team Working Guide
### For explaining the plan to your team: architecture, tech stack, datasets, NLP→numeric pipeline, similarity math, data format, and how to work in Antigravity

---

# PART A — THE WHOLE ARCHITECTURE, RESTATED FOR A TEAM BRIEFING

Before the deep technical detail, here is the one picture to draw on a whiteboard when you explain this to your team. Everything below expands one box at a time.

```
 ┌───────────────────────┐        ┌──────────────────────────┐
 │  HISTORICAL DATA        │        │   LIVE DATA (simulated      │
 │  (reports, DDRs,         │        │   eRTMAC-style stream)       │
 │  well logs — TEXT +       │        │   (telemetry — NUMBERS)       │
 │  NUMBERS, from the past)   │        └──────────────┬───────────────┘
 └────────────┬────────────┘                       │
              ▼                                    ▼
   ┌─────────────────────┐                ┌──────────────────────┐
   │   NLP PIPELINE          │                │  LIVE FEATURE ENGINE    │
   │  (text → structured,     │                │ (numbers → same "event   │
   │   numeric event data)     │                │  language" as history)    │
   └─────────┬────────────┘                └────────────┬───────────┘
             │                                            │
             ▼                                            │
   ┌─────────────────────────┐                            │
   │ HAZARD-SPECIFIC             │                            │
   │ SIMILARITY ENGINE             │◄───────────────────────────┘
   │ (which historical wells       │
   │  actually compare to NOW)       │
   └─────────┬───────────────────┘
             ▼
   ┌─────────────────────────────┐
   │ SEQUENCE MATCHING              │
   │ (does the CURRENT event         │
   │  sequence resemble a               │
   │  HISTORICAL one?)                    │
   └─────────┬───────────────────────┘
             ▼
   ┌───────────────────────────────────┐
   │ KNOWLEDGE GRAPH + GraphRAG + LLM      │
   │ (stores everything, retrieves the       │
   │  right evidence, writes an honest,        │
   │  citation-grounded, uncertainty-aware       │
   │  briefing for the engineer)                   │
   └─────────┬─────────────────────────────────┘
             ▼
      ENGINEER DASHBOARD (depth-synced playback,
      analog panel, briefing text)
             │
             ▼
      ENGINEER FEEDBACK → loops back into the
      Similarity Engine's weights
```

**The one sentence to say out loud to your team:** *"We turn both old reports and today's live numbers into the same 'language' of events, then we ask two questions — which old wells are actually comparable to this one right now (for this specific risk), and does today's pattern match a sequence that has played out before — and finally we let an LLM explain the evidence honestly, including when the evidence disagrees with itself."*

---

# PART B — FULL TECH STACK, MODULE BY MODULE

| Module | What it does | Core tech | Why this choice |
|---|---|---|---|
| **Data ingestion (historical)** | Load reports/logs into the pipeline | Python, `pandas`, `PyPDF2`/`pdfplumber` (if PDFs), plain text loaders | Universal, fast to prototype, no licensing cost |
| **NLP pipeline (P1)** | Text → structured events | `spaCy` (fast baseline NER), HuggingFace `transformers` (fine-tuned NER/relation model), `sentence-transformers` (embeddings) | Industry-standard, well-documented, free, runs on modest hardware |
| **Live telemetry simulator (P3-adjacent)** | Replays historical numeric drilling data as a "live" stream | Python generator/`asyncio`, simple WebSocket (`FastAPI` + `websockets`) or just a polling REST endpoint | Cheapest way to convincingly fake "real-time eRTMAC" for a demo |
| **Similarity engine (P2)** | Hazard-specific well similarity | `numpy`, `scipy` (distance functions), `scikit-learn` (normalization, optional learned weights) | Transparent, explainable math — no black box needed |
| **Sequence matching (P3)** | Match live event sequence to historical ones | `fastdtw` or `dtaidistance` (DTW), or a custom Needleman-Wunsch/edit-distance implementation for symbolic sequences | These are proven, well-understood algorithms — not deep learning, so fast to build and easy to explain to judges |
| **Precursor/anomaly detection (P3)** | Flag "something's changing" in live telemetry | Rolling z-score / CUSUM (statistical, fast) as the baseline; optional autoencoder (`PyTorch`/`Keras`) if time allows | Statistical methods are enough for a credible hackathon demo; deep learning is a stretch goal, not a requirement |
| **Knowledge Graph (P4)** | Stores wells/events/relations | `networkx` (in-memory graph, Python) | Zero setup, enough for a prototype, easy to inspect/debug |
| **GraphRAG retrieval (P4)** | Fetch the right evidence for a query | Custom pre-filter (via similarity engine's analog list) + `sentence-transformers` embeddings for fine-grained match within that filtered set | This is your actual novelty — plain vector-DB RAG (e.g. FAISS/Chroma) alone is NOT enough, see Part F |
| **LLM briefing layer (P4)** | Turn evidence into honest, cited text | An LLM API (Claude/GPT, or a locally-run open model via Ollama if you want zero API cost) with a forced-citation prompt template | LLM APIs are cheap at hackathon scale; local open models remove even that cost if needed |
| **Backend/orchestration (P4)** | Glue everything together | Python, `FastAPI` (lightweight, async-friendly, easy to demo live) | Minimal boilerplate, fast to iterate |
| **Frontend/dashboard (P5-equivalent)** | Depth-synced playback + analog panel | `React` + a charting library (`Recharts` or `Plotly.js`), or even a simpler `Streamlit` app if your team is short on frontend time | Streamlit specifically is worth considering if you're tight on time — it turns a Python script into a working dashboard in hours, not days |

---

# PART C — DATASETS: WHAT'S AVAILABLE, WHAT'S NOT, AND WHAT TO ACTUALLY USE

This is the part most teams get wrong by either (a) assuming they'll get OIL's real data, or (b) giving up and making everything purely synthetic with no grounding in reality. Here's the honest picture.

### C.1 What is NOT available
- **OIL's actual UA/UC (unsafe act/unsafe condition) reports, real completion reports, real eRTMAC feed** — proprietary, will very likely not be released before the finale, if ever, to a student team.
- **Real-time WITSML/OPC-UA feeds from an active Indian rig** — not accessible to you at all, for obvious operational/security reasons.

### C.2 What IS genuinely available (and this is important — use it)
- **The Volve Field Dataset (Equinor)** — this is the single best resource available to you, and most student teams doing this PS will not know about it. Equinor released a complete, real, public dataset from a real North Sea oil field (operated 2008–2016), released in 2018 specifically to support research/training use. It includes **real well logs, real drilling data, geological/stratigraphic data, and — critically — real-time drilling data originally in WITSML format** (the actual industry-standard format OIL's real systems would use). A university researcher (University of Stavanger) has already parsed the raw WITSML files into clean CSVs, which is a huge head start for you.
  - **Use this for:** validating your live-telemetry simulator with *real* drilling sensor curves (torque, RPM, flow, etc.) instead of purely invented numbers, and for grounding your trajectory/formation similarity features in a real well's real geometry.
  - **Caveat:** Volve is a North Sea field, not an OIL India (Assam/NE India) field — geologically different. Be upfront about this in your feasibility slide: "we validated our methodology on a real public field dataset; the same pipeline would apply to OIL's own fields once their data is available."
- **FORCE 2020 Lithology Prediction dataset** (a well-known public Norwegian well-log dataset used in ML competitions) — useful as a second, independent source of real well-log data if you want to strengthen your "formation similarity" feature engineering with real logs rather than only Volve.
- **Published SPE/OnePetro case-study papers** on stuck pipe and lost circulation — many abstracts and some full case descriptions are public even where the full paper is paywalled; useful as *stylistic and factual reference* for writing realistic synthetic report text (do not copy text verbatim — paraphrase into your own synthetic reports).
- **Public safety-incident report datasets** (e.g., OSHA severe-injury reports, which are fully public) — not oil-drilling-specific, but useful as a style reference for how free-text incident narratives are typically structured, if you want your synthetic reports to feel authentic.

### C.3 What you should build yourselves
- **A synthetic well corpus**: 10–15 fictional wells, each with (a) a formation/trajectory/BHA/mud-program profile grounded in ranges taken from Volve/FORCE 2020's real data (so your numbers are realistic, not arbitrary), and (b) a handful of short free-text "daily report" snippets per well, written by your team to include the event types you want to demo (mud loss, stuck pipe precursors), styled after real SPE incident write-ups.
- **A live telemetry simulator**: takes either (a) a real Volve time-series segment and replays it, or (b) a hand-crafted synthetic segment with an injectable precursor pattern, and streams it out at a controllable speed for the demo.

**Bottom line to tell your team:** *"We are not making everything up. Our similarity features and telemetry curves are grounded in a real, public oil-field dataset (Volve); only the report text and the specific hazard scenarios are synthetic, and we say so honestly in the feasibility slide."*

---

# PART D — HOW TO "EXTRACT LIVE DATA" (AND WHAT REAL SYSTEMS ACTUALLY DO)

Two separate things are being asked here — what OIL's *real* system does, and what *you* will build for the demo. Explain both to your team, because knowing the real-world standard makes your feasibility slide much more credible.

### D.1 How real rigs actually transmit live data (know this, mention it in Q&A)
The oil & gas industry has a real, standard data-interchange format for exactly this purpose: **WITSML (Wellsite Information Transfer Standard Markup Language)** — an XML-based standard for real-time and historical drilling data exchange between rig-site systems and remote monitoring centers (this is literally what eRTMAC-style systems are built on). A related standard, **OPC-UA**, is used for more general real-time industrial sensor/SCADA data. When you say "in production, this would ingest a WITSML feed," you are describing the actual real deployment path — not a fictional one.

### D.2 What you will build for the hackathon (be explicit that this is a simulation)
Since you cannot access a real WITSML feed, build a **replay simulator**:
1. Take a real numeric time-series segment (from the parsed Volve CSVs, or your own synthetic segment).
2. Write a small Python service that reads through it row-by-row (or at a fixed time-step) and pushes each reading out over a simple channel — a WebSocket, a lightweight message queue, or even just a REST endpoint you poll every few seconds.
3. Your "current well" telemetry stream in the demo is literally this replay, running at a speed you control (e.g., 1 simulated metre per second) so the live-warning "wow moment" happens on a predictable schedule during your presentation.
4. Explicitly label this in your architecture slide as **"Live Telemetry Simulator (WITSML-compatible interface; replays real/synthetic data for demonstration — production version would connect directly to eRTMAC's WITSML feed)"**. This one sentence tells a judge you understand the real deployment path even though you're demoing with simulated input — a strong credibility signal.

---

# PART E — NLP: TURNING HISTORICAL TEXT INTO NUMERIC, "PRESENT-DAY-COMPARABLE" DATA

This is the heart of your P1/P4 work. Walk through it as a pipeline, in order:

### Step 1 — Text cleaning & normalization
- Lowercase, remove boilerplate (headers/footers), standardize units (m vs ft, psi vs bar — pick one system and convert everything to it; this matters enormously for later numeric comparison).
- Handle code-mixed text (Hindi/Assamese/English) if your synthetic reports include it — at minimum, a language-ID step per sentence/phrase.
- **Tools:** `re` (regex) for boilerplate stripping, `spaCy`'s tokenizer, or a simple custom cleaner — don't overbuild this part, it's not where your novelty lives.

### Step 2 — Named Entity Recognition (NER): pulling out the "who/what/where"
- Goal: identify spans of text that are **Formation**, **Depth**, **Equipment**, **EventType**, **Intervention**, **Outcome**.
- **Tooling options, in order of hackathon-practicality:**
  1. **Rule-based / pattern matching** (`spaCy`'s `Matcher` or regex for depth values like "2870m", "2,870 m") — fast to build, surprisingly effective for well-defined patterns like depths and units.
  2. **Fine-tuned transformer NER** — take a pretrained base model (`bert-base-uncased`, or for Indian-context robustness, `MuRIL`/`IndicBERT`) and fine-tune a token-classification head on a small hand-labelled set of your synthetic reports (even 100–200 labelled sentences can work for a narrow, well-defined taxonomy). Use HuggingFace `transformers` + the `datasets` library.
  3. **Zero/few-shot LLM extraction** — for speed under time pressure, you can literally prompt an LLM to extract entities in a fixed JSON schema per sentence, no training required. This is the fastest path to a working demo, with the trade-off that it's less "our own trained model" for the research-paper angle — a reasonable trade-off if you're short on days.
- **Recommendation for a 5-day build:** start with option 3 (LLM-based extraction) to get the whole pipeline working end-to-end fast, then — if time remains — replace it with option 2 for the specific event/hazard entities, since "we trained our own domain NER model" is a stronger technical-depth claim than "we prompted an LLM to extract entities."

### Step 3 — Relation/Causal extraction: connecting the dots
- Goal: link entities into relationships — `(Event) CAUSED_BY (Precursor)`, `(Event) MITIGATED_BY (Intervention)`, `(Intervention) LED_TO (Outcome)`.
- **Technique:** dependency parsing (`spaCy`'s parser) combined with simple trigger-word rules ("as a result of," "following," "due to," "after applying") is enough for a prototype — this is a well-established NLP pattern called **rule-based relation extraction using lexical-syntactic patterns**, and it's genuinely defensible, not a hack.
- If you have time: a small fine-tuned relation-classification transformer (sentence + entity-pair → relation type) is the "more rigorous" version.

### Step 4 — Event normalization / taxonomy mapping
- Different reports will describe the same event differently ("torque increase," "TRQ spike," "elevated torque reading"). You need a step that maps all of these to **one canonical event-type ID** from a fixed vocabulary your team defines up front (e.g., `EVT_TORQUE_UP`, `EVT_MUD_LOSS_PARTIAL`, `EVT_MUD_LOSS_SEVERE`, `EVT_LCM_APPLIED`, `EVT_CIRC_RESTORED`).
- **Technique:** compute the embedding (via `sentence-transformers`, e.g. the `all-MiniLM-L6-v2` model — small, fast, free, no fine-tuning needed) of each extracted event phrase, then assign it to the nearest canonical event-type by **cosine similarity** against a small set of reference phrases you write for each canonical type. This is the exact mechanism that turns messy language into a fixed, comparable vocabulary.

### Step 5 — Converting to numeric/structured form (the actual "text → numbers" step)
Once you have (event-type ID, well, depth, timestamp, entities), you build a numeric feature representation two ways, because you need both:
1. **A structured record** (for the Knowledge Graph and for exact filtering): a row per event with columns `well_id, depth_m, timestamp, event_type_id, formation_id, ...` — fully numeric/categorical, ready for the similarity engine.
2. **A sequence token** (for sequence matching): each event becomes a symbol/token in a well's event-sequence "sentence," e.g. Well A's history becomes the token sequence `[NORMAL, TORQUE_UP, FLOW_ANOMALY, MUD_LOSS_PARTIAL, LCM_APPLIED, CIRC_RESTORED]` — this is literally what gets fed into the sequence-matching algorithm in Part F.

**Tell your team this one-liner:** *"NLP doesn't just summarize text for humans here — its real job is to turn free-text sentences into a fixed vocabulary of event-type IDs and numeric feature rows, so that a well drilled in 2014 and today's live well can be compared using the same numbers."*

---

# PART F — SIMILARITY CALCULATION: THE MATH, IN DETAIL

This is the section your team needs to understand cold, since it's your core novelty (hazard-specific similarity) and P2's main deliverable.

### F.1 Feature vector construction (per well, per hazard type)
For a given hazard (say, mud loss), define a feature vector per well, e.g.:
```
v_well = [formation_match_score, pore_pressure_diff, mud_weight_window_overlap,
          trajectory_similarity_score, depth_range_overlap, BHA_similarity_score]
```
Each component is itself a computed similarity or distance between the current well and a candidate historical well, **normalized to a common 0–1 scale** (min-max or z-score normalization — this step matters a lot, since raw units differ wildly: torque in kN·m vs. depth in metres vs. a categorical formation ID).

### F.2 The weighted similarity formula (this is your headline formula — write it on a slide)
```
Similarity(well_i, hazard_h) = Σ (w_h,k × sim_k(well_i, current_well))   for k = 1..K features
```
Where:
- `sim_k` is the normalized similarity (0 to 1) for feature `k` (e.g., formation match, trajectory match).
- `w_h,k` is the **weight of feature k for hazard h** — this is the entire point of your "hazard-specific" claim: for mud-loss (`h = mud_loss`), formation and pore-pressure features get high `w`; for stuck-pipe (`h = stuck_pipe`), trajectory and BHA features get high `w`.
- The weights must sum to 1 per hazard (`Σ w_h,k = 1`) so the final score stays interpretable as a 0–1 relevance score.

### F.3 Where do the weights come from? (Two credible options — use both, described as v1 and v2)
1. **v1 — Expert-elicited weights via Analytic Hierarchy Process (AHP):** AHP is a real, established multi-criteria decision-making technique (Saaty, 1980s) where you construct a pairwise-comparison matrix ("how much more important is formation-match than trajectory-match for mud-loss risk, on a 1–9 scale?") and derive normalized weights from its principal eigenvector. This is the version you can build and defend on Day 1 without needing any training data — cite the public drilling-engineering literature (e.g., SPE reviews on stuck-pipe causation) to justify your pairwise judgments, exactly as flagged in your earlier planning doc.
2. **v2 — Learned weights (stretch goal):** if you have any signal at all of "was this analog actually useful" (even from your team manually labelling synthetic scenarios), you can fit a simple **logistic regression** or **gradient-boosted tree** (`scikit-learn` or `xgboost`) where the features are the per-dimension similarities and the label is "was this a true positive analog." The learned coefficients become your data-driven weights. This is a nice-to-have, not required for a credible prototype — lead with v1.

### F.4 Individual similarity functions (the building blocks of `sim_k`)
- **Categorical features (formation type, BHA type):** `Jaccard similarity` — size of intersection over union of relevant attribute sets. Simple, interpretable, defensible.
- **Continuous numeric features (pore pressure, mud weight):** `1 − normalized Euclidean distance`, or Gaussian-kernel similarity `exp(−(Δ²)/(2σ²))` if you want smoother decay with distance — both are standard, well-understood.
- **Trajectory shape (inclination/azimuth vs. depth curves):** **Dynamic Time Warping (DTW) distance**, converted to a similarity via `1/(1+DTW_distance)` or a Gaussian kernel on the distance. DTW specifically handles the fact that two wells' trajectories may be "the same shape" but stretched/compressed differently along depth — exactly the right tool for this feature.
- **Text-derived event similarity (as a secondary, supporting signal only — not your primary similarity):** cosine similarity between `sentence-transformers` embeddings of report snippets.

### F.5 Sequence matching math (this is separate from well-similarity — it's about comparing *event sequences*, not static well attributes)
Two well-established approaches, both worth knowing and worth mentioning by name to a judge:
1. **Dynamic Time Warping (DTW)** — best for continuous numeric time-series (e.g., comparing the actual torque/flow curves of two wells over a depth window), since it can align sequences of different lengths/speeds while still recognizing they follow the "same shape."
2. **Sequence alignment (Needleman-Wunsch for global alignment, Smith-Waterman for local alignment)** — these are the classic bioinformatics algorithms used to align DNA/protein sequences, and they are *directly and legitimately applicable* to your discretized event-token sequences (Part E, Step 5) — you're aligning `[NORMAL, TORQUE_UP, MUD_LOSS_PARTIAL, ...]` against another well's token sequence the same way biologists align gene sequences, using a scoring scheme (match/mismatch/gap penalties) and dynamic programming. This is a genuinely elegant, well-grounded technique to cite — it signals real algorithmic literacy to a judge, not just "we called an AI API."
- **Libraries:** `fastdtw` or `dtaidistance` (DTW, pip-installable); for sequence alignment, `Biopython`'s `pairwise2`/`Align` module works perfectly well even outside biology, since it's a general string/sequence-alignment implementation — or a ~40-line custom Needleman-Wunsch implementation, which is simple enough to write yourselves and *show* in your technical slide as evidence of genuine engineering.

### F.6 The uncertainty/disagreement calculation (your other big differentiator)
When you have `N` matched analogs and `M` of them experienced the hazard event, don't just report `M/N` as a flat percentage — that hides how much you should trust it with only a few data points. Use a **Wilson score interval** (a standard statistical technique for confidence bounds on a proportion from a small sample) to compute a defensible confidence range, e.g., "2 of 4 analogs (50%, 95% CI: 15%–85%) experienced this event" — the wide interval on a small sample is itself the honest signal that "we don't have much data here," which is exactly the transparency your innovation report identified as a differentiator. This is a real, simple, citable statistical formula (available directly via `statsmodels.stats.proportion.proportion_confint(method='wilson')` in Python) — not something you need to invent.

---

# PART G — SUMMARY TABLE: TASK → TECHNIQUE → LIBRARY (for quick team reference)

| Task | Technique | Library/Tool |
|---|---|---|
| Text cleaning | Regex, tokenization | `re`, `spaCy` |
| Entity extraction | Rule-based + fine-tuned transformer NER (or LLM few-shot for speed) | `spaCy`, HuggingFace `transformers`, or an LLM API |
| Relation/causal extraction | Dependency parsing + lexical trigger patterns | `spaCy` |
| Event-type normalization | Sentence embeddings + cosine similarity to canonical labels | `sentence-transformers` |
| Well feature similarity | Weighted sum of per-feature similarity (Jaccard, Euclidean/Gaussian, DTW) | `numpy`, `scipy` |
| Hazard-specific weights | AHP (expert-elicited) → optional logistic regression/XGBoost (learned) | manual/`scikit-learn`/`xgboost` |
| Trajectory similarity | Dynamic Time Warping | `fastdtw`, `dtaidistance` |
| Event-sequence matching | Sequence alignment (Needleman-Wunsch/Smith-Waterman) | `Biopython.Align`, or custom implementation |
| Precursor/anomaly detection | Rolling z-score/CUSUM (baseline), autoencoder (stretch) | `numpy`/`scipy`, `PyTorch` (optional) |
| Uncertainty quantification | Wilson score confidence interval | `statsmodels` |
| Knowledge graph | In-memory property graph | `networkx` |
| Retrieval (GraphRAG) | Pre-filter by analog list, then embedding search within filtered set | `sentence-transformers` + simple cosine top-k |
| Briefing generation | LLM with forced-citation prompting | LLM API (or local via `Ollama`) |
| Backend | REST/WebSocket API | `FastAPI` |
| Frontend | Depth-synced playback dashboard | `React`+`Recharts`/`Plotly`, or `Streamlit` for speed |

---

# PART H — HOW TO DECIDE THE DATA FORMAT (the single most important early decision)

Your entire team's parallel work depends on agreeing on this on Day 1, before anyone writes significant code. Here is a concrete, ready-to-adopt schema — bring this to your team meeting and adjust field names as needed, but don't skip agreeing on *something* concrete.

### H.1 Canonical event record (JSON, one object per event — used between P1→P4 and P3→P4)
```json
{
  "well_id": "SYN-WELL-07",
  "event_id": "SYN-WELL-07-EVT-014",
  "depth_m": 2870.5,
  "timestamp": "2014-06-12T08:15:00Z",
  "event_type_id": "EVT_MUD_LOSS_PARTIAL",
  "formation_id": "FORM_HUGIN_SANDSTONE",
  "source": "report",
  "source_snippet_id": "SYN-WELL-07-REPORT-03-SENT-12",
  "confidence": 0.86,
  "raw_text": "Partial losses observed while drilling through the sandstone interval..."
}
```

### H.2 Canonical well-metadata record (JSON, one per well — used by P2)
```json
{
  "well_id": "SYN-WELL-07",
  "trajectory": [{"depth_m": 0, "inclination_deg": 0, "azimuth_deg": 0}, "..."],
  "formations": [{"formation_id": "FORM_HUGIN_SANDSTONE", "top_depth_m": 2700, "base_depth_m": 3100}],
  "mud_program": {"mud_weight_ppg": 11.2, "mud_type": "WBM"},
  "bha_type": "BHA_ROTARY_STEERABLE_A",
  "casing_design": "..."
}
```

### H.3 Canonical live-telemetry record (streamed, one per tick — used by P3/simulator → similarity/sequence engines)
```json
{
  "well_id": "CURRENT-WELL",
  "depth_m": 2830.2,
  "timestamp": "2026-09-10T14:02:33Z",
  "torque_knm": 18.4,
  "rop_m_per_hr": 12.1,
  "flow_lpm": 2100,
  "standpipe_pressure_bar": 145.2
}
```

### H.4 Format decisions, explained (so you can defend them)
- **JSON/JSONL for events and metadata** — human-readable (easy to debug when 4 people are integrating in a hurry), works identically in every language/library, trivially parsed by both your Python backend and any LLM prompt you build. This is the *interchange* format between modules.
- **CSV or Parquet for bulk raw telemetry storage** (not the live stream itself, but your historical Volve-derived numeric datasets) — columnar formats are simply faster to load and filter for large numeric time-series than JSON; Parquet specifically is worth it if your Volve extract gets large (megabytes+), CSV is fine for smaller cuts.
- **A shared, versioned "event-type vocabulary" file** (a simple JSON or CSV list of all valid `event_type_id` values, owned jointly by P1 and P3) — this is the single most important shared artifact in your whole project, since P1's NLP extraction and P3's live precursor detection must emit *the exact same set of event-type IDs* for sequence matching to work at all. Put this file in your shared repo on Day 1 and treat changes to it as requiring team agreement, not a solo edit.
- **Units standardization table** — decide once (metric, e.g., metres/bar/kN·m) and enforce it at the point of ingestion for both historical and live data, so no module ever has to guess which unit system a number is in.

---

# PART I — WORKING TOGETHER IN ANTIGRAVITY

Antigravity (Google's agentic development platform) has two modes, and understanding both changes how you should split work:

- **Editor View** — a normal AI-assisted code editor (like a VS Code with an agent alongside you) for synchronous, hands-on work.
- **Manager Surface / Agent Manager** — the actual differentiator: a "mission control" where you can **spawn multiple agents into separate workspaces, and they work asynchronously and in parallel**, each producing reviewable "Artifacts" (task lists, implementation plans, diffs, screenshots) that you approve or redirect, rather than one continuous chat.

### I.1 Should you give one giant prompt, or split into modules? — **Split into modules. Definitively.**

Reasons, specific to your project:
1. **Your four/five modules (NLP extraction, similarity engine, sequence matching, KG/RAG/LLM/backend, frontend) have genuinely different concerns, different libraries, and different failure modes.** One agent trying to hold all of that context at once will do a worse job on each part than four agents each focused tightly on one part with a clear contract.
2. **Antigravity is explicitly built for this** — the Manager Surface's whole purpose is running several scoped agents in parallel across workspaces, exactly matching your 4–6 person module split. Using one mega-prompt for the whole system wastes the tool's actual advantage.
3. **The Part H data contracts are what make parallel work safe.** As long as every agent is told the exact JSON schema its module must produce/consume, four agents can build in parallel without stepping on each other, and integration becomes "does the JSON match the schema," not "does the code architecturally make sense together."

### I.2 Recommended Antigravity setup for your team

**Create one workspace per module**, each with its own scoped agent and its own tightly-written prompt:

- **Workspace 1 — NLP Extraction (P1's agent):** Prompt should specify: input (raw text reports), output (exact JSON schema from Part H.1), the event-type vocabulary file, and explicitly which technique to start with (rule-based + LLM few-shot extraction first, per Part E recommendation) — plus a small labelled example set to test against.
- **Workspace 2 — Similarity Engine (P2's agent):** Prompt should specify: input (well-metadata JSON from H.2), output (a ranked analog list with per-feature weighted scores, per hazard type), and explicitly the weighted-formula and AHP-weight approach from Part F.2–F.3, so the agent doesn't default to a generic single blended score.
- **Workspace 3 — Sequence Matching + Live Simulator (P3's agent):** Prompt should specify: input (live telemetry ticks per H.3 + historical event sequences per H.1), output (a match score + aligned sequence visualization data), and explicitly name DTW/Needleman-Wunsch as the required approach (Part F.5) rather than letting the agent default to a generic ML classifier.
- **Workspace 4 — Knowledge Graph + GraphRAG + LLM Briefing + Backend Orchestration (P4's agent — this is you):** Prompt should specify: the graph schema (Part 4.3 from your earlier deep-dive doc), the GraphRAG pre-filter-then-retrieve design (not plain vector RAG), the forced-citation LLM prompt template, and the uncertainty/Wilson-interval calculation from Part F.6.
- **Workspace 5 (optional, later) — Frontend/Dashboard:** kept separate and started once Workspace 4's API shape is stable, since it consumes everyone else's output.
- **A final "Integration" workspace/session** — once all four modules produce output matching the agreed schemas, use one session (can even be a human-led session in the Editor View, not a fully autonomous agent) to wire the real modules together end-to-end, replacing the mocked data each module used during parallel development.

### I.3 How to actually write each module's prompt (a template)
For every workspace, structure the prompt as:
1. **Role & scope** — "You are building ONLY the [X] module. Do not modify other modules' code."
2. **Exact input format** — paste the JSON schema from Part H.
3. **Exact output format** — paste the expected JSON schema it must produce.
4. **Required technique** — name the specific algorithm/library from Parts E/F/G (don't leave this open-ended, or the agent may default to a generic, less-defensible approach like plain cosine-similarity-on-everything).
5. **Test data** — point it at your synthetic/Volve-derived sample files so it can self-test against real-shaped data, not toy examples.
6. **Definition of done** — a concrete, checkable output (e.g., "given this sample input file, produce this sample output file matching the schema").

### I.4 Sync discipline across parallel agents
- Use a **shared Git repository** with one branch per module workspace; merge into a shared `integration` branch daily, not just once at the end.
- Treat the **event-type vocabulary file and the JSON schemas in Part H as the actual contract** — any agent that wants to change them must flag it to the whole team first, since a silent schema change in one workspace will silently break another module's agent.
- Each morning, quickly run each module's agent's latest output against the *other* modules' expected input format (even a simple `python -c "import json; json.load(open('sample_output.json'))"` plus a schema-shape check) before continuing — catching drift early is much cheaper than discovering it on Day 4.

---

# PART J — HOW TO EXPLAIN ALL OF THIS TO YOUR TEAM (a talking script)

Use this as your actual spoken walkthrough:

> "We turn both old drilling reports and today's live sensor numbers into the same 'language' of events — using NLP to pull structured events out of messy text, and simple statistics to spot changes in live numbers. Once both sides speak the same language, we ask two questions: first, which historical wells are actually comparable to this one **for this specific risk** — not just nearby wells, but wells that share the right formation, trajectory, or equipment characteristics depending on whether we're worried about mud loss or a stuck pipe — using a weighted similarity formula we can defend with real drilling-engineering literature. Second, does the sequence of events happening right now match a sequence that's played out before in one of those wells — using the same kind of sequence-alignment math used in DNA analysis, applied to drilling events instead. Finally, an LLM turns all of that evidence into a plain-English briefing for the engineer — but the LLM is never allowed to make up the risk number or hide disagreement between historical wells; it can only explain evidence we've already computed, with a citation back to the exact report sentence or graph fact behind every claim. We validated this whole pipeline on a real public oil-field dataset (Volve, released by Equinor), so our numbers are grounded in real drilling physics, not invented — we're upfront that OIL's own field data would replace it in a real deployment. And we're building this in four parallel tracks in Antigravity, one agent per module, each with a locked-down data format so we can work independently and integrate without surprises."

---

# PART K — QUICK-START CHECKLIST FOR YOUR NEXT TEAM MEETING

1. Walk through the Part A diagram together, out loud, once.
2. Assign the 4 (or 5) Antigravity workspaces to the 4–6 team members per your existing role split.
3. Agree on the Part H.1–H.3 JSON schemas and the event-type vocabulary list — write it down in a shared doc before anyone opens Antigravity.
4. Download a small slice of the Volve real-time drilling CSVs (via the University of Stavanger's parsed files) and the FORCE 2020 well-log dataset as your grounding data.
5. Write each module's Antigravity prompt using the Part I.3 template and launch all workspaces in parallel.
6. Set a daily 10-minute sync to check schema compatibility across modules (Part I.4).