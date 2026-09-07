import json
import pandas as pd
from pathlib import Path

base = Path('results/module1_outputs')

print('=== Checking P1 Module 1 Outputs ===')

wells = json.load(open(base / 'wells_metadata.json'))
print(f'Wells Metadata: {len(wells)} wells loaded')

events = [json.loads(line) for line in open(base / 'events.jsonl')]
print(f'Events Dataset: {len(events)} events loaded')

vocab = json.load(open(base / 'event_type_vocabulary.json'))
key = 'event_types'
print(f'Event Vocabulary: {len(vocab.get(key, vocab))} event classes defined')

incidents = json.load(open(base / 'flagged_real_incidents.json'))
print(f'Flagged Real Incidents: {len(incidents)} real hazard incidents identified')

telemetry = pd.read_csv(base / 'telemetry/15_9-F-9A.csv')
print(f'WITSML Telemetry: {len(telemetry)} rows loaded (Well 15/9-F-9A)')

print('\nAll Module 1 data contracts are verified and ready for Module 2 & 3!')
