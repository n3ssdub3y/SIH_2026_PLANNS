"""
NWIS-Sentinel: Synthetic Well Roster & Demo Data (P3's starting point)
Pre-built demo wells with coordinates, formations, and synthetic events.

This is the "institutional memory" seed data for the demo.
"""

import json

# ---------- SYNTHETIC WELL ROSTER ----------
# Based loosely on the Volve field layout (North Sea, Norwegian Continental Shelf)
# Real Volve coordinates: ~58.44°N, 1.90°E

DEMO_WELLS = [
    {
        "well_id": "WELL-F9A",
        "name": "F-9A (Active Well)",
        "latitude": 58.4430,
        "longitude": 1.8950,
        "total_depth_m": 2850,
        "formations": ["Nordland", "Hordaland", "Rogaland", "Shetland", "Viking", "Hugin", "Draupne"],
        "formation_tops_m": [0, 800, 1200, 1600, 1900, 2200, 2600],
        "spud_date": "2012-04-15",
        "status": "drilling"
    },
    {
        "well_id": "WELL-F11",
        "name": "F-11",
        "latitude": 58.4455,
        "longitude": 1.8980,
        "total_depth_m": 2920,
        "formations": ["Nordland", "Hordaland", "Rogaland", "Shetland", "Viking", "Hugin", "Draupne"],
        "formation_tops_m": [0, 810, 1220, 1590, 1880, 2190, 2580],
        "spud_date": "2011-06-20",
        "status": "completed"
    },
    {
        "well_id": "WELL-F14",
        "name": "F-14",
        "latitude": 58.4410,
        "longitude": 1.9020,
        "total_depth_m": 3100,
        "formations": ["Nordland", "Hordaland", "Rogaland", "Shetland", "Viking", "Hugin", "Draupne", "Heather"],
        "formation_tops_m": [0, 790, 1180, 1570, 1910, 2230, 2640, 2900],
        "spud_date": "2010-09-01",
        "status": "completed"
    },
    {
        "well_id": "WELL-F15",
        "name": "F-15",
        "latitude": 58.4470,
        "longitude": 1.8900,
        "total_depth_m": 2780,
        "formations": ["Nordland", "Hordaland", "Rogaland", "Shetland", "Viking", "Hugin"],
        "formation_tops_m": [0, 820, 1250, 1620, 1940, 2250],
        "spud_date": "2011-11-10",
        "status": "completed"
    },
    {
        "well_id": "WELL-F1",
        "name": "F-1",
        "latitude": 58.4390,
        "longitude": 1.8870,
        "total_depth_m": 3050,
        "formations": ["Nordland", "Hordaland", "Rogaland", "Shetland", "Viking", "Hugin", "Draupne"],
        "formation_tops_m": [0, 830, 1270, 1640, 1950, 2280, 2650],
        "spud_date": "2009-03-15",
        "status": "completed"
    },
    {
        "well_id": "WELL-F4",
        "name": "F-4",
        "latitude": 58.4500,
        "longitude": 1.9100,
        "total_depth_m": 2690,
        "formations": ["Nordland", "Hordaland", "Rogaland", "Shetland", "Viking", "Hugin"],
        "formation_tops_m": [0, 780, 1150, 1530, 1850, 2150],
        "spud_date": "2010-01-22",
        "status": "completed"
    },
    {
        "well_id": "WELL-F7",
        "name": "F-7",
        "latitude": 58.4350,
        "longitude": 1.9050,
        "total_depth_m": 2950,
        "formations": ["Nordland", "Hordaland", "Rogaland", "Shetland", "Viking", "Hugin", "Draupne"],
        "formation_tops_m": [0, 815, 1230, 1610, 1920, 2210, 2590],
        "spud_date": "2010-07-05",
        "status": "completed"
    },
    {
        "well_id": "WELL-F12",
        "name": "F-12",
        "latitude": 58.4420,
        "longitude": 1.9150,
        "total_depth_m": 2880,
        "formations": ["Nordland", "Hordaland", "Rogaland", "Shetland", "Viking", "Hugin", "Draupne"],
        "formation_tops_m": [0, 800, 1200, 1580, 1890, 2200, 2620],
        "spud_date": "2011-04-18",
        "status": "completed"
    }
]


# ---------- SYNTHETIC HISTORICAL EVENTS ----------
# These populate the event database for the demo.
# In production, these come from P1's NLP extraction pipeline.

DEMO_EVENTS = [
    # -- WELL-F11: Mud losses in Hugin formation --
    {
        "event_id": "EVT-0001",
        "well_id": "WELL-F11",
        "event_type": "mud_loss",
        "depth_start_m": 2195,
        "depth_end_m": 2210,
        "formation": "Hugin",
        "severity": "moderate",
        "description": "Partial mud losses at 2195-2210m in Hugin sandstone. Lost returns reduced to 80%. Pumped 8 m3 hi-vis pill.",
        "mitigation": "hi-vis pill (8 m3)",
        "outcome": "resolved",
        "duration_hours": 4.5,
        "parameters": {"mud_weight_sg": 1.32, "flow_rate_lpm": 2200, "spp_bar": 175},
        "source_type": "synthetic",
        "source_report": "DDR_2011-08-12_F11",
        "confidence": 0.9,
        "timestamp": "2011-08-12T14:00:00Z"
    },
    # -- WELL-F11: Stuck pipe in Viking --
    {
        "event_id": "EVT-0002",
        "well_id": "WELL-F11",
        "event_type": "stuck_pipe",
        "depth_start_m": 1895,
        "depth_end_m": 1895,
        "formation": "Viking",
        "severity": "high",
        "description": "Differentially stuck at 1895m in Viking shale. Overpull 15 MT above string weight. Jarring for 6 hours.",
        "mitigation": "jarring + spotting oil-based pill",
        "outcome": "resolved",
        "duration_hours": 8.0,
        "parameters": {"mud_weight_sg": 1.38, "spp_bar": 190},
        "source_type": "synthetic",
        "source_report": "DDR_2011-07-28_F11",
        "confidence": 0.92,
        "timestamp": "2011-07-28T06:00:00Z"
    },
    # -- WELL-F14: Severe mud losses in Hugin --
    {
        "event_id": "EVT-0003",
        "well_id": "WELL-F14",
        "event_type": "mud_loss",
        "depth_start_m": 2240,
        "depth_end_m": 2260,
        "formation": "Hugin",
        "severity": "high",
        "description": "Total losses at 2240-2260m in fractured Hugin sandstone. Lost 45 m3 mud. Required LCM pill (medium + fine) followed by cement squeeze.",
        "mitigation": "LCM pill + cement squeeze",
        "outcome": "resolved",
        "duration_hours": 18.0,
        "parameters": {"mud_weight_sg": 1.35, "flow_rate_lpm": 2400, "spp_bar": 165},
        "source_type": "synthetic",
        "source_report": "DDR_2010-11-15_F14",
        "confidence": 0.88,
        "timestamp": "2010-11-15T02:00:00Z"
    },
    # -- WELL-F14: Stuck pipe in Draupne --
    {
        "event_id": "EVT-0004",
        "well_id": "WELL-F14",
        "event_type": "stuck_pipe",
        "depth_start_m": 2660,
        "depth_end_m": 2660,
        "formation": "Draupne",
        "severity": "critical",
        "description": "Mechanically stuck at 2660m in Draupne shale. Unable to rotate or reciprocate. Free-point at 2580m. Required sidetrack.",
        "mitigation": "sidetrack (backoff at 2580m)",
        "outcome": "escalated",
        "duration_hours": 72.0,
        "parameters": {"mud_weight_sg": 1.42},
        "source_type": "synthetic",
        "source_report": "DDR_2010-12-01_F14",
        "confidence": 0.95,
        "timestamp": "2010-12-01T00:00:00Z"
    },
    # -- WELL-F15: Minor mud losses in Hugin --
    {
        "event_id": "EVT-0005",
        "well_id": "WELL-F15",
        "event_type": "mud_loss",
        "depth_start_m": 2260,
        "depth_end_m": 2275,
        "formation": "Hugin",
        "severity": "low",
        "description": "Minor seepage losses (5-10 bbl/hr) at 2260-2275m. No treatment required. Self-sealed.",
        "mitigation": None,
        "outcome": "resolved",
        "duration_hours": 2.0,
        "parameters": {"mud_weight_sg": 1.30, "flow_rate_lpm": 2100},
        "source_type": "synthetic",
        "source_report": "DDR_2012-01-05_F15",
        "confidence": 0.82,
        "timestamp": "2012-01-05T10:00:00Z"
    },
    # -- WELL-F1: Mud losses in Rogaland --
    {
        "event_id": "EVT-0006",
        "well_id": "WELL-F1",
        "event_type": "mud_loss",
        "depth_start_m": 1350,
        "depth_end_m": 1370,
        "formation": "Rogaland",
        "severity": "moderate",
        "description": "Partial losses in Rogaland limestone at 1350-1370m. Pumped 10 m3 LCM pill (fine + medium). Returns restored.",
        "mitigation": "LCM pill (10 m3)",
        "outcome": "resolved",
        "duration_hours": 5.0,
        "parameters": {"mud_weight_sg": 1.25},
        "source_type": "synthetic",
        "source_report": "DDR_2009-05-20_F1",
        "confidence": 0.85,
        "timestamp": "2009-05-20T08:00:00Z"
    },
    # -- WELL-F7: Stuck pipe in Viking shale --
    {
        "event_id": "EVT-0007",
        "well_id": "WELL-F7",
        "event_type": "stuck_pipe",
        "depth_start_m": 1930,
        "depth_end_m": 1930,
        "formation": "Viking",
        "severity": "moderate",
        "description": "Tight hole conditions at 1930m. Pack-off while tripping. Worked pipe free after 3 hours of back-reaming.",
        "mitigation": "back-reaming + wiper trip",
        "outcome": "resolved",
        "duration_hours": 3.0,
        "parameters": {"mud_weight_sg": 1.36},
        "source_type": "synthetic",
        "source_report": "DDR_2010-09-10_F7",
        "confidence": 0.80,
        "timestamp": "2010-09-10T16:00:00Z"
    },
    # -- WELL-F12: Mud losses + kick (dual event scenario) --
    {
        "event_id": "EVT-0008",
        "well_id": "WELL-F12",
        "event_type": "mud_loss",
        "depth_start_m": 2210,
        "depth_end_m": 2230,
        "formation": "Hugin",
        "severity": "high",
        "description": "Severe losses in Hugin fractured zone at 2210-2230m. Lost 30 m3. Followed by minor gas influx due to reduced hydrostatic.",
        "mitigation": "LCM + weighted pill",
        "outcome": "resolved",
        "duration_hours": 12.0,
        "parameters": {"mud_weight_sg": 1.33, "flow_rate_lpm": 2300, "spp_bar": 155},
        "source_type": "synthetic",
        "source_report": "DDR_2011-05-22_F12",
        "confidence": 0.87,
        "timestamp": "2011-05-22T04:00:00Z"
    },
    {
        "event_id": "EVT-0009",
        "well_id": "WELL-F12",
        "event_type": "kick",
        "depth_start_m": 2225,
        "depth_end_m": 2225,
        "formation": "Hugin",
        "severity": "moderate",
        "description": "Minor gas kick following mud losses. 5 bbl pit gain. Shut-in, circulated out. MW increased to 1.40 SG.",
        "mitigation": "shut-in + weighted mud (1.40 SG)",
        "outcome": "resolved",
        "duration_hours": 6.0,
        "parameters": {"mud_weight_sg": 1.40},
        "source_type": "synthetic",
        "source_report": "DDR_2011-05-22_F12",
        "confidence": 0.90,
        "timestamp": "2011-05-22T16:00:00Z"
    },
    # -- WELL-F4: Formation change (non-hazard event for completeness) --
    {
        "event_id": "EVT-0010",
        "well_id": "WELL-F4",
        "event_type": "formation_change",
        "depth_start_m": 2150,
        "depth_end_m": 2150,
        "formation": "Hugin",
        "severity": "low",
        "description": "Entered Hugin formation at 2150m. Clean sandstone, good ROP (25 m/hr). No drilling issues.",
        "mitigation": None,
        "outcome": "resolved",
        "duration_hours": 0,
        "parameters": {"rop_m_per_hr": 25, "mud_weight_sg": 1.28},
        "source_type": "synthetic",
        "source_report": "DDR_2010-03-10_F4",
        "confidence": 0.95,
        "timestamp": "2010-03-10T12:00:00Z"
    }
]


# ---------- DEMO SCENARIOS (Pre-scripted telemetry triggers) ----------
DEMO_SCENARIOS = [
    {
        "scenario_id": "SCENARIO_1",
        "name": "Approaching Hugin Formation — Mud Loss Risk",
        "description": "Active well F-9A is drilling at 2180m, about to enter Hugin formation at 2200m. Historical data shows 4 of 6 offset wells experienced mud losses in Hugin.",
        "trigger": {
            "active_well": "WELL-F9A",
            "depth_m": 2180,
            "formation": "Hugin",
            "hazard_type": "mud_loss"
        },
        "expected_analogs": ["WELL-F11", "WELL-F14", "WELL-F12", "WELL-F15"],
        "wow_moment": "Switch hazard dropdown to 'stuck_pipe' — analogs re-rank visibly. F-14 jumps up (had critical stuck pipe), F-15 drops (no stuck pipe events)."
    },
    {
        "scenario_id": "SCENARIO_2",
        "name": "Viking Shale — Stuck Pipe Risk",
        "description": "F-9A at 1890m in Viking shale. Torque trending up, overpull increasing.",
        "trigger": {
            "active_well": "WELL-F9A",
            "depth_m": 1890,
            "formation": "Viking",
            "hazard_type": "stuck_pipe"
        },
        "expected_analogs": ["WELL-F11", "WELL-F7"],
        "wow_moment": "LLM briefing shows F-11 was stuck for 8 hours (jarring + oil pill) while F-7 freed in 3 hours (back-reaming). Analogs DISAGREE on approach."
    },
    {
        "scenario_id": "SCENARIO_3",
        "name": "Deep Draupne — Maximum Risk Zone",
        "description": "F-9A at 2600m entering Draupne formation. This is where F-14 had a catastrophic stuck pipe requiring sidetrack.",
        "trigger": {
            "active_well": "WELL-F9A",
            "depth_m": 2600,
            "formation": "Draupne",
            "hazard_type": "stuck_pipe"
        },
        "expected_analogs": ["WELL-F14"],
        "wow_moment": "Critical severity alert. Only one analog with Draupne experience, and it failed (sidetrack). System flags HIGH UNCERTAINTY — limited analog support."
    }
]


def get_demo_data():
    """Return all demo data as a dict."""
    return {
        "wells": DEMO_WELLS,
        "events": DEMO_EVENTS,
        "scenarios": DEMO_SCENARIOS
    }


if __name__ == "__main__":
    data = get_demo_data()
    print(f"Wells: {len(data['wells'])}")
    print(f"Events: {len(data['events'])}")
    print(f"Scenarios: {len(data['scenarios'])}")
    print(f"\nWell names: {[w['name'] for w in data['wells']]}")
    print(f"Event types: {set(e['event_type'] for e in data['events'])}")
    print(f"\nScenarios:")
    for s in data['scenarios']:
        print(f"  {s['scenario_id']}: {s['name']}")
