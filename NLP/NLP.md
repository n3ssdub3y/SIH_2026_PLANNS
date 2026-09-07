# NLP Course Project — Research-Backed Recommendations
### 5-Person Team | Flagship Selection Report

---

## How this was researched

Before ranking anything, I pulled current literature (2024–2026) and dataset availability across nine candidate problem spaces: legal contract review, cyber threat intelligence extraction, scientific citation verification, systematic-review/PICO automation, legal-document simplification, code-mixed/Indian-language grievance processing, regulatory compliance gap detection, cross-document event/claim provenance, and scam-victim forensic analysis. Four were dropped outright (see "Rejected" section) for being oversaturated, over-served by commercial tools, or too thin on data. Five survived scrutiny and are ranked below.

### Research Methodology & Candidate Screening

| Scope Dimension | Details & Funnel Methodology |
| :--- | :--- |
| **Literature Horizon** | Current literature (2024–2026) and dataset availability |
| **Candidate Problem Spaces Evaluated (9 Total)** | 1. Legal contract review<br>2. Cyber threat intelligence extraction<br>3. Scientific citation verification<br>4. Systematic-review/PICO automation<br>5. Legal-document simplification<br>6. Code-mixed/Indian-language grievance processing<br>7. Regulatory compliance gap detection<br>8. Cross-document event/claim provenance<br>9. Scam-victim forensic analysis |
| **Screening Outcome** | • **4 Dropped Outright**: Oversaturated, over-served by commercial tools, or too thin on data (detailed in *Considered and Rejected* section)<br>• **5 Survived Scrutiny**: High technical depth and feasible for a 5-person team, ranked below |

---

## Ranking at a glance

| Rank | Project | NLP Depth | Novelty | Data Availability | Feasibility (5 people) | Resume Value |
|:---:|:---|:---:|:---:|:---|:---:|:---:|
| **1** | Scam-Victim Forensic Schema Extractor | High | Very High | Good (public, needs assembly) | High | Very High |
| **2** | Citation-Integrity Verifier | High | High | Very Good (ready-made benchmark) | Very High | High |
| **3** | DPDP Act Compliance Gap Detector | Medium-High | Very High (timing) | Medium (build-your-own corpus) | Medium | Very High |
| **4** | Cross-Document Claim Provenance Tracker | High | High | Medium | Medium | High |
| **5** | Multi-Report CTI Campaign Aggregator | High | Medium | Good | Medium | Medium-High |

> **Recommendation:** If you want one flagship pick: **#1**. Reasoning is detailed at the bottom of this document.

---

# 1. Scam-Victim Forensic Schema Extractor — *Recommended Flagship*

### Project Profile & Specifications

| Dimension | Specification / Description |
| :--- | :--- |
| **Problem & Target Users** | Victim-facing fraud reports (cybercrime helplines, bank fraud desks, "romance scam" and "pig-butchering" hotlines, consumer-protection trackers) collect huge volumes of free-text narratives describing how a scam unfolded. Investigators and helpline staff currently read these manually to identify *which manipulation tactics were used* (urgency, authority impersonation, romance grooming, fake investment platforms) and *what actionable evidence is present* (crypto wallet addresses, payment rails, platform names). This is slow, inconsistent, and — critically — most systems today only capture contact metadata and dollar amounts, not the psychological/behavioral pattern of the scam, which is what actually helps investigators link cases and helps helpline agents ask the right follow-up questions in real time.<br><br>Direct users: national cybercrime helplines (India's 1930/cybercrime.gov.in is a concrete example), bank fraud-investigation teams, victim-support NGOs, and trust-and-safety teams at fintech/crypto platforms. |
| **Why It Matters** | Global scam losses are now measured in the tens of billions annually (FTC alone reported **$5.7B lost in 2024**, up 125% year-over-year), and India specifically logs a high and rising volume of cybercrime complaints per capita. Manual triage cannot scale with this volume, and generic "fraud/spam classifiers" don't capture *why* a scam worked — which is what's needed for both investigation and victim-support redesign. |
| **The Identified Gap** | The Forensic Schema paper's own finding is the opening: **manipulation-technique detection is reliable, but the *actionable forensic detail* supporting each finding is highly inconsistent across victim narratives, and blockchain/crypto identifiers are nearly absent** unless specifically prompted for. In other words — the extraction half of the problem is close to solved; the half nobody has built is a system that identifies *which* details are missing from a given narrative and actively asks the right follow-up question to close that gap. No public system does structured extraction *and* adaptive follow-up-question generation together. |
| **Expected Prototype Output** | A web tool where a victim/agent pastes or dictates a scam narrative and receives: a structured forensic case file (schema fields populated with confidence + evidence spans), a flagged list of missing/weak evidence fields, and 1–3 generated follow-up questions to ask next. A secondary "campaign view" clusters similar cases. |
| **Novelty vs. Generic Projects** | This is explicitly **not** spam/fraud binary detection (which the prompt asked to avoid) — the output is a structured forensic case file plus an interactive gap-closing mechanism, grounded in a specific, named limitation from a 2026 paper. Very few student projects will have found and be building on a gap this recent. |
| **Feasibility (5-Person Team)** | Realistic. Split naturally: (1) data collection/scraping + schema adaptation, (2) extraction model fine-tuning, (3) gap-detection + question-generation module, (4) evaluation/annotation coordination, (5) frontend + campaign-clustering view. No need to train models from scratch — pretrained LLMs + fine-tuning/LoRA is sufficient and matches the reference papers' own methodology. |
| **Resume & Interview Value** | Very high. "We read the newest fraud-forensics literature, found a documented gap (inconsistent evidentiary detail in victim reports), and built the missing half of the pipeline — an adaptive follow-up system — evaluated against real annotator-agreement baselines" is a strong, specific, defensible story, and ties naturally to India's cybercrime context if you want that framing. |

### Existing Work & Literature Baseline

| Prior Art / Benchmark | Description & Findings |
| :--- | :--- |
| ****PsyScam** (2025)** | first benchmark grounding scam narratives in 9 cognitive/psychological-technique categories, built from 6 public scam-reporting platforms; defines PT classification, "scam completion," and "scam augmentation" tasks. |
| ****PreScam** (2026)** | studies how manipulation techniques *sequence* over a scam conversation rather than treating a report as a static bag of tactics. |
| ****Forensic Schema for Psychological Manipulation in Cyber Fraud** (Wen et al., 2026, U. Washington Tacoma)** | the closest prior art: a 4-category, 35-question forensic schema with 11 manipulation indicators + crypto-evidence fields, applied via LLM annotation to **10,994 real victim reports**, validated against two human annotators (LLM–human κ = 0.69, matching human–human κ = 0.68). |
| ****Pig-Butchering Scams exploratory study** (2024)** | manually coded 2,570 victim narratives from Chainabuse and Crypto Scam Tracker across contact method, relationship-building, fund-extraction technique, and psychological manipulation. |
| • | Adjacent (but generic) work: Hinglish cybercrime *classification* using HingBERT/HingRoBERTa on India's I4C hackathon data — useful as a baseline for what "shallow classification" looks like, and exactly the kind of output this project should go beyond. |

### Proposed NLP Technical Pipeline

| Stage / Step | Module Name | Technical Methodology & Approach |
| :---: | :--- | :--- |
| **Step 1** | ****Schema-guided structured extraction**** | fine-tune/prompt an open LLM (e.g., Llama-3-8B or Mistral-7B, instruction-tuned) to map a free-text scam narrative onto a fixed schema (contact vector, relationship-building tactic, manipulation techniques used, financial instrument, platform, evidence completeness per field). |
| **Step 2** | ****Detail-gap detector**** | a lightweight classifier/rule-hybrid that flags schema fields with low "evidentiary support" (e.g., "cryptocurrency mentioned but no wallet ID extracted"). |
| **Step 3** | ****Adaptive follow-up question generator**** | given the gap map, generate 1–3 targeted, non-leading follow-up questions (this is the genuinely novel component — closing the gap the source paper identified) — implementable as a constrained generation module conditioned on the missing-field schema, evaluated for question relevance/specificity. |
| **Step 4** | **Optional stretch** | cluster extracted schemas across reports to surface *scam campaigns* (same tactics/wallets reused across victims) — gives investigators a leads dashboard, not just per-report output. |

### Data Plan & Corpus Strategy

| Stream / Focus Area | Dataset Strategy & Resource Details |
| :--- | :--- |
| **Primary** | assemble a multi-source corpus from **PsyScam's public dataset** (github.com/KiteFlyKid/PsyScam), **Chainabuse** and **Crypto Scam Tracker** abuse reports (public, scrapeable per the pig-butchering study's methodology), and **BBB Scam Tracker** / **IC3** public narrative excerpts. |
| **Aspect 2** | Use the Forensic Schema paper's 4-category/35-question schema as your annotation starting point (adapt/simplify to fit a semester timeline) rather than designing one from scratch. |
| **Aspect 3** | LLM-assisted annotation with human spot-checking (as the source paper did) is a realistic, defensible annotation strategy for a student team — document inter-annotator agreement (κ) the same way the reference papers do. |
| **Aspect 4** | If pursuing the India angle specifically, note that I4C's National Cyber Crime Reporting Portal data is *not* openly downloadable outside sanctioned hackathons — treat this as a stretch/context source, not your primary corpus. |

### Evaluation Framework & Benchmarks

| Evaluation Dimension | Benchmark Protocol & Success Metrics |
| :--- | :--- |
| **Schema-field extraction** | per-field F1/accuracy against held-out human-annotated narratives; report macro-F1 across the 11 manipulation indicators. |
| **Agreement** | LLM-vs-human κ, benchmarked against the 0.69 figure from the Forensic Schema paper as your baseline to beat or match. |
| **Follow-up question quality** | human evaluation (relevance, non-leading-ness, whether it actually elicits the missing field) — this is your headline novel metric since no baseline exists for it. |
| **Downstream utility** | simulate investigator triage time reduction (manual field-completion time vs. system-assisted). |

### Key References & Literature Links

| # | Citation / Paper Reference |
| :---: | :--- |
| 1 | Wen et al., *Forensic Schema for Psychological Manipulation in Cyber Fraud: LLM-Driven Victim Reports Analysis*, arXiv:2607.07751 (2026) |
| 2 | *PsyScam: A Benchmark for Psychological Techniques in Real-World Scams*, arXiv:2505.15017 (2025) — github.com/KiteFlyKid/PsyScam |
| 3 | *PreScam: A Benchmark for Predicting Scam Progression from Early Conversations*, arXiv:2605.12243 (2026) |
| 4 | *An Explorative Study of Pig Butchering Scams*, arXiv:2412.15423 (2024) |
| 5 | Rani et al., *Automated Classification of Cybercrime Complaints using Transformer-based Language Models for Hinglish Texts*, arXiv:2412.16614 (2024) — baseline reference for "shallow classification"<br><br>--- |

---

# 2. Citation-Integrity Verifier

### Project Profile & Specifications

| Dimension | Specification / Description |
| :--- | :--- |
| **Problem & Target Users** | When a paper cites a source to support a claim, the citation is often bibliographically valid but **semantically misaligned or outright wrong** — the cited work doesn't actually say what's claimed. This is distinct from "does this claim match reality" (fact-checking); it's "does this citation's target actually support this specific sentence." Users: journal editors/peer reviewers, PhD students and labs doing literature reviews, publishers building integrity-screening tools, and — increasingly — anyone reviewing AI-assisted writing, where LLM-generated citations are a known failure mode. |
| **Why It Matters** | A 2024 biomedical corpus study found **39.18% of annotated citation instances contained accuracy errors** — nearly 2 in 5. As LLM-assisted paper writing grows, unchecked citation drift is a rising integrity risk, not a shrinking one. |
| **The Identified Gap** | The Citation-Integrity paper's own best system — a retriever + fine-tuned claim-verification model — reaches only **0.59 micro-F1 / 0.52 macro-F1**; GPT-4 in-context learning does *better* on accurate citations but *worse* on catching errors (0.65 micro-F1, but only 0.45 macro-F1, meaning it under-catches the erroneous class that matters most). There is no deployed, usable tool that flags misaligned citations while a paper is being written or reviewed — only research-stage classifiers evaluated on held-out corpora. |
| **Expected Prototype Output** | A tool that takes a paper (or a citing sentence + BibTeX/DOI) and returns a per-citation accuracy verdict with a highlighted evidence span from the cited work and a confidence/severity score — usable as a Word/LaTeX plugin concept or a standalone web checker. |
| **Novelty vs. Generic Projects** | Not a "PDF summarizer" or generic fact-checker — it's a narrowly scoped, benchmarked task (claim–citation alignment) with a *specific, quantified, still-open performance gap* you can cite and try to beat. |
| **Feasibility (5-Person Team)** | High feasibility — dataset is ready-made, task is well-defined, and the retrieval+NLI architecture is standard and well-documented in the cited papers. Very achievable polish level for a semester. |
| **Resume & Interview Value** | Strong and cleanly explainable: "we benchmarked against a published 0.59 F1 result and built a cross-domain extension" is a crisp, verifiable claim for interviews. |

### Existing Work & Literature Baseline

| Prior Art / Benchmark | Description & Findings |
| :--- | :--- |
| ****Citation-Integrity corpus** (Oxford Bioinformatics, 2024)** | 100 highly-cited biomedical papers, 3,063 annotated citation instances (ACCURATE/NOT_ACCURATE/IRRELEVANT), public at github.com/ScienceNLP-Lab/Citation-Integrity. |
| ****SciFact** / **SciFact-Open** (Wadden et al., 2020/2022)** | the foundational scientific claim-verification benchmark (1.4K claims vs. abstracts, later expanded to 500K-abstract retrieval). |
| ****DeepSciVerify** (2026)** | LLM-driven evidence-escalation pipeline for claim–citation alignment, evaluated on the SCitance dataset. |
| ****SemanticCite** (2025)** | 1,000+ citations across 8 disciplines with functional/semantic annotations. |
| ****CiteME** (NeurIPS 2024 Datasets & Benchmarks)** | shows even strong LMs achieve only ~35% accuracy identifying the correctly cited paper from an excerpt. |

### Proposed NLP Technical Pipeline

| Stage / Step | Module Name | Technical Methodology & Approach |
| :---: | :--- | :--- |
| **Step 1** | **Retrieval stage** | given a citing sentence + its reference, retrieve the top-k evidence sentences from the cited paper (BM25 + dense re-ranker, following the Citation-Integrity paper's own best pipeline as your baseline). |
| **Step 2** | **Verification stage** | fine-tune a NLI/claim-verification model (e.g., a SciFact-pretrained MultiVerS-style model or a smaller open LLM) to classify ACCURATE / NOT_ACCURATE / IRRELEVANT, with rationale-sentence highlighting for explainability. |
| **Step 3** | **Differentiator** | combine the biomedical corpus (which is narrow) with a CS/NLP-domain extension you build yourselves (since ACL/arXiv papers are freely available and self-citation-checkable), demonstrating cross-domain generalization — a genuine open question in the literature. |
| **Step 4** | **Optional** | severity scoring (minor paraphrase drift vs. outright unsupported claim) rather than a flat 3-way label, which none of the cited systems currently do. |

### Data Plan & Corpus Strategy

| Stream / Focus Area | Dataset Strategy & Resource Details |
| :--- | :--- |
| **Primary** | the public Citation-Integrity corpus (ready-made, expert-annotated, no collection needed). |
| **Secondary/extension** | build a small CS-domain test set from ACL Anthology + arXiv papers (self-supervising via citation sentence vs. cited abstract pairs, following SciFact's citance-based annotation protocol) to test cross-domain robustness — this "we built our own eval slice" step is what differentiates you from simply re-running the existing benchmark. |

### Evaluation Framework & Benchmarks

| Evaluation Dimension | Benchmark Protocol & Success Metrics |
| :--- | :--- |
| **Metric 1** | Micro/macro-F1 against the Citation-Integrity test split, directly comparable to the paper's published 0.59/0.52 baseline and GPT-4 ICL's 0.65/0.45. |
| **Retrieval quality** | Recall@k / MRR for the evidence-retrieval stage. |
| **Cross-domain generalization** | same metrics on your self-built CS/NLP slice. |
| **Metric 4** | Human evaluation of rationale quality (does the highlighted evidence span actually justify the verdict?). |

### Key References & Literature Links

| # | Citation / Paper Reference |
| :---: | :--- |
| 1 | *Assessing citation integrity in biomedical publications: corpus annotation and NLP models*, Bioinformatics 40(7), 2024 — github.com/ScienceNLP-Lab/Citation-Integrity |
| 2 | Wadden et al., *Fact or Fiction: Verifying Scientific Claims*, EMNLP 2020 (SciFact) |
| 3 | *DeepSciVerify: Verifying Scientific Claim–Citation Alignment via LLM-Driven Evidence Escalation*, arXiv:2605.27710 (2026) |
| 4 | *SemanticCite: Citation Verification with AI-Powered Full-Text Analysis*, arXiv:2511.16198 (2025) |
| 5 | *CiteME: Can Language Models Accurately Cite Scientific Claims?*, NeurIPS D&B 2024<br><br>--- |

---

# 3. DPDP Act Compliance Gap Detector (India-specific)

### Project Profile & Specifications

| Dimension | Specification / Description |
| :--- | :--- |
| **Problem & Target Users** | India's **Digital Personal Data Protection Rules, 2025** were notified on 13 November 2025, starting an 18-month phased compliance countdown for every Indian business handling personal data. Companies must now check whether their internal privacy policies, consent flows, and vendor contracts actually satisfy the Act's obligations — today this is done manually by compliance consultants (KPMG, Deloitte, etc. are actively publishing manual "action plan" guides). Users: startup/SME compliance teams, DPOs, legal-tech vendors, and consulting firms without dedicated NLP tooling yet. |
| **Why It Matters** | This is a live, dated regulatory event with real financial stakes (penalties up to ₹250 crore per breach) and a hard compliance clock — a rare case of a course project mapping to something genuinely time-sensitive rather than evergreen. |
| **The Identified Gap** | There is currently **no public, benchmarked obligation-extraction or gap-detection dataset for the DPDP Act** — everything published on GDPR/CCPA doesn't transfer cleanly because DPDP has India-specific constructs (Data Fiduciary/Data Principal terminology, Consent Managers, the Data Protection Board, distinct breach-notification and cross-border-transfer rules). This is a textbook "research-to-product gap": methodology exists (the GDPR DPA-checking paper), but the domain-specific resource doesn't. |
| **Expected Prototype Output** | Upload a privacy policy → receive a structured DPDP compliance gap report: obligation-by-obligation coverage status, missing-clause flags with severity, and suggested clause language pulled from the Act's own text. |
| **Novelty vs. Generic Projects** | Not a generic "RAG chatbot over a legal PDF" — the deliverable is a structured, severity-scored gap report against a specific, freshly-enacted regulation with no existing benchmark, which is a defensible and rare claim. |
| **Feasibility (5-Person Team)** | Medium — the main cost is annotation time (you're building the first dataset of its kind), which is real work but scoped and bounded; the modeling techniques themselves (NER, sentence-matching, NLI) are standard. This is the idea most dependent on your team being willing to do careful manual annotation early. |
| **Resume & Interview Value** | Very high, especially for an India-based audience or any legal-tech/compliance-adjacent interview: "we built the first obligation-extraction dataset and gap-detection system for India's new data protection law, during its live 18-month compliance window" is distinctive and timely. |

### Existing Work & Literature Baseline

| Prior Art / Benchmark | Description & Findings |
| :--- | :--- |
| ****OPP-115** (Wilson et al., 2016), **PolicyQA** (2020), **PolicyIE** (2021), **PrivacyGLUE** (2023)** | established privacy-policy NLP corpora and tasks — but built for *US* privacy policy conventions (CCPA-era), not India's Act. |
| ****NLP-based Automated Compliance Checking of Data Processing Agreements against GDPR** (2022)** | the closest transferable methodology — sentence-level semantic matching of DPA text against 45 GDPR requirements, evaluated on 54 real DPAs. |
| ****ComplianceNLP** (2026) and **RAGulating Compliance** (2025)** | recent KG-augmented RAG systems for multi-framework regulatory gap detection (SEC/MiFID/Basel) — architecture template you can adapt. |
| • | One very early **arXiv preprint (Jan 2026)** proposes an agentic framework for DPDP-aligned data governance — confirms the space is *just* opening up, with no established benchmark or public dataset yet. |

### Proposed NLP Technical Pipeline

| Stage / Step | Module Name | Technical Methodology & Approach |
| :---: | :--- | :--- |
| **Step 1** | ****Obligation extraction**** | parse the DPDP Act + Rules text into a structured obligation ontology (subject/actor, obligation type, condition, deadline) — NER + relation extraction, following the GDPR DPA-checker's sentence-to-requirement matching design. |
| **Step 2** | ****Policy-to-obligation matching**** | given a company's privacy policy / internal data-handling doc, semantically match each policy statement to the obligation(s) it satisfies (sentence embeddings + entailment/NLI scoring), following the 2022 GDPR paper's protocol directly. |
| **Step 3** | ****Gap report generation**** | for every unmatched or weakly-matched obligation, generate a structured gap report with severity (e.g., missing breach-notification clause = high severity; missing optional disclosure = low). |
| **Step 4** | **This is the one project on this list where **you must build your own annotated dataset** — treat that as a deliverable, not an obstacle** | annotate ~30–50 real/sample privacy policies (many Indian companies have published DPDP-readiness policy updates you can use as source text) against the Act's clauses, following the 2022 GDPR paper's two-phase manual-then-automated annotation protocol as your template. |

### Data Plan & Corpus Strategy

| Stream / Focus Area | Dataset Strategy & Resource Details |
| :--- | :--- |
| **Primary source text** | the DPDP Act, 2023 + DPDP Rules, 2025 (public, MeitY). |
| **Policy corpus** | publicly available Indian company privacy policies + consulting firms' published "DPDP readiness" checklists (KPMG, Deloitte have public guidance documents breaking the Act into implementation-ready obligation categories — useful as a semi-structured starting ontology, not to be copied verbatim). |
| **Annotation** | your team defines and labels obligation-to-policy-clause mappings; budget meaningful time for this (2022 GDPR paper's team spent two working weeks on it for 24 documents), and document inter-annotator agreement. |

### Evaluation Framework & Benchmarks

| Evaluation Dimension | Benchmark Protocol & Success Metrics |
| :--- | :--- |
| **Metric 1** | Obligation-extraction F1 against your hand-labeled test set. |
| **Metric 2** | Policy-matching precision/recall (does the system correctly flag when a policy clause does/doesn't satisfy an obligation?), compared against a keyword-matching baseline. |
| **Gap-report usefulness** | human evaluation by comparing your system's gap report against a manually produced one for a held-out company policy. |

### Key References & Literature Links

| # | Citation / Paper Reference |
| :---: | :--- |
| 1 | Wilson et al., *OPP-115 Corpus*, 2016; Ahmad et al., *PolicyQA*, 2020 / *PolicyIE*, 2021 |
| 2 | *NLP-based Automated Compliance Checking of Data Processing Agreements against GDPR*, arXiv:2209.09722 (2022) |
| 3 | *ComplianceNLP: Knowledge-Graph-Augmented RAG for Multi-Framework Regulatory Gap Detection*, arXiv:2604.23585 (2026) |
| 4 | *RAGulating Compliance: A Multi-Agent Knowledge Graph for Regulatory QA*, arXiv:2508.09893 (2025) |
| 5 | *An Agentic Software Framework for Data Governance under DPDP*, arXiv:2601.01101 (2026) |
| 6 | Digital Personal Data Protection Rules, 2025 (MeitY, notified 13 Nov 2025)<br><br>--- |

---

# 4. Cross-Document Claim & Narrative Provenance Tracker

### Project Profile & Specifications

| Dimension | Specification / Description |
| :--- | :--- |
| **Problem & Target Users** | When a claim spreads across news outlets, social media, and blogs, it mutates — details get added, dropped, or distorted at each retelling. Journalists and researchers currently have no structured way to trace *where a claim originated* and *how it changed* as it propagated across sources; they either read everything manually or rely on binary true/false fact-checking, which discards the provenance information entirely. Users: investigative journalists, misinformation researchers, fact-checking organizations, OSINT analysts. |
| **Why It Matters** | This is explicitly framed as something *other than* fake-news classification — the output is a structured attribution graph and timeline, which is more useful for investigation than a single veracity label, and is closer to how journalists actually work (tracing a claim back to its first appearance and identifying where it was distorted). |
| **The Identified Gap** | Every one of the datasets above is framed as "cross-document event/temporal extraction is still a fundamentally under-explored area" relative to single-document extraction — and none of them combine event linking with *claim-level* attribution (who said it first, how the wording changed) in English at scale. The CLES dataset explicitly calls this an "unexplored" paradigm and is Chinese-only, leaving an open English-language opportunity. |
| **Expected Prototype Output** | Given a claim or topic, the system outputs a timeline + attribution graph showing the earliest known source, subsequent restatements, and where/how the wording or details diverged — visualized as an interactive graph, not a single true/false verdict. |
| **Novelty vs. Generic Projects** | Explicitly differentiated from fake-news detection by design: no veracity label is produced at all — only structured provenance, which is a genuinely underused framing per the literature itself. |
| **Feasibility (5-Person Team)** | Medium — the individual components (coreference, temporal ordering) are backed by existing datasets, but stitching them into a coherent end-to-end provenance graph and building your own annotated evaluation slice is real integration work. Doable, but the most engineering-heavy of the five ideas. |
| **Resume & Interview Value** | High, particularly for anyone interested in journalism-tech, OSINT, or misinformation research — a distinctive graph-output framing that avoids the "we built another fake-news classifier" cliché. |

### Existing Work & Literature Baseline

| Prior Art / Benchmark | Description & Findings |
| :--- | :--- |
| ****CRAB** (2024)** | cross-document dataset (173 documents, 2,730 event pairs, 20 stories) explicitly built to assess causal-relationship strength between events *across* different articles, not just within one. |
| ****CDEC** | Cross-Document Event Coreference** (2021): 21K Wikinews articles clustered into storylines via a "Related News" hyperlink graph, with dense cross-document event-identity annotation. |
| ****CLES** (2024)** | large-scale cross-document event extraction dataset (20K+ documents, 37.7K events, 70%+ cross-document) — built for Chinese, which is a genuine limitation/opportunity (an English-language equivalent doesn't yet exist at this scale). |
| ****TIMELINE** (2023) and **Background Summarization of Event Timelines** (2023, using Timeline17/Crisis/Social Timeline datasets)** | temporal-ordering and timeline-construction resources. |

### Proposed NLP Technical Pipeline

| Stage / Step | Module Name | Technical Methodology & Approach |
| :---: | :--- | :--- |
| **Step 1** | **Document clustering** | group articles/posts discussing the same underlying story (embedding-based clustering + the "related-article graph" trick from CDEC). |
| **Step 2** | **Cross-document event/claim coreference** | identify when two documents are describing the same underlying claim (fine-tune a cross-encoder on CDEC/CRAB-style pairs). |
| **Step 3** | **Temporal ordering + provenance graph construction** | order claim mentions by publication date, and represent claim mutation as a graph (nodes = claim instances per source, edges = "derived from" with a distortion/similarity score). |
| **Step 4** | **Distortion scoring** | quantify how much a claim instance diverges from its earliest known instance (semantic similarity + added/dropped-entity detection) — this is your novel contribution layered on top of existing cross-doc coreference work. |

### Data Plan & Corpus Strategy

| Stream / Focus Area | Dataset Strategy & Resource Details |
| :--- | :--- |
| **Aspect 1** | CDEC (Wikinews, public, CC-BY) and CRAB are directly usable for training/evaluating the coreference and causal-strength components. |
| **Aspect 2** | For the claim-provenance/timeline layer, construct your own small corpus around 5–10 real news stories (scrape via RSS/NewsAPI-style public feeds, respecting terms of service) and manually annotate claim mutation — a bounded, achievable task for one sub-team. |

### Evaluation Framework & Benchmarks

| Evaluation Dimension | Benchmark Protocol & Success Metrics |
| :--- | :--- |
| **Cross-document coreference** | precision/recall against CDEC's gold clusters. |
| **Metric 2** | Causal/temporal ordering accuracy against CRAB and TIMELINE. |
| **Provenance-graph quality** | human evaluation of whether the constructed "who said it first, how did it change" graph matches a manually researched ground truth for your own annotated stories. |

### Key References & Literature Links

| # | Citation / Paper Reference |
| :---: | :--- |
| 1 | *CRAB: Assessing the Strength of Causal Relationships Between Real-world Events*, arXiv:2311.04284 (2024) |
| 2 | *Cross-document Event Identity via Dense Annotation*, arXiv:2109.06417 (2021) — CDEC |
| 3 | *Harvesting Events from Multiple Sources: Towards a Cross-Document Event Extraction Paradigm*, arXiv:2406.16021 (2024) — CLES |
| 4 | *TIMELINE: Exhaustive Annotation of Temporal Relations...*, arXiv:2310.17802 (2023) |
| 5 | *Background Summarization of Event Timelines*, arXiv:2310.16197 (2023)<br><br>--- |

---

# 5. Multi-Report CTI Campaign Aggregator

### Project Profile & Specifications

| Dimension | Specification / Description |
| :--- | :--- |
| **Problem & Target Users** | Security analysts read cyber threat intelligence (CTI) reports and manually tag which MITRE ATT&CK tactics/techniques a threat actor used, so defenders can map detections to real adversary behavior. Users: SOC analysts, threat-intel teams, MSSPs. |
| **Why It Matters** | This directly supports proactive defense — accurately mapped CTI is what lets defenders build detections ahead of an attack rather than after one. |
| **The Identified Gap** | The SoK paper's answer is effectively "not yet," and the specific, still-open sub-problem is **cross-report, campaign-level aggregation**: almost all existing work tags techniques *within a single report*, but real adversary campaigns are described piecemeal across dozens of reports from different vendors, with inconsistent naming and partial overlap. A 2026 paper, *Beyond Single Reports: Evaluating Automated ATT&CK Technique Extraction in Multi-Report Campaign Settings*, is one of the only works to test this directly, and shows performance degrades substantially versus single-report extraction. |
| **Expected Prototype Output** | Given a set of CTI report URLs/PDFs about the same campaign, output one unified, deduplicated ATT&CK technique profile with confidence scores and source attribution per technique. |
| **Novelty vs. Generic Projects** | Positioned specifically at the cross-report aggregation gap rather than re-solving already well-covered single-report tagging — but this is the most competitive/crowded space on the list, so novelty depends on staying disciplined about that scoping. |
| **Feasibility (5-Person Team)** | Medium — strong existing tooling lowers the floor (achievable baseline is fast to stand up), but the genuinely novel cross-report layer requires real entity-resolution engineering. |
| **Resume & Interview Value** | Medium-high — cybersecurity-adjacent NLP is a strong recruiting signal, but because the space is crowded, be ready to clearly articulate why your project isn't "yet another ATT&CK tagger." |

### Existing Work & Literature Baseline

| Prior Art / Benchmark | Description & Findings |
| :--- | :--- |
| **This is the most heavily researched space on this list** | **TRAM** (MITRE's own dataset), **CTIBench** (NeurIPS 2024), **CTI-HAL** (2025), **CTINEXUS**, **CyBERTa**, and dozens of BERT/LLM-based single-report TTP extractors. A **2025 USENIX Security "SoK" paper explicitly asks "Automated TTP Extraction from CTI Reports: Are We There Yet?"** — surveying the entire field. |

### Proposed NLP Technical Pipeline

| Stage / Step | Module Name | Technical Methodology & Approach |
| :---: | :--- | :--- |
| **Step 1** | **Single-report technique extraction** | fine-tune a transformer (e.g., SecureBERT/CyBERTa-style) on TRAM/CTI-HAL for per-report ATT&CK tagging — this is your baseline, well-supported by existing code/models. |
| **Step 2** | **Cross-report entity/campaign linking** | cluster reports describing the same campaign or actor (via shared IOCs, actor-name aliasing, temporal proximity) using entity resolution techniques. |
| **Step 3** | **Aggregated technique-profile construction** | merge per-report technique tags into a single deduplicated, confidence-weighted campaign profile, resolving naming inconsistencies across vendors (a known, cited pain point). |
| **Step 4** | Component 4 | Output as a STIX-compatible structured campaign summary. |

### Data Plan & Corpus Strategy

| Stream / Focus Area | Dataset Strategy & Resource Details |
| :--- | :--- |
| **Aspect 1** | TRAM (MITRE Center for Threat-Informed Defense, public GitHub), CTIBench, CTI-HAL — all public, ready to use for the single-report baseline. |
| **Aspect 2** | For the cross-report aggregation layer, construct a small multi-report campaign test set (public APT threat reports referencing the same named campaign from multiple vendors — APTnotes repository is a public aggregator) and manually verify aggregated technique coverage. |

### Evaluation Framework & Benchmarks

| Evaluation Dimension | Benchmark Protocol & Success Metrics |
| :--- | :--- |
| **Single-report baseline** | F1 against TRAM/CTIBench published numbers. |
| **Cross-report aggregation** | precision/recall of the merged campaign profile against manually verified ground truth, plus a "how much does performance degrade going single→multi-report" analysis, directly comparable to the 2026 "Beyond Single Reports" paper's findings. |

### Key References & Literature Links

| # | Citation / Paper Reference |
| :---: | :--- |
| 1 | Büchel et al., *SoK: Automated TTP Extraction from CTI Reports — Are We There Yet?*, USENIX Security 2025 |
| 2 | *Beyond Single Reports: Evaluating Automated ATT&CK Technique Extraction in Multi-Report Campaign Settings*, arXiv:2604.07470 (2026) |
| 3 | *CTI-HAL: A Human-Annotated Dataset for Cyber Threat Intelligence Analysis*, arXiv:2504.05866 (2025) |
| 4 | MITRE Center for Threat-Informed Defense, *TRAM dataset*, github.com/center-for-threat-informed-defense/tram |
| 5 | Alam et al., *CTIBench: A Benchmark for Evaluating LLMs in Cyber Threat Intelligence*, NeurIPS 2024<br><br>--- |

---

# Considered and rejected

Per your instruction to be critical rather than padding the list:

### Rejection Analysis & Comparison Matrix

| Candidate Problem Space | Landscape, Data Status & Detailed Rejection Rationale |
| :--- | :--- |
| **# Considered and rejected<br><br>Per your instruction to be critical rather than padding the list** |  |
| ****Legal contract clause review/retrieval (CUAD/ACORD/MAUD)**** | excellent datasets and research depth, but this space is now heavily commercialized (Kira Systems, LawGeex, Ironclad, Luminance, etc.) and extremely well-covered academically. A student prototype has little room to say anything a dozen funded startups and multiple NeurIPS-track datasets haven't already said. Reject for novelty and differentiation, not for data or feasibility. |
| ****PICO extraction / systematic-review automation**** | strong datasets (EBM-NLP) but the practical tooling gap is mostly closed: Covidence, DistillerSR, RobotReviewer and multiple GenAI pipelines (one 2024 study reported 98% GPT-4o extraction accuracy on 680K+ PICOs) already serve this well. Reject as over-served. |
| ****Legal/bureaucratic plain-language simplification**** | real research gap exists (small, thin datasets like the Plain-English-Contracts corpus), but the deliverable shape is uncomfortably close to "generic PDF summarizer," which you explicitly asked to avoid, and the evaluation story (readability + faithfulness) is harder to make as crisp as the other five. Reject as too close to the "slop" category and too thin on data. |
| ****Plain Hinglish/code-mixed cybercrime complaint *classification***** | good data story (I4C hackathon dataset, HingBERT), but as a bare classification task it's exactly the "basic text classification with an accuracy score" pattern you asked to avoid, and the I4C dataset itself isn't openly accessible outside sanctioned hackathons. The *idea* survives in a stronger, more actionable form as Project #1 above (structured extraction + follow-up generation on public scam-report data), which I'd treat as the better version of this same instinct.<br><br>--- |

---

# My actual recommendation

If you want one flagship: **Project #1, the Scam-Victim Forensic Schema Extractor.**

### Strategic Decision Matrix & Selection Guidance

| Option Tier | Project Recommendation | Detailed Strategic Rationale & Fit |
| :---: | :--- | :--- |
| **Primary Flagship** | **Project #1: Scam-Victim Forensic Schema Extractor** | Reasoning, briefly: it's the only idea on this list built on genuinely fresh (2025–2026) research with a *named, specific, still-open limitation* you can directly target (the "forensic detail gap" from the Wen et al. paper) rather than a broad, long-standing open problem where you're one of a hundred groups chipping away at it. The data story is realistic without needing restricted government access. The output — a structured case file plus an adaptive follow-up-question generator — is unambiguously "actionable," not a bare classification score, which satisfies your hardest constraint. And the interview story writes itself: you can point to a specific paper, a specific gap sentence in that paper, and a specific system you built to close it. |
| **Safest Backup** | **Project #2: Citation-Integrity Verifier** | **Project #2 (Citation Integrity)** is the safest, highest-certainty-of-success alternative if your team wants a lower-risk build with a ready-made benchmark and less annotation overhead — recommend it as backup if #1's data-assembly work feels too open-ended for your timeline. |
| **Highest-Ceiling Option** | **Project #3: DPDP Act Compliance Gap Detector** | **Project #3 (DPDP)** is the highest-ceiling choice if your team is comfortable doing real annotation work and wants maximum resume distinctiveness for the Indian job market specifically — but it's the most annotation-heavy of the five, so only choose it if you're confident in your team's discipline around that work. |
