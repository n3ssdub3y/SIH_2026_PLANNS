                  ┌──────────────────────────┐
                  │ HISTORICAL DATA          │
                  │                          │
                  │ Daily Drilling Reports   │
                  │ WITSML / XML             │
                  │ Well Metadata             │
                  │ Formation Data            │
                  │ BHA / Trajectory         │
                  └────────────┬─────────────┘
                               │
                               ▼
                  ┌──────────────────────────┐
                  │ DATA NORMALIZATION       │
                  │                          │
                  │ PDF/XML/JSON → canonical │
                  │ schema                   │
                  └────────────┬─────────────┘
                               │
                 ┌─────────────┴─────────────┐
                 ▼                           ▼
      ┌─────────────────────┐       ┌──────────────────────┐
      │ HISTORICAL TEXT     │       │ HISTORICAL NUMERICAL │
      │                     │       │                      │
      │ DDR comments        │       │ depth                │
      │ operations          │       │ torque               │
      │ observations        │       │ WOB                  │
      │ interventions       │       │ ROP                  │
      └──────────┬──────────┘       │ pressure             │
                 │                  │ flow                 │
                 ▼                  └──────────┬───────────┘
      ┌─────────────────────┐                 │
      │ NLP EXTRACTION      │                 │
      │                     │                 │
      │ Events              │                 │
      │ Entities            │                 │
      │ Relations           │                 │
      │ Cause → effect      │                 │
      │ Interventions       │                 │
      └──────────┬──────────┘                 │
                 │                            │
                 └─────────────┬──────────────┘
                               ▼
                    ┌──────────────────────┐
                    │ CANONICAL EVENT      │
                    │ REPRESENTATION       │
                    │                      │
                    │ depth               │
                    │ formation           │
                    │ event               │
                    │ precursor           │
                    │ intervention        │
                    │ outcome             │
                    │ sensor features     │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │ HISTORICAL WELL      │
                    │ MEMORY               │
                    │                      │
                    │ Well 1               │
                    │ Well 2               │
                    │ Well 3               │
                    │ ...                  │
                    └──────────┬───────────┘
                               │
                               │
          CURRENT WELL         │
                               │
┌──────────────────────────────┴────────────────────────┐
│                                                       │
│ LIVE TELEMETRY                                        │
│                                                       │
│ WITSML / ETP in production                            │
│ Volve replay / simulator for prototype                │
│                                                       │
│ Torque / WOB / ROP / Flow / Pressure / RPM / etc.    │
└──────────────────────────────┬────────────────────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │ SIGNAL PROCESSING    │
                    │                      │
                    │ normalization        │
                    │ rolling statistics   │
                    │ trends               │
                    │ slopes               │
                    │ deviations           │
                    │ change detection     │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │ LIVE EVENT DETECTOR  │
                    │                      │
                    │ torque↑              │
                    │ ROP↓                 │
                    │ pressure↑            │
                    │ flow anomaly         │
                    │ etc.                 │
                    └──────────┬───────────┘
                               │
                               ▼
                 ┌─────────────────────────────┐
                 │ HAZARD-SPECIFIC SIMILARITY │
                 │                             │
                 │ Mud Loss                    │
                 │ Stuck Pipe                  │
                 │                             │
                 │ different feature weights  │
                 └──────────────┬──────────────┘
                                │
                                ▼
                    ┌──────────────────────┐
                    │ TOP-K ANALOG WELLS   │
                    │                      │
                    │ Well A  0.87         │
                    │ Well F  0.82         │
                    │ Well C  0.77         │
                    │ Well H  0.72         │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │ SEQUENCE MATCHING    │
                    │                      │
                    │ Current:             │
                    │ A → B → C → D       │
                    │                      │
                    │ Historical:          │
                    │ A → B → X → D → E   │
                    │                      │
                    │ DTW / alignment      │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │ UNCERTAINTY ENGINE   │
                    │                      │
                    │ 2/4 → mud loss       │
                    │ 2/4 → no mud loss    │
                    │                      │
                    │ Why disagreement?    │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │ EVIDENCE RETRIEVAL   │
                    │                      │
                    │ actual report text   │
                    │ actual depth         │
                    │ actual event         │
                    │ actual intervention  │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │ LLM BRIEFING         │
                    │                      │
                    │ explanation          │
                    │ evidence             │
                    │ citations            │
                    │ disagreement         │
                    │ suggested attention  │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │ ENGINEER DASHBOARD   │
                    └──────────────────────┘