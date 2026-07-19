import json
from collections import defaultdict
import pandas as pd
import sys
from pathlib import Path
sys.path.append('pipeline')
import yaml
from ingestion.loader import build_district_master
from imputation.imputer import impute_panel
from engine.normalizer import normalize
from engine.aggregator import aggregate

with open('data/scores.json') as f:
    data = json.load(f)

# 1. Cluster volumetrics & top 3 flagships
clusters = defaultdict(list)
for d in data['districts']:
    arch = d.get('archetype', 'Unknown')
    if not arch: arch = 'Unknown'
    score = d['scores']['overall']['current']
    clusters[arch].append({'name': d['districtName'], 'score': score})

print('=== CLUSTER VOLUMETRICS & FLAGSHIPS ===')
for arch, items in clusters.items():
    items.sort(key=lambda x: x['score'], reverse=True)
    top3 = items[:3]
    print(f'{arch} ({len(items)} districts):')
    for idx, item in enumerate(top3):
        name = item['name']
        score = item['score']
        print(f'  {idx+1}. {name} ({score:.2f})')

# 3. Pillar Correlation Check
with open('pipeline/config/index_config.yaml') as f:
    config = yaml.safe_load(f)

pipeline_dir = Path('pipeline')
xwalk = pd.read_csv('pipeline/crosswalk/district_crosswalk.csv', dtype=str)
raw_current, _ = build_district_master(config, xwalk, pipeline_dir, 2011)

raw_panel = {2011: raw_current}
imputed_panel = impute_panel(raw_panel, config)
imputed_current = imputed_panel[2011]
normed = normalize(imputed_current, config)
agg = aggregate(normed, config)

pillar_scores = agg['overall']['pillar_scores']
corr = pillar_scores.corr()
print('\n=== PILLAR CORRELATION MATRIX ===')
print(corr.round(3))
