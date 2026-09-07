# DDR NLP Extraction & Prompt Tuning Task
In the prototype, we replay public real-time drilling data or simulate the stream. In production, the same ingestion layer is designed around WITSML/ETP.”
This workspace also performs NLP extraction on 10 Daily Drilling Reports (DDRs), converting unstructured daily logs into structured events (hazard type, severity, depth, formation, mud properties, NPT, and mitigations).

## Folder Structure
```
nlp_task_ddr/
├── venv/                 # Python Virtual Environment
├── requirements.txt      # Dependencies (pandas, requests, python-dotenv)
├── extract_10_ddrs.py    # Main NLP extraction runner
├── prompts/
│   └── extraction_prompt.txt   # Prompt template for LLM / NLP extraction
├── data/
│   └── sample_10_ddrs.json     # 10 input DDR text reports
└── results/
    ├── extracted_10_ddrs.json  # Full JSON extraction output
    └── extracted_10_ddrs.csv   # Summary tabular CSV output
```

## Quick Start

1. **Activate the virtual environment**:
   - **PowerShell**: `.\venv\Scripts\Activate.ps1`
   - **CMD**: `.\venv\Scripts\activate.bat`

2. **Run extraction on 10 DDRs**:
   ```bash
   python extract_10_ddrs.py
   ```

3. **Check Results**:
   - `results/extracted_10_ddrs.json`
   - `results/extracted_10_ddrs.csv`
<!-- comments to check github repo -->