"""
NWIS-Sentinel: NLP Extraction Pipeline (P1's core module)
Extracts structured drilling events from Daily Drilling Report text.

Uses LLM structured output to convert free-text DDR entries into
the shared event schema format.

Usage:
    from services.nlp_extractor import extract_events_from_ddr
    events = extract_events_from_ddr(ddr_text, well_id="WELL-F9A")
"""

import json
import os
from typing import Optional

# ---------- CONFIGURATION ----------
# Set your API key as an environment variable:
#   set OPENAI_API_KEY=sk-...
#   OR
#   set GOOGLE_API_KEY=AI...

LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "openai")  # "openai" or "google"
OPENAI_MODEL = "gpt-4o-mini"
GOOGLE_MODEL = "gemini-2.0-flash"


# ---------- EXTRACTION PROMPT ----------
SYSTEM_PROMPT = """You are a drilling-event extraction system for oil and gas operations.

Given a Daily Drilling Report (DDR) text entry, extract ALL drilling events mentioned.
Focus on these event types:
- mud_loss: Any mention of mud losses, lost circulation, lost returns, hi-vis pills, LCM treatment
- stuck_pipe: Any mention of stuck pipe, tight hole, overpull, jarring, back-reaming, pack-off
- kick: Any mention of kick, well control, shut-in, gas influx, flow check
- torque_spike: Excessive torque, drag, high friction
- cementing_issue: Cement failures, poor bond, channeling
- formation_change: New formation encountered, formation tops
- equipment_failure: BHA failure, tool failure, twist-off
- npt: Non-productive time, waiting on weather, repair time

For each event found, output a JSON object with these EXACT fields:
{
  "event_type": one of ["mud_loss", "stuck_pipe", "kick", "torque_spike", "cementing_issue", "formation_change", "equipment_failure", "npt", "other"],
  "depth_start_m": number or null (depth in meters where event occurred),
  "depth_end_m": number or null,
  "formation": string or null (geological formation name if mentioned),
  "severity": one of ["low", "moderate", "high", "critical"],
  "description": string (brief description from the report text),
  "mitigation": string or null (action taken to resolve),
  "outcome": one of ["resolved", "ongoing", "escalated", "unknown"],
  "duration_hours": number or null,
  "parameters": {
    "mud_weight_sg": number or null,
    "flow_rate_lpm": number or null,
    "spp_bar": number or null
  } or null,
  "confidence": number between 0 and 1
}

Return a JSON array of events. If NO drilling events are found, return an empty array [].
Be conservative — only extract events you can clearly identify from the text.
Include the relevant text snippet in the description field."""

USER_PROMPT_TEMPLATE = """Extract drilling events from this DDR entry:

Well: {well_id}
Report Date: {report_date}

--- DDR TEXT ---
{ddr_text}
--- END ---

Return ONLY a JSON array of events. No other text."""


def extract_events_openai(ddr_text: str, well_id: str, report_date: str = "unknown") -> list[dict]:
    """Extract events using OpenAI API."""
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError("Install openai: pip install openai")
    
    client = OpenAI()
    
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_PROMPT_TEMPLATE.format(
                well_id=well_id,
                report_date=report_date,
                ddr_text=ddr_text
            )}
        ],
        response_format={"type": "json_object"},
        temperature=0.1,  # Low temperature for consistent extraction
        max_tokens=2000
    )
    
    result = json.loads(response.choices[0].message.content)
    
    # Handle both {"events": [...]} and direct [...] formats
    if isinstance(result, dict) and "events" in result:
        return result["events"]
    elif isinstance(result, list):
        return result
    else:
        return [result] if result else []


def extract_events_google(ddr_text: str, well_id: str, report_date: str = "unknown") -> list[dict]:
    """Extract events using Google Gemini API."""
    try:
        import google.generativeai as genai
    except ImportError:
        raise ImportError("Install google-generativeai: pip install google-generativeai")
    
    genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
    model = genai.GenerativeModel(GOOGLE_MODEL)
    
    prompt = SYSTEM_PROMPT + "\n\n" + USER_PROMPT_TEMPLATE.format(
        well_id=well_id,
        report_date=report_date,
        ddr_text=ddr_text
    )
    
    response = model.generate_content(
        prompt,
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json",
            temperature=0.1
        )
    )
    
    result = json.loads(response.text)
    if isinstance(result, dict) and "events" in result:
        return result["events"]
    elif isinstance(result, list):
        return result
    else:
        return [result] if result else []


def extract_events_from_ddr(
    ddr_text: str,
    well_id: str,
    report_date: str = "unknown",
    provider: Optional[str] = None
) -> list[dict]:
    """
    Main extraction function. Extracts structured drilling events from DDR text.
    
    Args:
        ddr_text: Raw text from a Daily Drilling Report
        well_id: Well identifier (e.g., "WELL-F9A")
        report_date: Date of the report (e.g., "2012-05-15")
        provider: "openai" or "google" (defaults to LLM_PROVIDER env var)
    
    Returns:
        List of event dicts conforming to event_schema.json
    """
    provider = provider or LLM_PROVIDER
    
    if not ddr_text or len(ddr_text.strip()) < 20:
        return []
    
    # Call appropriate LLM
    if provider == "openai":
        raw_events = extract_events_openai(ddr_text, well_id, report_date)
    elif provider == "google":
        raw_events = extract_events_google(ddr_text, well_id, report_date)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")
    
    # Post-process: add well_id, event_ids, source info
    processed = []
    for i, evt in enumerate(raw_events):
        evt["event_id"] = f"EVT-{len(processed):04d}"  # Will be reassigned by DB
        evt["well_id"] = well_id
        evt["source_type"] = "ddr_extraction"
        evt["source_report"] = f"DDR_{report_date}_{well_id}"
        evt.setdefault("confidence", 0.7)
        evt.setdefault("severity", "moderate")
        evt.setdefault("outcome", "unknown")
        evt.setdefault("mitigation", None)
        evt.setdefault("parameters", None)
        processed.append(evt)
    
    return processed


# ---------- BATCH PROCESSING ----------
def batch_extract_from_csv(
    csv_path: str,
    well_id: str = "WELL-F9A",
    text_column: str = "input",
    max_reports: int = 50,
    provider: Optional[str] = None
) -> list[dict]:
    """
    Batch-extract events from a CSV of DDR reports.
    
    Args:
        csv_path: Path to the Volve DDR CSV
        well_id: Default well ID to assign
        text_column: Column containing the DDR text
        max_reports: Max reports to process (API cost control)
        provider: LLM provider
    
    Returns:
        List of all extracted events
    """
    import pandas as pd
    
    df = pd.read_csv(csv_path)
    df = df.dropna(subset=[text_column])
    
    if len(df) > max_reports:
        print(f"Processing first {max_reports} of {len(df)} reports (cost control)")
        df = df.head(max_reports)
    
    all_events = []
    for idx, row in df.iterrows():
        text = str(row[text_column])
        report_date = f"report_{idx:04d}"
        
        try:
            events = extract_events_from_ddr(text, well_id, report_date, provider)
            all_events.extend(events)
            print(f"  [{idx+1}/{len(df)}] Extracted {len(events)} events")
        except Exception as e:
            print(f"  [{idx+1}/{len(df)}] ERROR: {e}")
    
    # Reassign sequential event IDs
    for i, evt in enumerate(all_events):
        evt["event_id"] = f"EVT-{i:04d}"
    
    print(f"\nTotal: {len(all_events)} events from {len(df)} reports")
    return all_events


# ---------- CLI ----------
if __name__ == "__main__":
    import sys
    
    # Quick test with a sample DDR
    sample_ddr = """
    00:30 - 06:00: MU baker windowmaster whipstock milling assembly. Continue TIH with DP.
    06:00 - 10:00: Continued TIH with windowmaster whipstock milling assembly. Tagged 9 5/8" bridge-plug at 2211 m dpm.
    10:00 - 12:00: Oriented whipstock using MWD. Set anchor on whipstock.
    12:00 - 18:00: Cut window in 9 5/8" casing using whipstock. Top of window 2202 m MD bottom of window 2207 m MD. 
    Pumped 5 m3 hi-vis pill while milling at 2205 m.
    18:00 - 21:00: Drilled/milled new formation from 2207 2213 m. Experienced partial mud losses at 2208 m.
    Pumped 5 m3 hi-vis pill while drilling at 2208 m.
    21:00 - 23:00: Reamed window. Unable to go down through window without rotating based on using maximum 
    of 12 MT weight. Possible stuck pipe situation averted by back-reaming.
    """
    
    print("=== NWIS NLP Extraction Test ===")
    print(f"Provider: {LLM_PROVIDER}")
    print(f"Input length: {len(sample_ddr)} chars\n")
    
    try:
        events = extract_events_from_ddr(sample_ddr, "WELL-F9A", "2012-05-15")
        print(f"Extracted {len(events)} events:\n")
        print(json.dumps(events, indent=2))
    except Exception as e:
        print(f"Error (expected if no API key set): {e}")
        print("\nTo test, set one of:")
        print("  set OPENAI_API_KEY=sk-...")
        print("  set GOOGLE_API_KEY=AI...")
        print("  set LLM_PROVIDER=google")
