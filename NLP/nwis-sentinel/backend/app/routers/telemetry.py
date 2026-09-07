"""Telemetry router — simulated real-time drilling data stream."""

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import json
import time
import random
import asyncio

router = APIRouter()

# Simulated telemetry state
_sim_state = {
    "depth_m": 2150,
    "rop_m_per_hr": 15.0,
    "wob_kN": 80,
    "torque_kNm": 12.5,
    "spp_bar": 185,
    "flow_rate_lpm": 2300,
    "mud_weight_sg": 1.32,
    "rpm": 120,
    "gas_units": 5,
    "active_well": "WELL-F9A"
}


@router.get("/current")
def get_current_telemetry():
    """Get current telemetry snapshot."""
    return _sim_state


@router.get("/stream")
async def stream_telemetry(
    start_depth: float = 2150,
    target_depth: float = 2250,
    speed: float = 1.0
):
    """
    Stream simulated telemetry as Server-Sent Events (SSE).
    Each event is a JSON object with current drilling parameters.
    
    Simulates drilling from start_depth to target_depth.
    Speed controls how fast (1.0 = normal, 5.0 = 5x speed for demo).
    """
    async def generate():
        depth = start_depth
        tick = 0
        
        while depth < target_depth:
            tick += 1
            
            # Advance depth
            rop = 12 + random.gauss(0, 2)  # m/hr ± noise
            depth += rop * (speed / 3600)  # per-second increment
            
            # Simulate parameters with realistic noise
            data = {
                "tick": tick,
                "timestamp": time.time(),
                "depth_m": round(depth, 2),
                "rop_m_per_hr": round(max(0, rop), 1),
                "wob_kN": round(75 + random.gauss(0, 5), 1),
                "torque_kNm": round(12 + random.gauss(0, 1.5), 1),
                "spp_bar": round(180 + random.gauss(0, 8), 0),
                "flow_rate_lpm": round(2300 + random.gauss(0, 50), 0),
                "mud_weight_sg": round(1.32 + random.gauss(0, 0.01), 3),
                "rpm": round(120 + random.gauss(0, 5), 0),
                "gas_units": round(max(0, 5 + random.gauss(0, 2)), 1),
                "well_id": "WELL-F9A"
            }
            
            # Inject anomaly precursors near hazard zones
            if 2190 <= depth <= 2220:
                # Approaching Hugin formation — simulate mud loss precursors
                data["spp_bar"] -= random.uniform(10, 25)  # Pressure drop
                data["flow_rate_lpm"] -= random.uniform(100, 300)  # Flow reduction
                data["gas_units"] += random.uniform(3, 8)  # Gas increase
                data["alert"] = {
                    "type": "mud_loss_precursor",
                    "message": f"SPP dropping, flow reduction at {depth:.0f}m — approaching known loss zone in Hugin formation",
                    "severity": "warning" if depth < 2200 else "critical"
                }
            
            if 1880 <= depth <= 1910:
                # Viking shale zone — stuck pipe precursors
                data["torque_kNm"] += random.uniform(3, 8)  # Torque increase
                data["wob_kN"] += random.uniform(10, 20)  # Overpull
                data["alert"] = {
                    "type": "stuck_pipe_precursor",
                    "message": f"Torque trending up at {depth:.0f}m in Viking shale — historical stuck pipe zone",
                    "severity": "warning"
                }
            
            # Update global state
            _sim_state.update(data)
            
            # Send SSE
            yield f"data: {json.dumps(data)}\n\n"
            await asyncio.sleep(1.0 / speed)
        
        # Final message
        yield f"data: {json.dumps({'tick': tick + 1, 'status': 'completed', 'final_depth_m': round(depth, 2)})}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )
