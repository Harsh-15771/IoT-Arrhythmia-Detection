import pandas as pd
import numpy as np

csv_path = r'data\raw\mimic_ppg\metadata.csv'
out_path = r'data\raw\mimic_ppg\mimic_2000_balanced_cohort.csv'

print("Generating Clinically Balanced 2,000-Patient Cohort from metadata.csv...")

# Target 400 unique patients per major clinical category
targets = {
    'AF': 400,
    'SBRAD': 400,
    'STACH': 400,
    'PACED_BLOCK': 400, # VPACE, AVPACE, 1AVB, AFLT, APACE
    'SR': 400
}

collected = {k: [] for k in targets}
seen_patients = set()

paced_rhythms = {'VPACE', 'AVPACE', '1AVB', 'AFLT', 'APACE'}

chunk_size = 250_000
for chunk in pd.read_csv(csv_path, chunksize=chunk_size, low_memory=False):
    # Only pristine quality
    pristine = chunk[chunk['vector_10s_pleth_sqi'].astype(str).str.contains(r'\[1, 1, 1\]', na=False)]
    
    for _, row in pristine.iterrows():
        pid = str(row['patient'])
        if pid in seen_patients:
            continue
            
        rhythm = str(row['event_rhythm'])
        
        # Categorize
        cat = None
        if rhythm == 'AF' and len(collected['AF']) < targets['AF']:
            cat = 'AF'
        elif rhythm == 'SBRAD' and len(collected['SBRAD']) < targets['SBRAD']:
            cat = 'SBRAD'
        elif rhythm in ['STACH', 'SVTACH'] and len(collected['STACH']) < targets['STACH']:
            cat = 'STACH'
        elif rhythm in paced_rhythms and len(collected['PACED_BLOCK']) < targets['PACED_BLOCK']:
            cat = 'PACED_BLOCK'
        elif rhythm == 'SR' and len(collected['SR']) < targets['SR']:
            cat = 'SR'
            
        if cat is not None:
            seen_patients.add(pid)
            collected[cat].append(row)
            
        # Check if all filled
        if all(len(collected[k]) >= targets[k] for k in targets):
            break
            
    print("Progress:", {k: len(collected[k]) for k in targets})
    if all(len(collected[k]) >= targets[k] for k in targets):
        break

all_rows = []
for k in targets:
    all_rows.extend(collected[k])

df_balanced = pd.DataFrame(all_rows)
df_balanced.to_csv(out_path, index=False)
print(f"\nSUCCESS! Created {out_path} with {len(df_balanced)} UNIQUE patients!")
print(df_balanced['event_rhythm'].value_counts())
