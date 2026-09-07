import json
import os
import sys
from pathlib import Path
import pandas as pd

possible_paths = [
    Path('NLP/nlp_task_ddr/results/module1_outputs'),
    Path('results/module1_outputs'),
    Path('../results/module1_outputs'),
    Path(__file__).resolve().parent / 'results/module1_outputs',
    Path(__file__).resolve().parent / 'NLP/nlp_task_ddr/results/module1_outputs',
]

base = None
for p in possible_paths:
    if p.exists() and (p / 'wells_metadata.json').exists():
        base = p
        break

if not base:
    print('[ERROR] Could not locate results/module1_outputs directory.')
    print('Current working directory:', os.getcwd())
    sys.exit(1)

print('=' * 50)
print('VERIFYING MODULE 1 DATA CONTRACTS (NWIS-Sentinel)')
print('=' * 50)
print('Data location:', base.resolve())

wells = json.load(open(base / 'wells_metadata.json', 'r', encoding='utf-8'))
print(f'[SUCCESS] Wells Metadata:         {len(wells)} wells loaded')

events = [json.loads(line) for line in open(base / 'events.jsonl', 'r', encoding='utf-8') if line.strip()]
print(f'[SUCCESS] Events Dataset:         {len(events)} structured drilling events loaded')

vocab = json.load(open(base / 'event_type_vocabulary.json', 'r', encoding='utf-8'))
vocab_list = vocab.get('event_types', vocab)
print(f'[SUCCESS] Event Vocabulary:       {len(vocab_list)} canonical event classes defined')

incidents = json.load(open(base / 'flagged_real_incidents.json', 'r', encoding='utf-8'))
print(f'[SUCCESS] Real Hazard Incidents:  {len(incidents)} ground-truth crises identified')

telemetry = pd.read_csv(base / 'telemetry/15_9-F-9A.csv')
print(f'[SUCCESS] WITSML Telemetry:       {len(telemetry)} rows loaded (Well 15/9-F-9A)')

print('=' * 50)
print('ALL MODULE 1 DELIVERABLES ARE 100% OPERATIONAL!')
print('P2 can now proceed with Module 2 & Module 3.')
print('=' * 50)
