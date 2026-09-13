# NWIS-Sentinel Central Dashboard & Portal
### SIH 2026 | Problem Statement: SIH26121 | Oil India Limited

A terminal / BSPWM-inspired central operations dashboard serving as the unified command portal for the entire NWIS-Sentinel drilling intelligence platform.

---

## ⚡ Quick Start

### 1. Working Directory
```bash
cd NLP/nlp_task_ddr
```

### 2. Launch Unified Platform (Port 5000)
```bash
python gateway.py
```
Open **[http://localhost:5000](http://localhost:5000)** in your browser.

> **Unified Gateway Mode:** When running `python gateway.py`, all modules start under a single unified gateway on port 5000. Standalone dashboard debugging is also supported via `python dashboard/app.py --port 5000`.

---

## 🖥️ Interface Architecture (BSPWM / Alacritty Terminal Aesthetic)

The portal replicates a tiling-window-manager desktop environment:
- **Top BSPWM Bar**:
  - Virtual desktop / workspace tags (`1`, `2`, `3`, `4`, `5`).
  - Active window manager badge `[bspwm]`.
  - Centered live real-time system clock.
  - Live system resource monitors (`CPU: %`, `RAM: G`, `NET: ↑↓`).
- **Alacritty Terminal Window**:
  - Window control buttons (Close, Minimize, Maximize).
  - Terminal title banner: `alacritty — nwis@sentinel:~/system`.
  - **Dynamic Neofetch**:
    - ASCII NWIS-Sentinel triangle emblem rendered with line-by-line typewriter animation.
    - System specifications: Platform, Project, Partner (Oil India Limited), Stack, Wells (159), Single-Port Unified Gateway (:5000), and operational health.
    - ANSI color palette test blocks.
  - **Terminal Prompt**: `nwis@sentinel ~/system # ls -la` with blinking cursor.
- **Module Launch Cards (Indexed directory style)**:
  - **`module2/`** (`/module2/`) — Geospatial & Offset Similarity Engine (Leaflet, AHP, 159 Wells).
  - **`module3.live`** (`/module3/monitor`) — Real-Time Telemetry & Anomaly Monitor (CUSUM, Z-Score, WebSocket).
  - **`module4.graph`** (`/module4/`) — Knowledge Graph, GraphRAG & AI Briefing Studio (Vis.js, GraphRAG, Gemini).
  - **`module5.agent`** (`/module5/`) — Engineering RAG Decision Support Agent (ChromaDB, Gemini, Scenarios).
- **Automated Health Check**:
  - Automatically pings module health endpoints through the unified gateway in the background.
  - Visually updates cards (dimming inactive modules) and toggles system status indicators.

---

## 📁 Files

- `app.py`: Lightweight Flask web server serving the portal.
- `templates/dashboard.html`: Single-page responsive BSPWM/terminal UI.
