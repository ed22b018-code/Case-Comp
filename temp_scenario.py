import json

with open('data/scores.json') as f:
    data = json.load(f)

# Task 1: Therapy Gap Analysis
districts = data['districts']
gap_list = []
for d in districts:
    c_score = d['scores']['chronic']['current']
    a_score = d['scores']['acute']['current']
    if c_score is not None and a_score is not None:
        gap = c_score - a_score
        gap_list.append({'name': d['districtName'], 'gap': gap, 'chronic': c_score, 'acute': a_score})

gap_list.sort(key=lambda x: x['gap'], reverse=True)

print('=== 1. THERAPY GAP ANALYSIS (Top 3 Chronic > Acute) ===')
for g in gap_list[:3]:
    name = g['name']
    gap = g['gap']
    c = g['chronic']
    a = g['acute']
    print(f'{name}: Gap of +{gap:.2f} (Chronic {c} vs Acute {a})')

# Task 2: Sensitivity Check
# Original Top 10
orig_sorted = sorted(districts, key=lambda x: x['scores']['overall']['current'], reverse=True)
orig_top10 = {d['districtName'] for d in orig_sorted[:10]}

# New weights
def calc_new_score(pillars):
    d = pillars.get('demand', 0)
    m = pillars.get('monetization', 0)
    a = pillars.get('access', 0)
    g = pillars.get('growth', 0)
    if d==0 or m==0 or a==0 or g==0: return 0
    return (d**0.25) * (m**0.30) * (a**0.25) * (g**0.20)

new_scores = []
for d in districts:
    pillars = d['pillars']['overall']
    new_s = calc_new_score(pillars)
    new_scores.append({'name': d['districtName'], 'score': new_s})

new_sorted = sorted(new_scores, key=lambda x: x['score'], reverse=True)
new_top10 = {d['name'] for d in new_sorted[:10]}

dropped = orig_top10 - new_top10
print('\n=== 2. SENSITIVITY CHECK ===')
print(f'Original Top 10: {list(orig_top10)}')
print(f'New Top 10: {list(new_top10)}')
print(f'Dropped out: {list(dropped)}')
print(f'Total dropped out: {len(dropped)}')
