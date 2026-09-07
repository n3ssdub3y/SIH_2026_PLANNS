# NWIS Data Sources — Explained, Prioritized & Linked

---

## Priority Matrix (Quick View)

| Priority | Data Source | Why This Priority | Demo Impact |
|:---:|:---|:---|:---:|
| 🔴 **P0** | **ix. Historical operational event records** (mud losses, kicks, stuck pipe, NPT) | This IS your core product — the events you match against | Critical |
| 🔴 **P0** | **ii. Daily Drilling Reports (DDRs)** | Primary NLP input — unstructured text you extract events FROM | Critical |
| 🟠 **P1** | **i. Well Completion Reports (WCRs)** | Richest single-well narrative summaries; feed the knowledge base | High |
| 🟠 **P1** | **vi. eRTMAC data streams** | The "live" side — what triggers your analog matching | High |
| 🟡 **P2** | **iv. Historical well parameters & drilling records** | Structured time-series (ROP, WOB, torque) for similarity scoring | Medium |
| 🟡 **P2** | **v. Reservoir and geological data** | Formation names, depths, lithology — needed for cross-well correlation | Medium |
| 🟡 **P2** | **vii. Well trajectory and survey data** | Geospatial "nearby" calculation — needed for the map | Medium |
| ⚪ **P3** | **viii. Casing, cementing, and mud program records** | Supporting context; useful but not core for a 5-day demo | Low |
| ⚪ **P3** | **iii. Drilling and mud logging databases** | Overlaps with DDRs and well parameters; supplementary | Low |

---

## Detailed Source Breakdown

---

### 🔴 P0 — CRITICAL: Build your demo around these

---

### ix. Historical Operational Event Records
*Mud losses, kicks, stuck pipe incidents, fishing operations, NPT events*

**What it is:** Structured or semi-structured logs of every significant incident that occurred during drilling — categorized by event type, depth, duration, severity, and resolution action taken. NPT = Non-Productive Time (any time the drill isn't making hole).

**Why it's #1 priority:** Your entire system matches *current drilling conditions* against *historical events at similar wells/formations/depths*. Without a database of past events, there's nothing to match against. This is literally the "institutional memory" the PS asks for.

**For your demo:** This becomes your **structured event database** that the similarity engine queries.

#### 🔗 Public Equivalents & Links

| Resource | Link | What You Get |
|:---|:---|:---|
| **Petrobras 3W Dataset** ⭐ | [github.com/petrobras/3W](https://github.com/petrobras/3W) | Multivariate time-series from real oil wells with labeled undesirable events (kicks, flow instability, loss of circulation, stuck pipe). Version 2.0 has Parquet files, updated labels. **Best public source for labeled drilling events.** |
| 3W on Kaggle | [kaggle.com/datasets (search "3W")](https://www.kaggle.com/datasets?search=petrobras+3w) | Same dataset, community-cleaned versions in CSV |
| **DataDRILL** | [doi.org/10.5281/zenodo.12759014](https://doi.org/10.5281/zenodo.12759014) | 2,000+ simulated drilling scenarios with 28 parameters, designed specifically for kick detection and formation pressure prediction. Clean, ready-to-use. |
| Utah FORGE Drilling Events | [gdr.openei.org](https://gdr.openei.org/) → search "Utah FORGE" | Daily drilling reports from real geothermal wells with operational events, depth logs, incident records |
| IADC Incident Statistics | [iadc.org](https://www.iadc.org/) | Industry-level incident statistics (not raw data, but useful for context/validation) |

---

### ii. Daily Drilling Reports (DDRs)

**What it is:** A narrative text document written every 24 hours by the on-site drilling engineer. Contains: operations summary (what happened), depth progress, mud properties, equipment used, any problems encountered, and time breakdowns. **This is unstructured text** — the primary input for your NLP extraction pipeline.

**Why it's #1 priority:** DDRs are where the richest operational knowledge lives in natural language. Extracting structured events from DDRs is the core NLP task of your project. Every "lesson learned" that isn't in a database is buried in a DDR somewhere.

**For your demo:** This is what your NLP pipeline ingests and extracts events from.

#### 🔗 Public Equivalents & Links

| Resource | Link | What You Get |
|:---|:---|:---|
| **Volve DDRs on Hugging Face** ⭐ | [huggingface.co/datasets/bengsoon/volve_alpaca](https://huggingface.co/datasets/bengsoon/volve_alpaca) | **1,759 real DDRs** from Equinor's Volve field, pre-processed into Alpaca format (instruction/input/output) for NLP/LLM fine-tuning. Train: 1,596 / Test: 163. **Best ready-to-use NLP drilling text dataset.** |
| Volve Raw WITSML DDRs | [Equinor Data Village on Databricks](https://www.equinor.com/energy/volve-data-sharing) | Raw DDR files in WITSML XML format — need parsing (use `xmltodict` or custom scripts) |
| Volve DDR CSV (Kaggle) | [kaggle.com/datasets/atunkiel/volve-dataset-well-f-9-a](https://www.kaggle.com/datasets/atunkiel/volve-dataset-well-f-9-a) | Pre-converted CSV of Volve real-time drilling data for specific wells |
| Utah FORGE Daily Reports | [gdr.openei.org](https://gdr.openei.org/) → search "Utah FORGE 56-32" or "16A(78)-32" | Real daily drilling reports from US DOE geothermal wells — PDF/Excel format |
| SPE Data Repository | [spe.org/en/industry/digital-data-sets/](https://www.spe.org/en/industry/digital-data-sets/) | Various contributed drilling datasets (may require SPE login) |

---

### 🟠 P1 — HIGH: Needed for a convincing demo

---

### i. Well Completion Reports (WCRs)

**What it is:** A comprehensive end-of-well document summarizing the entire drilling campaign for a single well — from spud (start) to completion. Includes: well design rationale, formation tops encountered, drilling problems and solutions, casing program executed, cementing results, testing results, and final well status. **Typically 20–100+ pages per well.**

**Why it's important:** WCRs are the richest single-document source of "lessons learned" per well. They contain the full narrative arc: what was planned vs. what actually happened, including every problem and how it was resolved. For your knowledge base, WCRs provide the deep context that DDRs (daily snapshots) don't.

**For your demo:** WCRs feed your **knowledge repository** and provide the long-form text for the "explain the analog" LLM justification module.

#### 🔗 Public Equivalents & Links

| Resource | Link | What You Get |
|:---|:---|:---|
| **Equinor Volve Field Dataset** ⭐ | [equinor.com/energy/volve-data-sharing](https://www.equinor.com/energy/volve-data-sharing) | ~40,000 files including well completion reports, well design docs, drilling logs. **The single most comprehensive public drilling dataset in the world.** Free under Equinor Open Data Licence. |
| Volve on Databricks Marketplace | [marketplace.databricks.com](https://marketplace.databricks.com/) → search "Volve Data Village" | Same dataset, cloud-accessible format |
| Volve GitHub Tools | [github.com/AndrzejTunkiel/VolveDataExploration](https://github.com/AndrzejTunkiel/VolveDataExploration) | Jupyter notebooks to parse and explore Volve data |
| Utah FORGE End-of-Well Reports | [gdr.openei.org](https://gdr.openei.org/) → search "end of well report" | Real completion reports from US DOE geothermal wells |
| US State Regulatory Filings | [Railroad Commission of Texas](https://www.rrc.texas.gov/) / [COGCC Colorado](https://cogcc.state.co.us/) | Public well records filed by operators (PDF, variable quality) |

---

### vi. eRTMAC Data Streams

**What it is:** **Enhanced Real-Time Monitoring & Control Center** — Oil India's proprietary system that streams live drilling data from rigs to a centralized command center. Streams include: weight on bit (WOB), rate of penetration (ROP), torque, standpipe pressure, pump flow rates, mud weight in/out, gas readings, and more. 24/7 monitoring by engineers.

**Why it's important:** eRTMAC is the "live" input to your system — the current well's real-time telemetry that you compare against historical patterns. When eRTMAC shows a torque spike or mud weight drop, your system should recognize "this looks like what happened before a stuck pipe in Well X at this formation."

**For your demo:** You'll **simulate** eRTMAC with a synthetic telemetry stream (since the real system is OIL-internal).

> [!IMPORTANT]
> eRTMAC is **100% proprietary to Oil India** — there is no public equivalent of this specific system. For your demo, simulate it using the real-time drilling parameter format from public datasets.

#### 🔗 Public Simulation Sources

| Resource | Link | What You Get |
|:---|:---|:---|
| **Volve Real-Time Drilling Data** ⭐ | [kaggle.com/datasets/atunkiel/volve-dataset-well-f-9-a](https://www.kaggle.com/datasets/atunkiel/volve-dataset-well-f-9-a) | Real time-indexed drilling parameters (ROP, WOB, torque, pressure) from Volve wells — **use as template for your telemetry simulator** |
| DataDRILL (Zenodo) | [doi.org/10.5281/zenodo.12759014](https://doi.org/10.5281/zenodo.12759014) | 28 simulated drilling parameters with realistic scenarios — perfect for demo telemetry |
| OSDC Drilling Simulations | [github.com/APMonitor/drilling](https://github.com/APMonitor/drilling) | Open-source drilling simulation models in Python/MATLAB |
| WITSML Standard (schema reference) | [energistics.org](https://www.energistics.org/) | The industry-standard format for real-time drilling data transfer — useful if you want your simulator to output realistic-looking data |
| eRTMAC Info (OIL website) | [oil-india.com](https://www.oil-india.com/) → search "eRTMAC" or "Project DRIVE" | Background reading on what eRTMAC actually does — useful for your PPT |

---

### 🟡 P2 — MEDIUM: Needed for depth, not for MVP

---

### iv. Historical Well Parameters & Drilling Records

**What it is:** Structured, tabular time-series data logged automatically during drilling — depth vs. time, ROP, WOB, torque, RPM, standpipe pressure, flow rate, mud weight, etc. Unlike DDRs (narrative text), this is **numerical sensor data** recorded at regular intervals (every few seconds to minutes).

**Why it matters:** These are the *features* your hazard-specific similarity scoring uses. When comparing "is Well B a good analog for the current well?", you compare their drilling parameter profiles at equivalent depths/formations. This is the quantitative backbone behind the analog ranking.

#### 🔗 Public Equivalents

| Resource | Link | What You Get |
|:---|:---|:---|
| **Volve Drilling Data (CSV)** | [kaggle.com/datasets/atunkiel/volve-dataset-well-f-9-a](https://www.kaggle.com/datasets/atunkiel/volve-dataset-well-f-9-a) | Real drilling parameters in CSV — ROP, WOB, torque, etc. |
| 3W Dataset | [github.com/petrobras/3W](https://github.com/petrobras/3W) | Multivariate well sensor data with labeled events |
| DataDRILL | [doi.org/10.5281/zenodo.12759014](https://doi.org/10.5281/zenodo.12759014) | 28 drilling parameters per scenario |
| Figshare ROP Data | [figshare.com](https://figshare.com/) → search "drilling rate of penetration" | Smaller focused datasets for ROP optimization |

---

### v. Reservoir and Geological Data

**What it is:** Formation names (e.g., Tipam, Barail, Girujan in OIL's Assam context), formation tops (depths where each formation starts/ends), lithology (sandstone, shale, limestone), porosity, permeability, pore pressure gradients, and fracture gradients. This is the geological "map" of what's underground.

**Why it matters:** Cross-well correlation is fundamentally about **formation**, not just depth. A mud loss at 2,500m in the Tipam formation is relevant to another well entering Tipam — even if that well hits Tipam at 2,200m. Without formation data, your system can only match by depth (crude) rather than by geology (meaningful).

#### 🔗 Public Equivalents

| Resource | Link | What You Get |
|:---|:---|:---|
| **Volve Geological Data** | [equinor.com/energy/volve-data-sharing](https://www.equinor.com/energy/volve-data-sharing) | Formation tops, stratigraphic data, petrophysical logs |
| Kansas Geological Survey | [kgs.ku.edu](https://www.kgs.ku.edu/Magellan/Logs/index.html) | Searchable well log database with formation data, wireline logs, LAS files |
| USGS National Produced Waters Database | [usgs.gov](https://www.usgs.gov/mission-areas/water-resources/science/national-produced-waters-geochemistry-database) | Geochemical/reservoir data across US wells |
| Macrostrat (formation database) | [macrostrat.org](https://macrostrat.org/) | Geological formation data, lithology, stratigraphy — API accessible |
| Open Subsurface Data Universe (OSDU) | [community.opengroup.org/osdu](https://community.opengroup.org/osdu) | Industry-standard schema for subsurface data — reference implementation |

---

### vii. Well Trajectory and Survey Data

**What it is:** The 3D path of the wellbore underground — recorded as Measured Depth (MD), Inclination, and Azimuth at survey stations. Used to compute the well's actual underground position (latitude, longitude, true vertical depth at every point). Essential for directional/deviated/horizontal wells.

**Why it matters:** This is what powers the **"nearby wells" geospatial map** — you can't show wells on a map or calculate which wells are "nearby" without knowing their actual underground paths. Two wells 500m apart at surface might be 2km apart at target depth if drilled in different directions.

#### 🔗 Public Equivalents

| Resource | Link | What You Get |
|:---|:---|:---|
| **Volve Well Trajectories** | [equinor.com/energy/volve-data-sharing](https://www.equinor.com/energy/volve-data-sharing) | Deviation surveys for all Volve wells |
| Kansas GIS Well Data | [kgs.ku.edu](https://www.kgs.ku.edu/) → Oil and Gas Mapper | Interactive map with well locations and headers |
| Texas RRC Well Locations | [rrc.texas.gov](https://www.rrc.texas.gov/oil-and-gas/research-and-statistics/well-information/) | Public well coordinate data for Texas |
| `wellpathpy` (Python library) | [github.com/Zabamund/wellpathpy](https://github.com/Zabamund/wellpathpy) | Python library to compute well trajectories from survey data — **use this for your prototype** |
| `welly` (Python library) | [github.com/agilescientific/welly](https://github.com/agilescientific/welly) | Well log and trajectory handling in Python |

---

### ⚪ P3 — LOW: Context/enrichment, not core for demo

---

### viii. Casing, Cementing, and Mud Program Records

**What it is:** Engineering design documents specifying: casing sizes and setting depths (the steel pipes lining the well), cement volumes and types used to bond casing to rock, and mud/fluid programs (mud weight, viscosity, additives used at each depth interval). These are both *planned* (the design) and *as-executed* (what actually happened).

**Why it matters (but lower priority):** These feed the "what mitigation was used" part of your system. If Well B had a cement failure at 3,000m, you want to know what cement program they used so you can compare against your current plan. Important for a production system, but for a 5-day demo, the *events* matter more than the *engineering details behind* them.

#### 🔗 Public References

| Resource | Link | What You Get |
|:---|:---|:---|
| Volve Completion String Data | [equinor.com/energy/volve-data-sharing](https://www.equinor.com/energy/volve-data-sharing) | Casing and completion design records |
| OSDC Cementing Models | [github.com/APMonitor/drilling](https://github.com/APMonitor/drilling) | Open-source cementing simulation code |
| SPE Technical Papers | [onepetro.org](https://www.onepetro.org/) | Search "casing design case study" or "cementing failure" — rich narrative data in paper appendices |

---

### iii. Drilling and Mud Logging Databases

**What it is:** Structured databases recording mud logging data — gas chromatography readings (methane, ethane, propane), cuttings descriptions (lithology from rock chips), drilling parameters logged by the mud logger, and formation evaluation data. Mud logging is the first line of geological and safety monitoring at the wellsite.

**Why it matters (but overlaps):** Largely overlaps with DDRs (source ii) and well parameters (source iv). Gas readings are critical for kick detection (a safety event), but the 3W dataset already provides labeled kick events. For the demo, you'll get more value from DDR text extraction and event records than from raw mud log databases.

#### 🔗 Public References

| Resource | Link | What You Get |
|:---|:---|:---|
| Volve Mud Log Data | [equinor.com/energy/volve-data-sharing](https://www.equinor.com/energy/volve-data-sharing) | Raw WITSML mud log objects |
| WITSML mudLog Schema | [energistics.org](https://www.energistics.org/) | Standard data schema for mud logging |
| `lasio` (Python library) | [github.com/kinverarity1/lasio](https://github.com/kinverarity1/lasio) | Read/write LAS well log files in Python |

---

## The "One Dataset to Rule Them All" for Your Demo

If you can only download **one thing**, make it:

> ### ⭐ Equinor Volve Field Dataset
> **Link:** [equinor.com/energy/volve-data-sharing](https://www.equinor.com/energy/volve-data-sharing)  
> **Easier access:** [Hugging Face (DDRs)](https://huggingface.co/datasets/bengsoon/volve_alpaca) + [Kaggle (drilling params)](https://www.kaggle.com/datasets/atunkiel/volve-dataset-well-f-9-a)
> 
> It covers **7 out of 9** of your data sources in one download: WCRs ✅, DDRs ✅, mud logs ✅, well parameters ✅, geological data ✅, trajectories ✅, casing/completion ✅. Only eRTMAC (proprietary) and consolidated event records (use 3W instead) are missing.

And supplement with:

> ### ⭐ Petrobras 3W Dataset
> **Link:** [github.com/petrobras/3W](https://github.com/petrobras/3W)
> 
> For **labeled drilling events** (kicks, stuck pipe, loss of circulation) with real sensor data — directly usable as your event ground truth.

---

## Download Priority for Your 5-Day Build

| Day | What to Download | Who Downloads |
|:---|:---|:---:|
| **Day 0 (now)** | Volve DDRs from Hugging Face (`bengsoon/volve_alpaca`) | #1 (NLP Lead) |
| **Day 0 (now)** | 3W Dataset from GitHub | #3 (Data Lead) |
| **Day 0 (now)** | Volve drilling params CSV from Kaggle | #3 (Data Lead) |
| **Day 0 (now)** | DataDRILL from Zenodo | #3 (Data Lead) |
| **Day 1** | Volve full dataset (if bandwidth allows — it's several TB) OR just the well reports + trajectories subset | #3 |
| **Day 1** | `wellpathpy` + `lasio` Python libraries | #5 (Frontend/Map) |
