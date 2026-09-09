# Module 5: Engineering RAG + LLM Agent

This is a standalone module providing an evidence-grounded engineering decision-support agent. It consumes outputs from Modules 1-3.

## Architecture
- `schemas/`: Pydantic models for structured data.
- `ingestion/`: Adapter to read Module 1 (events, flagged incidents) and Module 2 (analog wells).
- `retrieval/`: ChromaDB vector store and retrieval logic.
- `agent/`: Gemini LLM integration with strict evidence-grounding prompts.
- `app.py`: Streamlit frontend for the drilling engineer.

## Setup
1. Copy `.env.example` to `.env` and set your `GEMINI_API_KEY`.
2. Install dependencies: `pip install -r requirements.txt`
3. Run the app: `streamlit run app.py`

## Usage
Provide the current drilling parameters and/or event sequence, then ask the agent questions like:
- "What happened in similar wells?"
- "What interventions were successful?"
- "Why mud loss instead of stuck pipe?"

The agent will retrieve relevant historical events, constrained by the top analog wells, and provide factual, cited answers.
