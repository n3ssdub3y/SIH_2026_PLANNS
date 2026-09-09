# NWIS-Sentinel — Corrected Slide Blueprint (Slides 2–6)
**SIH26121 — Oil India Limited — Nearby Wells Intelligence System**

This document replaces the old "Part 4: Visual, Diagram & Flowchart Blueprints" section of the master guide. It is built from `PLANNNNN.md` (current implementation plan), `nwis_data_sources.md`, the official PS text, and an external research pass — not from the outdated guide.

Since the code will not be checked and the panel is judging the idea/architecture, every slide below leans on one clear architecture-style diagram as the dominant visual — boxes, swimlanes, and arrows, styled and colored properly (not a bare skeletal flowchart, not an AI-generated poster), with one or two small supporting graphics. No emojis anywhere in the deck.

---

## Research Corrections Carried Into This Version

These stand regardless of demo/code status, because they are about what the slides *claim*, which the panel will read closely:

- **Do not use "15/9-19A, July 26 1997, 3,172 m" as the flagship backtest fact.** Sodir's public wellbore history shows well **15/9-19 A** reached total depth with no stuck-pipe event on record. The real, documented incident is on the *sidetrack* well **15/9-19 B**: "due to stuck pipe the string was severed and the well plugged back." Use 15/9-19B, and do not state a specific depth/timestamp/lead-time unless it comes out of an actual run of your pipeline — present the backtest as your validation method, with a real number only if you have one by submission time.
- **Module status:** `PLANNNNN.md` is a build plan, not a report of finished work. Drop "Module 1: 100% Implemented & Tested," "159 wells / 1,959 events / 63 incidents," ">91% precision," "<150 ms latency" — none of these appear in the source documents. Use PLANNNNN's stated *targets* instead (100+ real wells via FORCE 2020, 5–9 real Volve wellbores with telemetry, 40–60 synthetic wells / 200–400 synthetic reports).
- **5 hazard types, not an 18-class ontology.** `PLANNNNN.md` scopes the event vocabulary to mud loss, stuck pipe, overpressure, torque spikes, and cementing issues.
- **Statistical baseline first, not XGBoost + Bi-LSTM.** The current plan mandates rolling z-score / CUSUM as the primary, always-visible detector; a neural model is an optional secondary signal only.
- **Explainability mechanism is AHP weights + Wilson confidence intervals + citation-checked LLM briefings** — not SHAP/LIME, which isn't in the current plan.
- **Map stack:** Google Maps Platform JS API, with Leaflet + OpenStreetMap as the stated free fallback — not PostGIS/Mapbox/Deck.gl.
- **Confirmed-accurate figures kept:** ~25% of drilling NPT from stuck pipe/lost circulation and ~$250M+/year industry-wide cost (corroborated across independent academic/industry sources); Volve DDR corpus = 1,759 records (`bengsoon/volve_alpaca` on Hugging Face); FORCE 2020 = 118 real wells (Zenodo, NPD/Sodir release, NOLD 2.0 license).
- **Dropped as unsourced:** "70% reduction in well-planning time," "$800k–2.5M saved per incident," "40,000 L diesel / 105 t CO2 per event," "10 idle rig-days per well." None trace to the project files or to a verifiable source for this project's context. Replaced with defensible, cited industry baselines, explicitly separated from project-specific projections.

---

## Deck-Wide Visual System

Apply this same system on every slide so the five slides read as one deck.

- **Palette:** one dark neutral (slate/navy) as the structural color for boxes and text, one cool accent (teal or blue) for "data / pipeline" elements, one warm accent (amber) reserved only for alerts, risk, and warnings. No more than these three colors plus a light neutral background.
- **Diagram idiom:** rounded rectangle nodes, thin uniform-weight arrows, consistent corner radius, consistent node padding. Group related nodes inside a labeled outer container (a "swimlane" or "phase box") rather than letting nodes float freely — this is what makes a Mermaid-style diagram read as designed rather than auto-generated.
- **Text inside diagrams:** node labels are 2–5 words. Never a sentence inside a box. Anything that needs a sentence goes in a caption strip beneath the diagram or is left for the spoken pitch.
- **Provenance marker:** a small filled dot = real data, a small outlined/hollow dot = synthetic data. Reused on every slide that references data sources (3, 4, 6), so the transparency theme is visually consistent.
- **Badges:** any standalone fact or number is shown as a small pill-shaped badge, not as loose floating text. One visual treatment for badges across all five slides.
- **Icons:** simple, single-weight line icons only, used sparingly (one per major node at most). No stock photography, no 3D renders, no gradients-as-decoration, no satellite/hero imagery unless it is functionally the map itself.
- **Type:** one geometric sans-serif throughout, two weights only (regular for body/labels, bold for titles and key numbers).

---

## SLIDE 2 — IDEA TITLE

### PART A — DETAILED CONTENT

**1. Detailed explanation of the proposed solution**

NWIS-Sentinel is a standalone AI/ML/NLP decision-support platform that sits alongside OIL's existing eRTMAC real-time monitoring system and gives it institutional memory. eRTMAC tells a drilling team what is happening *right now* on the active well. NWIS-Sentinel answers the question eRTMAC cannot: has this happened before, nearby, and what did we learn?

Four linked layers, matching `PLANNNNN.md`'s actual module boundaries:

- **Layer 1 — Document Intelligence:** OCR + NLP pipeline converts historical Well Completion Reports, Daily Drilling Reports, and mud logs (scanned or digital) into structured, timestamped, depth-tagged events, normalized against a fixed 5-hazard canonical vocabulary (mud loss, stuck pipe, overpressure, torque spike, cementing issue).
- **Layer 2 — Geospatial & Offset-Well Intelligence:** an interactive map finds nearby wells within a user-defined radius, plus a hazard-specific similarity engine — five separately-weighted feature sets, one per hazard, with weights derived transparently via the Analytic Hierarchy Process (AHP) rather than hidden inside a model.
- **Layer 3 — Predictive Risk & Time-Travel Backtest:** statistically transparent precursor detection (rolling z-score / CUSUM) on live or replayed telemetry, matched against analog wells' historical event sequences via sequence alignment, with risk always reported as a Wilson-confidence-interval range, never a bare number.
- **Layer 4 — Knowledge Graph, GraphRAG & Dashboard:** wells, formations, events, interventions, and outcomes tied into a queryable graph; engineer-facing briefings generated with a forced-citation LLM prompt and an automatic verification pass; everything surfaced on one unified dashboard.

**2. How it addresses the problem** — map directly to the OIL problem statement's own four points:
- *"Display nearby wells on a geospatial map relative to the active well"* → the radius-based map.
- *"Instant access to historical drilling experiences...from offset wells"* → the searchable knowledge repository.
- *"Correlate drilling parameters, reservoir characteristics, mud losses, kicks, stuck pipe..."* → the hazard-specific similarity engine and formation/depth correlation table.
- *"Generate proactive alerts when current drilling operations approach depths or formations where similar challenges were encountered"* → precursor detection, sequence matching, and alerting.

**3. Innovation and uniqueness**
- **Hazard-specific similarity, not one generic score** — five separately-weighted similarity functions, because the features that predict stuck pipe (trajectory shape, BHA type) are not the features that predict cementing failure (cement volume, casing design), and the weights are auditable via AHP, not implicit inside a neural net.
- **Pre-filter-then-retrieve GraphRAG**, not plain vector search over all documents — the system restricts to the hazard-relevant analog subgraph first, then retrieves only within that pre-filtered set, reducing hallucination risk and keeping every answer traceable to a specific well/report.
- **Statistical-first predictive core** — rolling z-score / CUSUM is the mandatory, always-visible baseline; deep learning is optional and secondary, by design, so a rig-floor alert always has a plain-language reason.
- **The historical time-travel backtest** — replaying a real historical well's data chronologically, blind to the future, to measure how much lead time the system would have given. Present as your validation methodology; only quote a specific number once one has actually been computed.

### PART B — DESIGN & VISUALIZATION DIRECTION

**Composition:** one dominant architecture diagram in the center, a one-line hero statement above it, three small badges below it. Nothing else on the slide.

**Primary diagram — System Concept Map (four-phase pipeline, Mermaid-style swimlanes rendered as a designed graphic):**

Four labeled phase containers side by side, left to right: **EXTRACT — CORRELATE — PREDICT — ADVISE**. Each container is a large rounded outer box in a light tint of the slide's accent color, with the phase name as a bold header. Inside each container sits one small icon and one 2–4 word subtitle (not a sentence) — e.g., inside EXTRACT: a document icon, subtitle "Reports become events." Inside CORRELATE: a map-pin icon, subtitle "Find offset wells." Inside PREDICT: a small waveform icon, subtitle "Detect precursors." Inside ADVISE: a small graph/node icon, subtitle "Explain the alert."

Thin uniform arrows connect the four containers left to right. Below the four containers, a slim connector strip shows what feeds in on the left ("historical reports," "live telemetry," each as a tiny badge) and what comes out on the right ("rig-floor alert," "DOC dashboard," each as a tiny badge) — this is the only place data sources are named on this slide; keep it to labels, not lists.

**Supporting visuals:** none beyond the four phase icons already in the diagram. Do not add a second illustration — the phase diagram alone should carry the slide.

**Callouts below the diagram:** three short badges stating the problem-to-solution pairing, each capped at roughly six words per side, e.g.: "Nearby wells buried in reports" leading to "Mapped and searchable in seconds"; "One generic similarity score" leading to "Five hazard-specific engines, AHP-weighted"; "Unexplained AI alerts" leading to "Every alert traces to a real well."

**Hierarchy:** hero line (largest, top) - phase diagram (dominant, center) - three badges (smallest, bottom row).

**Density:** the lightest slide in the deck. One diagram, one sentence, three badges. No technology names, no numbers, no backtest figures here — that content belongs on Slides 3 and 4.

---

## SLIDE 3 — TECHNICAL APPROACH

### PART A — DETAILED CONTENT

**1. Technologies to be used** (grounded in `PLANNNNN.md`, including the explicit free-fallback options where the plan allows a choice):

| Layer | Technology | Note |
|---|---|---|
| OCR | Google Cloud Vision API, or Tesseract as free fallback | credential-dependent |
| NLP / entity extraction | spaCy (rule-based NER for depths/units), Hugging Face transformers (few-shot / fine-tuned extraction) | both explicitly planned |
| Event normalization | sentence-transformers (Hugging Face) similarity against a versioned canonical vocabulary | 5 hazard types |
| Geospatial map | Google Maps Platform JS API, or Leaflet + OpenStreetMap as free fallback | |
| Similarity engine | Jaccard (categorical), Gaussian-kernel / Euclidean (continuous), DTW (trajectory shape) | AHP for weight derivation |
| Search | Whoosh or Elasticsearch, plus sentence-transformer embeddings | keyword + semantic |
| Predictive core | rolling z-score / CUSUM (primary, always shown); optional autoencoder reconstruction error (secondary) | no XGBoost / Bi-LSTM in current plan |
| Sequence matching | Biopython pairwise alignment (Needleman-Wunsch / Smith-Waterman) | |
| Confidence reporting | Wilson score confidence intervals | |
| Knowledge graph | in-memory property graph | library TBD by Module 4 owner |
| LLM | Google Vertex AI / Gemini, or Hugging Face Inference API | forced-citation prompt + verification pass |
| Dashboard | React or Streamlit | Streamlit offered as the speed option |

**2. Methodology / implementation workflow** — the same four-phase pipeline as Slide 2, with technical depth added:

1. **Extract:** OCR renders scanned reports to text; NLP extracts Formation / Depth / Equipment / EventType / Intervention / Outcome spans; causal/relation extraction links event to intervention to outcome via dependency parsing and lexical triggers ("as a result of," "following," "due to"); everything normalized to the versioned 5-hazard vocabulary.
2. **Correlate:** user selects a well and a radius; nearby wells surface on the map, color-coded by data source (real Volve / real FORCE2020 / synthetic); for each of the 5 hazards a separately-weighted similarity score ranks offset wells; a formation-tops table answers "who else hit this formation, at what depth."
3. **Predict:** telemetry (live or replayed) runs through statistical precursor detection; matched against analog wells' historical event sequences via alignment; risk is reported as "N of M matched analogs experienced this event next (X%, 95% CI: Y%–Z%)" — never a bare percentage.
4. **Advise:** the knowledge graph pre-filters to the hazard-relevant analog subgraph; retrieval happens only within that subgraph; the LLM briefing carries a citation on every sentence to a specific graph node or report snippet; a verification pass checks each citation and removes unsupported sentences; the dashboard shows the alert, its full feature/weight breakdown, and the verified briefing together.

**Framing note for this slide:** state once, clearly, that this is the target architecture per the current build plan — the demo shown live is the working proof of it, not a claim that every box in the diagram is independently benchmarked.

### PART B — DESIGN & VISUALIZATION DIRECTION

**Composition:** this is the deck's master schematic and can hold the most detail, but every node still stays label-length, not sentence-length.

**Primary diagram — Master Architecture Schematic (Mermaid-style swimlane flowchart, styled as a proper infographic):**

Four horizontal swimlanes stacked top to bottom, one per phase (Extract, Correlate, Predict, Advise), each swimlane a full-width band in a light tint of the accent color with the phase name as a left-aligned header tab. Inside each swimlane, 2–3 small connected nodes show the real components for that phase — for example, inside Extract: "OCR" leading to "NLP Extraction" leading to "5-Hazard Vocabulary." Inside Predict: "Precursor Detection (statistical)" leading to "Sequence Match" leading to "Wilson CI Risk Score." Keep each node to 2–4 words; if a concept needs more, it becomes a small caption beneath the node rather than being crammed into the box.

A thin connecting arrow runs vertically between the swimlanes, showing the pipeline flowing top to bottom (or left to right if horizontal fits the layout better — pick whichever keeps text most legible at slide scale).

Beneath the four swimlanes, one slim data-provenance strip: three small badges (Volve real-time telemetry, FORCE 2020 well logs, synthetic DDR corpus), each with the small filled/hollow provenance dot from the deck-wide system.

**Supporting visual:** one small standalone badge, separate from the diagram, stating the transparency principle in a short phrase: "every prediction ships with its feature values and weights" — positioned as a caption, not as another diagram.

**Labels/callouts:** component names only, 2–4 words. Arrows may carry a one-to-two word label where it adds clarity ("normalized events," "analog wells," "citation-checked").

**Hierarchy:** the four swimlanes are the visual anchor and take most of the slide; the provenance strip and the transparency badge are smaller, positioned below, and clearly secondary.

**Density:** this can be the most detailed slide in the deck, but density comes from having more small labeled nodes, never from paragraph text. If the diagram feels crowded, drop a component from the visual and mention it verbally instead of shrinking the type.

**What not to include:** no fabricated performance numbers (latency, accuracy percentages) unless they come from an actual run. If a number is wanted here, use a structural fact instead — "5 hazard types," "4-phase pipeline," "AHP-weighted similarity" — shown as a small badge, not a performance claim.

---

## SLIDE 4 — FEASIBILITY AND VIABILITY

### PART A — DETAILED CONTENT

**1. Feasibility analysis**

- **Technical feasibility:** every core technique used is an established, well-documented method — OCR, NER, embedding search, AHP, DTW, sequence alignment, Wilson intervals, rolling statistics. This is a genuine strength: the project deliberately avoids exotic, hard-to-validate deep learning as its primary mechanism, so every component is individually proven; the innovation is in how they are combined for this specific domain problem.
- **Data feasibility:** the project has identified and mapped real, public, freely licensed datasets that substitute for OIL's proprietary WCRs/DDRs at meaningful scale — Volve (real North Sea field, real WITSML-origin telemetry, real DDR text, Equinor Open Data Licence) and FORCE 2020 (118 real wells, NPD/Sodir-released, NOLD 2.0 license), supplemented by a clearly-labeled synthetic corpus for hazard coverage the real data does not fully provide. The sourcing plan is concrete and already scoped, not aspirational.
- **Operational feasibility:** the system is designed as a standalone layer alongside eRTMAC, not a replacement — it consumes the same class of real-time drilling parameters (ROP, WOB, torque, SPP, flow) that WITSML-based rig systems already stream, so integration does not require re-instrumenting the rig.

**2. Potential challenges & risks, and 3. mitigation strategies** — risks specific to this project's actual plan:

| Challenge | Why it's real | Mitigation actually planned |
|---|---|---|
| Proprietary OIL data unavailable for the hackathon | WCRs/DDRs are confidential; cannot use OIL's real archives | Public real datasets (Volve, FORCE 2020) chosen because they cover most of OIL's listed data source categories, supplemented by clearly-labeled synthetic reports for hazard types the real data doesn't document |
| No genuine eRTMAC data to simulate live streaming | eRTMAC is fully proprietary to OIL | a Live Telemetry Simulator, explicitly labeled as such in code and documentation, replays real Volve WITSML-origin telemetry row by row to approximate the real feed's structure |
| Risk of the time-travel backtest becoming an unverifiable claim | easy to overstate a lead-time number without real computation | the backtest lead-time is only reported once computed end-to-end from real data, and the specific well and case used are stated explicitly |
| False-alarm fatigue on a real rig floor | every alerting system faces this in the field | Wilson confidence intervals are reported alongside every risk score, never a bare percentage, so uncertainty stays visible rather than hidden |
| Skepticism toward "black box" AI from experienced drillers | domain experts distrust unexplained ML | AHP pairwise weights and feature-level similarity breakdowns are stored as human-readable, auditable files; LLM briefings must cite a specific well or report for every sentence, with a verification pass that removes unsupported claims |
| Sequential four-module handoff is a single point of failure | confirmed by the team's own plan — each module blocks the next | each module has an explicit, versioned output-file contract, so downstream modules can build against a stable interface even while upstream internals are still being refined |

### PART B — DESIGN & VISUALIZATION DIRECTION

**Composition:** two zones — a small feasibility triad across the top, a risk-to-mitigation architecture diagram dominating the rest of the slide.

**Primary diagram — Risk/Mitigation Bridge (rendered as a two-column architecture diagram, not a plain table):**

Two parallel columns of rounded nodes: left column in the warm accent color, labeled "Risk," right column in the cool accent color, labeled "Mitigation," with a short connecting arrow between each matched pair. Use four to five rows, picking the strongest rows from the table above — not all six. Each node is a short label (four to six words), matching the deck-wide node-length rule. This reads as a resolved problem-to-solution ladder rather than a spreadsheet, while still being a proper structured diagram rather than a decorative graphic.

**Secondary visual — Feasibility Triad:** three small nodes across the top of the slide (Technical, Data, Operational), each a short label plus one supporting badge underneath carrying a real, sourced fact — for example, under Data: "118 real wells, FORCE 2020" plus "real Volve telemetry." No invented numbers in this row.

**Supporting visual:** reuse the small provenance dot (filled = real, hollow = synthetic) from Slide 3 next to the Data node, to keep the visual language consistent across the deck.

**Labels/callouts:** risk and mitigation labels capped at six words; feasibility badges capped at the sourced fact only, no elaboration.

**Hierarchy:** the risk/mitigation bridge is the visual anchor and largest element; the feasibility triad sits above it, smaller; the provenance dot is the smallest element on the slide.

**Density:** medium. This slide legitimately carries more content than Slide 2, but the bridge-diagram format keeps it from reading as a wall of text even with five rows.

**What not to include:** no repeat of the four-phase pipeline (already shown twice); no dollar figures (those belong on Slide 5); no plain black-and-white table — the two-column bridge treatment is what keeps this an architecture diagram rather than a spreadsheet.

---

## SLIDE 5 — IMPACT AND BENEFITS

### PART A — DETAILED CONTENT

**1. Potential impact on target audience**

- **Rig-floor drillers and toolpushers:** an explainable, confidence-scored early warning instead of relying solely on individual experience when approaching a historically hazardous depth or formation.
- **Drilling engineers and well planners:** instant, searchable access to what happened in nearby wells at similar formations and depths, instead of manually reading through stacks of PDF reports — this directly targets the problem statement's own stated pain point of retrieval being "time-consuming and dependent on individual experience & memory."
- **Asset managers and OIL leadership:** a standing, queryable institutional-memory layer that survives staff turnover, addressing the same organizational risk the problem statement names directly.

**2. Quantified benefits — handled carefully, per the earlier research pass.** The old guide's specific dollar figures are not sourced to the project files or to an independently verifiable source for this context, so they are not carried forward. Two ways to present this section, in order of preference:

- **Preferred, safer framing:** state the industry baseline using only well-supported figures — stuck pipe and lost circulation together account for roughly a quarter of drilling non-productive time, with industry-wide costs estimated in the hundreds of millions of dollars annually. Present this explicitly as an industry estimate, not a claim about OIL specifically, and connect it to the system: "NWIS-Sentinel targets this exact category of NPT by giving early, explainable warning; the time-travel backtest is designed to quantify how much lead time this specific system provides, once run end-to-end on real historical data."
- **If a real backtest result exists by submission or demo time:** replace the generic industry figure with the computed lead-time result, and only then translate it into an estimated cost-avoidance range using a stated, cited day-rate assumption, clearly labeled as an estimate rather than a guaranteed saving.

- **Operational and safety benefits:** early detection of kicks and overpressure supports well-control safety, which is a well-established general benefit of early-warning drilling systems and does not need a specific invented number.
- **Knowledge preservation:** frame this around the problem statement's own language — institutional knowledge currently "dependent on individual experience & memory" — rather than an invented narrative.
- **Environmental co-benefit, stated qualitatively only:** avoided non-productive time reduces idle-rig fuel burn and associated emissions, and earlier lost-circulation detection reduces drilling-fluid loss; state this directionally, without a specific litres or tonnes figure unless it can be sourced or computed.

### PART B — DESIGN & VISUALIZATION DIRECTION

**Composition:** a three-persona architecture diagram as the dominant visual, with a small, visually distinct evidence strip beneath it — deliberately kept separate so sourced industry facts are never confused with project-specific projections.

**Primary diagram — Persona Impact Map:** one small central node representing NWIS-Sentinel, with three branches leading out to three persona nodes (Rig-floor driller, Drilling engineer, Asset manager), styled as a simple hub-and-spoke architecture diagram rather than a decorative illustration. Each persona node carries a short title and one line of benefit text pulled directly from Part A (five to eight words). This keeps the same node-and-connector visual language as Slides 2 through 4, so it still reads as an architecture diagram rather than a different genre of graphic.

**Secondary visual — Evidence Strip:** a single row beneath the diagram with two or three small badges carrying only sourced, cited facts, for example: "roughly 25 percent of drilling NPT — stuck pipe and lost circulation, industry estimate" and "250 million dollars plus per year — estimated industry-wide cost." Style these badges in a visually quieter, more muted treatment than the persona diagram above them, so the slide visually separates "what the system is projected to do" from "what independent industry literature already shows."

**Labels/callouts:** persona benefit lines capped at eight words; evidence badges capped at the numeric fact plus a two-to-four-word source tag.

**Hierarchy:** persona map is primary and largest; evidence strip is secondary, smaller, and visually muted.

**Density:** medium-low. Three well-sourced facts read as more credible than a longer list of unsourced ones — resist adding more badges.

**What not to include:** no dollar-per-well savings figure, no litres-of-diesel or tonnes-of-CO2 figure, no percentage reduction in planning time, unless the team can point to exactly where that number is computed or sourced.

---

## SLIDE 6 — RESEARCH AND REFERENCES

### PART A — DETAILED CONTENT

**1. Industry and academic literature**

Stuck-pipe and lost-circulation NPT statistics are corroborated across multiple independent sources; cite generally as industry and academic literature on drilling non-productive time rather than a single specific reference number unless the team has the exact source in hand and has verified it. The IADC Drilling Manual and Lexicon is a safe general reference for standard event-classification taxonomy. Any other specific paper citation (author, year, venue) should be double-checked against the actual source before it goes on a judge-facing slide — an unverifiable citation on the credibility slide undermines the whole deck more than one fewer reference would.

**2. Datasets actually used or planned, per `PLANNNNN.md`, all independently verified in this research pass:**

- **Equinor Volve Field Dataset** — a real North Sea field, released under Equinor's Open Data Licence; DDR text corpus available pre-processed as `bengsoon/volve_alpaca` on Hugging Face, 1,759 records (1,596 train, 163 test); real-time drilling parameter CSVs available via a public Kaggle mirror.
- **FORCE 2020 Lithology Prediction Dataset** — 118 real wells, Norwegian Continental Shelf, released by the Norwegian Offshore Directorate for a public machine learning competition, hosted on Zenodo under NOLD 2.0 license.
- **Synthetic DDR/WCR corpus** — LLM-generated, explicitly and consistently labeled synthetic in the source field of every record, used only to supplement hazard-type coverage the real datasets do not fully document.

**3. Technical and open-source foundation:**

spaCy, Hugging Face Transformers and sentence-transformers, Biopython (pairwise alignment), statsmodels (Wilson score intervals), Leaflet with OpenStreetMap or Google Maps Platform, and the WITSML/Energistics standard as the schema reference for the telemetry format Volve's real-time data originally used, and the format eRTMAC-equivalent systems use in production.

### PART B — DESIGN & VISUALIZATION DIRECTION

**Composition:** the calmest slide in the deck by design — a three-tier stacked reference structure, still an architecture-style diagram (tiers as containers, not a plain bibliography list), but with almost no additional illustration.

**Primary diagram — Tiered Source Structure:** three horizontal bands stacked top to bottom, each a labeled container in the deck's accent tint, matching the swimlane treatment used on Slide 3 for visual consistency:

- Top band, "Literature" — two or three compact citation nodes, each a short title plus a one-line descriptor, no full citation block on the slide itself.
- Middle band, "Datasets" — the visually largest band, since this is the strongest evidence: three nodes (Volve, FORCE 2020, Synthetic corpus), each carrying the small filled or hollow provenance dot used throughout the deck, plus one factual badge each (Volve: "1,759 DDRs"; FORCE 2020: "118 real wells"; Synthetic: "target 200 to 400 reports, 40 to 60 wells").
- Bottom band, "Open-source and standards" — a small row of tool names only (spaCy, Hugging Face, Biopython, WITSML), no accompanying description.

**Supporting visual:** none beyond the provenance dots already used elsewhere — this slide should feel quiet and reference-like, not compete visually with Slides 2 or 3.

**Labels/callouts:** dataset nodes may carry one factual badge each, since these are independently verified numbers rather than projections.

**Hierarchy:** the Datasets band is visually dominant, since it is the strongest and most concrete evidence; Literature and Open-source bands are smaller and quieter.

**Density:** low to medium. This slide's job is trust, not persuasion — every citation shown should be one the team can defend if asked to show the source.

**What not to include:** no re-explanation of the architecture (already covered on Slide 3); no unverified citations; no additional decorative graphics beyond the tiered structure itself.

---

## Summary of What Changed From the Old Guide

- Replaced fabricated implementation/validation metrics (159 wells, 1,959 events, 63 incidents, >91% precision, <150 ms latency, 18-class ontology, XGBoost + Bi-LSTM, SHAP/LIME, PostGIS/Mapbox) with what `PLANNNNN.md` actually specifies as the target architecture: 5 hazard types, statistical-first precursor detection, AHP-weighted similarity, Wilson confidence intervals, citation-checked LLM briefings, Google Maps/Leaflet fallback stack.
- Corrected the flagship backtest fact from a fabricated depth/timestamp on well 15/9-19A to the real, sourced stuck-pipe/severed-string event on well 15/9-19B, with an explicit instruction not to state a specific lead-time figure unless computed.
- Removed unsourced economic and environmental figures (70 percent planning-time reduction, 800k to 2.5 million dollars per incident, 40,000 litres diesel per event) and replaced them with the one set of figures that is independently corroborated (roughly 25 percent of drilling NPT, 250 million dollars plus per year industry-wide), explicitly framed as an industry estimate rather than a project-specific claim.
- Replaced every "professional enterprise schematic" instruction with a concrete, slide-sized architecture diagram per slide — phase pipeline, master swimlane schematic, risk/mitigation bridge, persona hub-and-spoke, tiered source structure — each using short node labels rather than dense text blocks, and each reusing the same color, icon, and provenance-dot system so the five slides read as one deck.
- Removed all emoji-based section markers and iconography language from the design instructions.
