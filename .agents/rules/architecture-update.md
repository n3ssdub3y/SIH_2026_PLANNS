---
trigger: always_on
---

Always keep `ARCHITECTURE.md` synchronized with the **actual current implementation and architecture** of the project.

After any major architectural change, implementation change that affects system structure, module responsibilities, data flow, dependencies, models, APIs, integrations, inter-module communication, or deployment/runtime behavior, update `ARCHITECTURE.md` accordingly.

For every significant architectural change:

* Update the relevant existing sections rather than simply appending outdated information.
* Clearly document the new architecture, component responsibilities, data flow, inputs/outputs, dependencies, and interactions.
* Add or update **Mermaid diagrams** wherever they improve understanding of the architecture or data flow.
* Ensure diagrams and written explanations accurately reflect the current codebase.
* Remove or revise information that is no longer accurate after the change.
* Clearly distinguish implemented functionality from planned, experimental, simulated, or future functionality.
* Do not invent or assume architectural components, integrations, capabilities, or data flows that are not supported by the current implementation.

For minor changes that do not materially alter the architecture, update `ARCHITECTURE.md` with a concise 1–2 line note only when the change is architecturally relevant.

The goal is for `ARCHITECTURE.md` to remain a reliable **source of truth for the current system architecture**, not merely a historical changelog.
