# Module 1 Walkthrough: Real OCR and the MiniLM Language-Model Layer

> SIH 2026 · eRTMAC-NWIS (NWIS-Sentinel) · Module 1, live DDR ingestion
> This document covers **two changes to Module 1 only**: (1) replacing the simulated OCR with real GPU OCR, and (2) adding a language-model (MiniLM) layer to the event extractor. Nothing else in the project is described here.

---

## 1. Where the two changes sit

Module 1 reads drilling reports (DDRs) and turns them into structured events such as "stuck pipe at 619 m". Before these changes:

- The upload page on `/module1` was a **scripted animation**. The uploaded file was ignored, and the page replayed canned logs and six hard-coded events for a fictional well.
- The event extractor was **keyword + regex only**. It finds an event only when a report happens to contain one of its listed phrases.

After the changes, a user can upload a real DDR PDF and the system will **read it with OCR, find the events with a hybrid keyword + language-model extractor, and show the real results**, while the original animation keeps playing, driven by real progress.

```
 Upload PDF ──► Phase 1: OCR (PaddleOCR, GPU) ──► page text ──► Phase 2: NLP (keyword + MiniLM) ──► events
                   │                                                      │
                   └── live % badge + scan animation                      └── same 15-field event format as before
```

Both phases are independent worker processes, started and supervised by the Module 1 server (`module1/server.py`).

---

# Part A: Phase 1, Real OCR

## 2. What changed for OCR

| | Before | After |
|---|---|---|
| Uploaded file | Ignored | Saved, validated, and processed |
| Text on screen | Pre-written canned text | Text actually recognised from your pages |
| Progress | A fixed 10-second timeline | Real page-by-page progress (e.g. "OCR 37% · page 35/93") |
| Events shown | 6 hard-coded events for "FORGE-58-32" | Events extracted from your document |
| Animation | Scan line, highlights, token stream | **Unchanged**, now runs for the whole real job |

The old simulation is not deleted. It lives on under a **"Show Demo"** button (labelled "DEMO · SIMULATED") that runs entirely in the browser with no server calls. The upload path and the demo path never touch each other.

## 3. The OCR engine and why

| Option | Verdict |
|---|---|
| **PaddleOCR 2.7.3 (PP-OCRv4)** | **Chosen.** Runs on the NVIDIA GPU (RTX 4060 here), is accurate on form-style DDR pages, and installs with pip. |
| Tesseract + OpenCV | Needs a separate system install outside pip; not on the target machine. |
| EasyOCR | Needs GPU PyTorch for usable speed, which would make installation much heavier. |
| RapidOCR (same models via ONNX, CPU) | Tried as a fallback and removed: 60-90 s per page, lower confidence (~0.83), conflicting OpenCV requirement. |

PaddleOCR's pipeline has three small neural networks: a **detector** (finds text regions), an **angle classifier** (fixes rotated text) and a **recogniser** (reads each region). If no GPU is visible, it falls back to the CPU, which is slower but gives the same output.

## 4. How the OCR runs

1. **Upload.** `POST /module1/upload` checks that the file is a real PDF (type, size up to 100 MB, page count) and saves it under `data/runtime/module1/uploads/`.
2. **Render.** The OCR worker (`module1/ocr_worker.py`) opens the PDF with PyMuPDF and renders each page to an image at **200 dpi**.
3. **Recognise.** PaddleOCR returns text boxes with a confidence each. The worker rebuilds **reading order**: boxes are sorted top-to-bottom, grouped into lines by vertical position, then ordered left-to-right within each line.
4. **Report progress.** After every page the worker sends the text, character count, mean confidence and time. The server turns this into a job percentage that the browser polls every 300 ms.
5. **Hand off.** When all pages are done, the page texts go to the NLP worker (Part B).

Every page is OCR'd, even if the PDF already has a text layer. This keeps behaviour identical for scanned reports. If PaddleOCR cannot load at all, the server falls back to the PDF's own text layer and labels the result **"NOT OCR"** in the UI rather than pretending.

**Progress bar mapping.** OCR fills 5%-80% of the bar (proportional to pages done), segmentation 81%, NLP 82%-97%, writing results 98%, done 100%.

**Why a separate process.** The OCR runs in its own worker, not inside the web server. A long OCR job therefore never blocks the API, and PaddleOCR (which cannot share a process with PyTorch) stays isolated from the language model. The worker talks to the server with one JSON message per line over stdin/stdout, and it exits automatically if the server dies.

**GPU setup.** On Windows only an NVIDIA driver is needed. The CUDA libraries Paddle uses (cuDNN 8, cuBLAS 11) come from `requirements.txt` as ordinary pip packages, and the worker adds their folders to the DLL search path at start-up.

## 5. OCR results

Measured on the 93-page Utah FORGE 78B-32 report (`assets/Utah_FORGE_DDRs.pdf`):

| Metric | Value |
|---|---|
| Characters recovered | 242,693 (96% of the 251,773 in the PDF's own text layer) |
| Mean recognition confidence | 0.984 |
| Speed, GPU otherwise idle | ~1.2 s per dense page (93 pages in ~106 s) |
| Speed, laptop busy with browser and all other services | 1.5 s median, ~8 s worst page (~284 s total) |
| End-to-end job including NLP, last verified run | 113 s |

---

# Part B: Phase 2, The MiniLM Language-Model Layer

## 6. The problem

The original extractor (`nlp_rules.py`, moved unchanged out of `p1_full_pipeline.py`) classifies a report into one of **18 event types** by looking for keywords such as "stuck pipe" or "lost circulation". Real reports use drilling jargon the list does not contain:

- "hole **packed off** around the BHA" (stuck pipe)
- "**pit gain** 12 bbl, flow check positive" (kick)
- "**took weight** at 2,210 m and reamed" (tight hole)
- "**pulled 40k over**" (overpull)

On our test set the keyword rules found only **30% of the hazard sentences**. The goal was to improve recall without breaking the output format and without a labelled training set, because no labelled DDR data exists for this project.

**Constraints that shaped the choice**

1. **No labelled data**, so any model must work zero-shot (no training). Models that need fine-tuning to be useful were excluded from this phase.
2. **The output must stay identical**: the same 15-field event record that Modules 2-5 already consume.
3. **Existing committed data must not change.** The language model runs on live uploads only; the committed `events.jsonl` and everything built on it are untouched.
4. **It must run on a laptop**, offline, and be fast next to OCR.

## 7. The candidates

Six approaches were tested, chosen to cover the realistic range of "language model" options:

| Candidate | What it is | How it was used here |
|---|---|---|
| **Keyword rules** | The existing `classify_event` | The baseline to beat |
| **BERT-base** (110M parameters) | General-purpose encoder | Sentence embeddings, matched against class descriptions |
| **RoBERTa-base** (125M) | BERT trained longer on more data | Same |
| **DeBERTa-v3-base** (184M) | Stronger general encoder | Same |
| **GLiNER medium v2.1** (195M, DeBERTa-v3 backbone) | Zero-shot *span* tagger: finds pieces of text matching a label you give in plain English | Event types supplied as natural-language labels |
| **all-MiniLM-L6-v2** (23M) | A small model *trained specifically so that similar sentences get similar vectors* | Sentence embeddings, matched against class descriptions |

**Considered but not tested, and why**

| Option | Reason excluded |
|---|---|
| Fine-tuned BERT / RoBERTa / DeBERTa token classifiers | Need thousands of BIO-labelled sentences. We have none, and training on our own keyword labels would only relearn the keywords, the very ceiling we want to break. |
| Domain encoders (PetroBERT, GeoBERT, GEOBERTje, SciBERT) | Trained on Portuguese, Chinese, Dutch or academic text. No public English drilling encoder exists. |
| Domain-adaptive pre-training on the 1,759 Volve reports | Small, LLM-summarised corpus, and it would still need labels afterwards. Listed as future work. |
| Cloud LLM (Qwen-72B, Gemini) per sentence | Needs internet and API keys, adds latency per sentence, and is non-deterministic. The project must work offline. |

## 8. How the candidates were tested

The evaluation is a script, **`module1/eval_model_selection.py`**, which is committed so the choice can be reproduced and audited. Its full results are saved in `module1/outputs/model_selection.json`.

**Test set: 60 sentences covering all 18 classes**

| Part | Count | Source |
|---|---|---|
| Hazard sentences | 43 | 2-4 per hazard class |
| Routine sentences | 17 | Normal operations ("circulated bottoms up", "pressure tested BOP"), including look-alikes such as "kick-off plug" |
| From the real Volve DDR corpus | 33 | Verbatim sentences |
| Hand-written edge cases | 27 | Paraphrase-heavy ("packed off", "pit gain", "pulled 40k over"), because Volve has few or no examples of kick, overpressure or torque spike |

**How embedding models classify (BERT, RoBERTa, DeBERTa, MiniLM).** Each of the 18 classes is described by a few short phrases ("prototypes", for example "total losses, no returns to surface"). The sentence and the prototypes are turned into vectors by the model, and the sentence gets the class of the **closest prototype** (cosine similarity). "Routine operations" has its own prototypes, so it competes on equal terms, and there is no threshold to tune on the test set. For BERT, RoBERTa and DeBERTa the vector is the average of the word vectors, which is the standard zero-shot recipe.

**GLiNER** instead scans the sentence for spans matching event labels (for example "total loss of returns") and takes the best-scoring one; no span means routine.

**Two fairness rules**
- The prototype phrases were written as *descriptions of each class*, deliberately not copied from the test sentences.
- Every model was scored twice: on its own, and **as a hybrid with the keyword rules**, as it would be deployed.

**Metrics.** *Macro-F1* is the F1 score averaged over all 18 classes, so rare classes count as much as common ones. *Hazard recall* is the share of real hazard sentences that were flagged as some hazard. *Routine false-alarm rate* is the share of routine sentences wrongly flagged as hazards.

## 9. Results

### 9.1 Event typing, 60 sentences

| Candidate | Size | Speed (GPU) | Macro-F1 alone | Macro-F1 + keywords | Hazard recall alone | Routine false alarms alone |
|---|---|---|---|---|---|---|
| Keyword rules (baseline) | n/a | instant | 0.277 | n/a | 0.302 | 0.235 |
| BERT-base | 110M | 2.6 ms | 0.522 | 0.583 | 0.884 | 0.353 |
| RoBERTa-base | 125M | 2.6 ms | 0.454 | 0.544 | 0.930 | 0.647 |
| DeBERTa-v3-base | 184M | 10.3 ms | 0.189 | 0.364 | 0.814 | 0.824 |
| GLiNER medium v2.1 | 195M | 41.4 ms | 0.430 | 0.462 | 0.465 | 0.118 |
| **all-MiniLM-L6-v2** | **23M** | **3.3 ms** | **0.771** | **0.737** | **0.884** | 0.412 |

("+ keywords" means the keyword rules decide when they fire, and the model fills in when they say routine.)

**Held-out check.** To guard against tuning on the test set, the sentences were split into a dev half (34) and a test half (26). A similarity margin was tuned on the dev half only, and the test half was scored once. Macro-F1 on the test half:

| Candidate | Keyword | Model alone | Model + keywords |
|---|---|---|---|
| BERT | 0.107 | 0.501 | 0.425 |
| RoBERTa | 0.107 | 0.529 | 0.448 |
| DeBERTa-v3 | 0.107 | 0.106 | 0.139 |
| **MiniLM** | 0.107 | **0.690** | **0.648** |

GLiNER is not part of this split because it has no similarity margin to tune. With only 26 test sentences the absolute values are noisy, but the ranking is the same as on the full set.

### 9.2 MiniLM per-class results (full 60 sentences, alone)

| Event class | Precision | Recall | F1 | Support | Keyword F1 |
|---|---|---|---|---|---|
| Partial mud loss | 1.00 | 1.00 | 1.00 | 3 | 0.00 |
| Total mud loss | 1.00 | 0.33 | 0.50 | 3 | 0.00 |
| LCM applied | 1.00 | 0.33 | 0.50 | 3 | 0.80 |
| Circulation restored | 0.67 | 1.00 | 0.80 | 2 | 0.00 |
| Stuck pipe | 0.50 | 0.33 | 0.40 | 3 | 0.40 |
| Differential sticking | 1.00 | 1.00 | 1.00 | 2 | 0.00 |
| Tight hole | 0.75 | 0.75 | 0.75 | 4 | 0.29 |
| Jarring | 0.50 | 1.00 | 0.67 | 2 | 0.67 |
| Fishing | 0.50 | 0.67 | 0.57 | 3 | 0.50 |
| Kick | 0.67 | 0.67 | 0.67 | 3 | 0.00 |
| Gas influx | 1.00 | 1.00 | 1.00 | 2 | 0.00 |
| BOP shut-in | 0.67 | 1.00 | 0.80 | 2 | 0.00 |
| Overpressure detected | 1.00 | 1.00 | 1.00 | 2 | 0.00 |
| Torque up | 1.00 | 1.00 | 1.00 | 2 | 0.57 |
| Torque spike | 0.67 | 1.00 | 0.80 | 2 | 0.67 |
| Cementing failure | 1.00 | 1.00 | 1.00 | 3 | 0.00 |
| Waiting on cement | 0.67 | 1.00 | 0.80 | 2 | 0.67 |
| Routine drilling | 0.67 | 0.59 | 0.63 | 17 | 0.43 |

Nine classes score F1 = 0 with keywords alone (partial loss, total loss, circulation restored, differential sticking, kick, gas influx, BOP shut-in, overpressure, cementing failure). MiniLM recovers all of them, most of them perfectly. Its weak spots are stuck pipe (confused with tight hole) and total mud loss (confused with partial loss), which are genuinely close neighbours.

### 9.3 Why MiniLM won

- **Accuracy.** It was clearly the best: 0.77 vs 0.52 for the next model (BERT), with the same ordering on the held-out half.
- **Why the bigger models lost.** BERT, RoBERTa and DeBERTa are trained to predict masked words, not to put similar sentences close together, so their raw vectors are not built for similarity matching. They would need labelled fine-tuning to compete, which is exactly what we do not have. DeBERTa's raw vectors were nearly useless here (0.19).
- **GLiNER lost** because it extracts *pieces of text*, which is a poor fit for deciding what a whole sentence is about. It missed more than half of the hazard sentences and was about 13x slower than MiniLM. It is very conservative though (12% routine false alarms), which is why it remains a candidate once a labelled set exists.
- **Cost.** MiniLM is the smallest model (23M parameters, roughly 90 MB) and among the fastest. It also runs well on a CPU.
- **Fit.** Modules 4 and 5 already use the same model for retrieval, so there is no new model to ship or maintain.

The rule agreed in advance was: if GLiNER does not come out ahead, use the better model, and if two are within noise, prefer the cheaper. MiniLM was both better and cheaper, so no tie-break was needed.

### 9.4 Field extraction (depth, mud weight, volume, formation)

A separate 20-sentence test compared ways of extracting the numeric fields.

| Method | Depth | Mud weight | Volume | Formation | All fields | Time/sentence |
|---|---|---|---|---|---|---|
| Original regex (metres only, no unit conversion) | 0.70 | 0.75 | 0.80 | 0.75 | 0.75 | 0.05 ms |
| **Unit-aware regex (`units.py`)** | **1.00** | **1.00** | **1.00** | **1.00** | **1.00** | 0.1 ms |
| Unit-aware regex + GLiNER filling gaps | 1.00 | 1.00 | 1.00 | 0.85 | 0.96 | ~47 ms |

GLiNER added nothing and occasionally filled in a wrong value, so field extraction stays plain unit-aware regex. This is the second reason **GLiNER is not part of the pipeline**. Caveat: the same person wrote the test sentences and the parsers, so the 1.00 is optimistic.

## 10. How MiniLM is used in the final system

**MiniLM is the only language model in Module 1.** It does not replace the keyword rules; it adds a second opinion. The code is in `module1/nlp_engine.py` (engine), `module1/event_prototypes.py` (class descriptions) and `module1/units.py` (field parsing).

### 10.1 Step by step

For an OCR'd document:

1. **Segment.** Pages are grouped into daily reports using the "Report For <date>" header on each page. Pages with no header continue the previous report. If no headers exist at all, each page is one report.
2. **Clean.** Lines that repeat across many pages (form labels, table headers, page footers) are removed, as are headings and boilerplate such as safety summaries and inventory tables. Time-log rows lose their time and hour columns.
3. **Split sentences.** A rule-based splitter is used, because the standard NLTK splitter fragments technical text.
4. **Keyword pass (per sentence).** The original rules, with two protections:
   - **Negation:** "no tight spots" or "no losses" is not an event.
   - **Known traps:** "fishing neck", "kick-off plug", "torque test", "torqued connections", "drilling jar" and similar are ignored.
5. **Semantic pass (per sentence).** DDR abbreviations are expanded first (FIT to "formation integrity test", POOH to "pull out of hole", WOC to "waiting on cement"), because a general model does not know them. MiniLM then embeds the sentence and compares it with the prototype phrases of all 18 classes (3-5 for each hazard class, 18 for routine operations).
6. **Decision rule.** For each sentence:

   | Situation | Result | Confidence |
   |---|---|---|
   | Keyword fires and MiniLM agrees | Keyword's event ("both") | 0.92 |
   | Keyword fires, MiniLM disagrees or is unsure | Keyword's event | 0.85 |
   | No keyword, but the best hazard class beats the best routine class by at least the **margin 0.19** (and no sentence-level negation) | MiniLM's event ("semantic") | 0.55 to 0.80, scaled by how far past the margin it is |
   | Neither | Routine | 0.95 |

7. **Extract fields** with the unit-aware parsers, looking first in the event's own sentence, then its neighbours, then the report header:
   - depth: feet to metres (x 0.3048);
   - mud weight: SG (x 8.33) and lb/ft3 (/ 7.48) to ppg;
   - volume: m3 to bbl (x 6.29);
   - NPT hours and formation names.

   Rates such as "m/hr" are never mistaken for depths.
8. **Build records.** One record per distinct event type per daily report, using **exactly the same 15 fields as `events.jsonl`**. A report with no hazard gets one routine record. The reason each event was chosen (matched keyword, similarity score, margin) is returned beside the records, not inside them, so the format is untouched.
9. **Save.** Results are written to `results/module1_outputs/uploads/<job>.jsonl` plus a `_meta.json` (git-ignored). Uploads are deliberately **not** fed to Modules 2-5.

### 10.2 Why the margin is 0.19

The 0.771 macro-F1 in section 9 is the "pick the closest class" setting, which flags 41% of routine test sentences as hazards. Real drilling reports are mostly routine lines, so that would drown users in false alarms. In production, MiniLM may only create an event when the best hazard match beats the "routine" match by a margin. The operating curve:

| Margin | Hazard sentences caught | Routine sentences wrongly flagged | Share of all 6,802 Volve sentences flagged |
|---|---|---|---|
| 0.10 | 74% | 24% | 7.7% |
| 0.13 | 70% | 6% | 5.1% |
| 0.16 | 67% | 0% | 3.6% |
| **0.19 (used)** | **61%** | **0%** | **2.3%** |
| 0.22 | 56% | 0% | 1.7% |
| 0.25 | 49% | 0% | 1.2% |
| 0.28 | 40% | 0% | 0.9% |

0.19 was chosen as a point with no false alarms on the routine test sentences and with only about 2% of real Volve sentences firing. Recall is 61%, against 30% for keywords alone.

### 10.3 Checks on the final system

| Check | Result |
|---|---|
| **Refactor safety:** the moved rules re-run on all 1,759 Volve reports | Reproduce the committed `events.jsonl` exactly |
| **Jargon smoke test** (20 sentences keywords miss, plus 10 routine) | Keywords catch 2 of 20; hybrid catches 15 of 20; 0 of 10 routine sentences flagged |
| **Real document**, 93-page Utah FORGE report | 14 hazard events (7 of them found by the semantic layer) out of 38 records |
| Manual review of those 14 | 11 plausible (tight hole, stuck pipe, overpull, waiting on cement, high motor torque, recovered junk); 3 false positives, all equipment mentions |
| Output schema | Exactly the 15 fields of `events.jsonl` |
| Time for MiniLM on the 93-page report | ~9 s on CPU, ~0.8 s on GPU, identical output |

The CPU is used by default. OCR takes minutes, so the extra seconds are not noticeable, and it keeps the install small.

### 10.4 Honest limitations

- The 60 evaluation sentences were labelled by one person. They are a **screening set, not a gold standard**.
- The margin was chosen with the whole set visible, so the 61% recall is optimistic.
- The real-document review was done by hand on one report.
- The next step is a 300-500 sentence gold set labelled by two annotators. That would give an unbiased accuracy figure and allow fine-tuning; GLiNER and the larger encoders become worth retesting at that point.

---

# Part C: Seeing it work

## 11. Running it

```bash
# one command from your IDE terminal (repo root or NLP/nlp_task_ddr)
python NLP/nlp_task_ddr/run_all_modules.py
# or double-click start_all.bat (creates the venv and installs requirements first)
```

Then open **http://localhost:5000/module1**.

1. **Live path:** click "Process sample: Utah_FORGE_DDRs.pdf" or drop in your own DDR PDF. The scan animation runs for the whole job, the badge shows the real percentage and page, the token stream shows recognised text, the log shows real timings, and the results panel shows the extracted well metadata and events (hover an event for its source sentence).
2. **Demo path:** click **Show Demo** for the original scripted replay. It is badged "DEMO · SIMULATED" and makes no server calls.
3. **Health:** `http://localhost:5000/module1/health` reports the OCR engine and device, the semantic model, the margin and whether both workers are ready.

## 12. File guide

| File (under `NLP/nlp_task_ddr/module1/`) | Role |
|---|---|
| `server.py` | Upload API, job queue, progress tracking; supervises both workers |
| `ocr_worker.py` | Phase 1: PDF to image, PaddleOCR, reading order, per-page progress |
| `nlp_worker.py` | Phase 2: keeps the MiniLM engine loaded; runs extraction jobs |
| `nlp_engine.py` | Phase 2 engine: segmentation, keyword + semantic decision, record building |
| `event_prototypes.py` | The class-description phrases and the abbreviation list |
| `units.py` | Unit-aware parsers for depth, mud weight, volume, NPT, formation |
| `nlp_rules.py` | The original keyword/regex rules (unchanged, moved here) |
| `eval_model_selection.py` | The reproducible model comparison behind section 9 |
| `outputs/model_selection.json` | Full numbers from the last full comparison run |
| `test_nlp_engine.py` | Tests: rules reproduce `events.jsonl`, schema, units, traps, semantic recall |
| `module1.html` | The page: live path plus the client-side "Show Demo" |

To re-run the comparison: BERT, RoBERTa and MiniLM work with the normal install. GLiNER and DeBERTa need `pip install gliner==0.2.30 sentencepiece==0.2.0`; without them those rows are skipped and the output goes to `model_selection_partial.json`, so the committed full table is kept.

```bash
cd NLP/nlp_task_ddr
python module1/eval_model_selection.py
python -m pytest module1/        # Module 1 tests
```
