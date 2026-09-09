# NWIS-Sentinel Central Dashboard & Portal
### SIH 2026 | Problem Statement: SIH26121 | Oil India Limited

A terminal / BSPWM-inspired central operations dashboard serving as the unified command portal for the entire NWIS-Sentinel drilling intelligence platform.

---

## ⚡ Quick Start

### 1. Working Directory
```bash
cd NLP/nlp_task_ddr
```

### 2. Launch Dashboard Server (Port 5000)
```bash
python dashboard/app.py --port 5000
```
Open **[http://localhost:5000](http://localhost:5000)** in your browser.

> **Orchestrated Mode:** When running `python run_all_modules.py`, the dashboard launches automatically as the primary entry point.

---

## 🖥️ Interface Architecture (BSPWM / Alacritty Terminal Aesthetic)

The portal replicates a tiling-window-manager desktop environment:
- **Top BSPWM Bar**:
  - Virtual desktop / workspace tags (`1`, `2`, `3`, `4`, `5`).
  - Active window manager badge `[bspwm]`.
  - Centered live real-time system clock.
  - Live system resource monitors (`CPU: %`, `RAM: G`, `NET: ↑↓`).
- **Alacritty Terminal Window**:
  - macOS / Linux window control buttons (Close, Minimize, Maximize).
  - Terminal title banner: `alacritty — nwis@sentinel:~/system`.
  - **Dynamic Neofetch**:
    - ASCII NWIS-Sentinel triangle emblem rendered with line-by-line typewriter animation.
    - System specifications: Platform, Project, Partner (Oil India Limited), Stack, Wells (159), Modules (4 active, ports 5001–5005), and operational health.
    - ANSI color palette test blocks.
  - **Terminal Prompt**: `nwis@sentinel ~/system # ls -la` with blinking cursor.
- **Module Launch Cards (Indexed directory style)**:
  - **`module2/`** (`:5001`) — Geospatial & Offset Similarity Engine (Leaflet, AHP, 159 Wells).
  - **`module3.live`** (`:5003`) — Real-Time Telemetry & Anomaly Monitor (CUSUM, Z-Score, WebSocket).
  - **`module4.graph`** (`:5004`) — Knowledge Graph, GraphRAG & AI Briefing Studio (Vis.js, GraphRAG, Gemini).
  - **`module5.agent`** (`:5005`) — Engineering RAG Decision Support Agent (ChromaDB, Gemini, Scenarios).
- **Automated Health Check**:
  - Automatically pings ports 5001, 5003, 5004, and 5005 in the background.
  - Visually updates cards (dimming inactive modules) and toggles system status indicators.

---

## 📁 Files

- `app.py`: Lightweight Flask web server serving the portal.
- `templates/dashboard.html`: Single-page responsive BSPWM/terminal UI.
