# Future Aspects & Roadmap for NWIS-Sentinel

This document compiles improvements and long-term architectural upgrades that are valuable for the project but are deferred beyond the immediate hackathon deadline.

## 1. Advanced NLP & Information Extraction
*   **Deep Learning NER (spaCy / BERT):** Replace the current regex + keyword lookup pipeline with fine-tuned Named Entity Recognition. The current approach hits ~70% of records. Utilizing models like `en_core_web_sm` or a domain-specific BERT model will capture the remaining 30% of complex, unstructured geological and operational entities.
*   **Causal Relation Extraction:** Build a dependency parser pass to extract `MITIGATED_BY` and `LED_TO` relationships. Currently, events are isolated. Linking "Mud Loss" -> "Pumped LCM" -> "Circulation Restored" automatically from text will vastly enrich the Knowledge Graph.

## 2. Telemetry & Data Processing Upgrades
*   **Direct WITSML / OPC-UA Ingestion:** The current architecture uses a WebSocket simulator to replay CSVs. For production deployment at OIL's eRTMAC, this simulation layer must be swapped for a live WITSML 1.4 / 2.0 SOAP/XML or OPC-UA connector.
*   **Scale to Multi-Well Telemetry:** The predictive pipeline is currently tested on a single well's full telemetry (15/9-F-9A). We need to source or synthesize high-frequency telemetry for multiple wells to stress-test the anomaly detection across diverse baseline operational signatures.
*   **Handle Channel Sparsity:** Modern rigs have higher-frequency sensors (e.g., Mud Density Out). The statistical engines (CUSUM/Z-score) should be tuned to dynamically adapt to intermittent or sparse channel sampling without triggering false alarms.

## 3. Modeling & Similarity Engine Enhancements
*   **Depth-Segmented Similarity:** The Module 2 similarity engine uses a well's average mud weight. A highly precise upgrade would compute similarity on a depth-by-depth basis (e.g., comparing analog mud weights specifically at the 1000m-1500m interval).
*   **Real-Only Confidence Intervals:** As real historical DDRs are integrated, the system should allow filtering the Wilson Confidence Interval sequence matching to explicitly exclude synthetic well events, relying 100% on empirical historical occurrences.
*   **Autoencoder Anomaly Baseline:** While the transparent statistical baseline (Z-Score/CUSUM) must remain the primary truth, an unsupervised deep learning autoencoder (reconstruction error) could run in parallel as a secondary signal for complex, multi-variate precursors.

## 4. UI & Dashboard Upgrades
*   **Multi-Well Parallel Monitoring:** Expand the dashboard to monitor 10+ active drilling rigs simultaneously using Celery or Ray for orchestration, matching the scale of enterprise operations.
*   **True GPS coordinates for all proxy data:** Replace the approximate NCS region coordinates used for FORCE 2020 wells with accurate wellhead coordinates to improve the geospatial radius search accuracy.
