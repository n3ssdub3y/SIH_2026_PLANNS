import json
import os
from pathlib import Path
from typing import List, Dict, Any

from config import M1_EVENTS_JSONL, M1_FLAGGED_INCIDENTS, M2_ANALOG_WELLS

class DataAdapter:
    def __init__(self):
        self.events: List[Dict[str, Any]] = []
        self.flagged_incidents: List[Dict[str, Any]] = []
        self.analog_wells: Dict[str, Any] = {}
        self.load_data()

    def load_data(self):
        # Load Module 1 Events
        if os.path.exists(M1_EVENTS_JSONL):
            with open(M1_EVENTS_JSONL, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        self.events.append(json.loads(line))
        
        # Load Module 1 Flagged Incidents
        if os.path.exists(M1_FLAGGED_INCIDENTS):
            with open(M1_FLAGGED_INCIDENTS, 'r', encoding='utf-8') as f:
                self.flagged_incidents = json.load(f)

        # Load Module 2 Analog Wells
        if os.path.exists(M2_ANALOG_WELLS):
            with open(M2_ANALOG_WELLS, 'r', encoding='utf-8') as f:
                self.analog_wells = json.load(f)

    def get_top_analog_wells(self, well_id: str, hazard: str = None, top_k: int = 5) -> List[str]:
        """Get top analog well IDs for a given target well and hazard."""
        if well_id not in self.analog_wells:
            return []
        
        well_data = self.analog_wells[well_id]
        
        if hazard and hazard in well_data:
            analogs = well_data[hazard]
        else:
            # Flatten all analogs if hazard not specified or not found
            all_analogs = []
            for h in well_data.values():
                all_analogs.extend(h)
            analogs = sorted(all_analogs, key=lambda x: x.get('weighted_score', 0), reverse=True)
            
        # Deduplicate and return top_k
        seen = set()
        result = []
        for a in analogs:
            w_id = a['well_id']
            if w_id not in seen:
                seen.add(w_id)
                result.append(w_id)
                if len(result) >= top_k:
                    break
        return result

    def get_events_for_wells(self, well_ids: List[str]) -> List[Dict[str, Any]]:
        """Get all events for a list of well IDs."""
        well_id_set = set(well_ids)
        # Use flagged incidents as primary source of important evidence
        relevant_incidents = [evt for evt in self.flagged_incidents if evt.get('well_id') in well_id_set]
        
        if not relevant_incidents:
            # Fallback to general events if no flagged incidents found
             relevant_incidents = [evt for evt in self.events if evt.get('well_id') in well_id_set and evt.get('hazard', 'none') != 'none']
             
        return relevant_incidents
