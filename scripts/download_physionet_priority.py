import os
import sys
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

DATASET_DIR = "physionet_2015"
BASE_URL = "https://physionet.org/files/challenge-2015/1.0.0/training/"

# Parse ALARMS to prioritize arrhythmias first
alarm_dict = {}
with open(os.path.join(DATASET_DIR, "ALARMS"), "r") as f:
    for line in f:
        line = line.strip()
        if not line: continue
        parts = line.split(",")
        if len(parts) == 3:
            alarm_dict[parts[0]] = (parts[1], int(parts[2]))

# Filter records with PLETH
hea_files = sorted([f[:-4] for f in os.listdir(DATASET_DIR) if f.endswith(".hea")])
arrhythmia_records = []
normal_records = []

for rec in hea_files:
    if rec not in alarm_dict:
        continue
    alarm_type, is_true = alarm_dict[rec]
    
    # Check if has PLETH channel
    hea_path = os.path.join(DATASET_DIR, rec + ".hea")
    has_pleth = False
    with open(hea_path, "r", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"): continue
            parts = line.split()
            if len(parts) >= 9 and any(kw in parts[-1].upper() for kw in ["PLETH", "PPG", "PULSE", "SPO2"]):
                has_pleth = True
                break
    
    if has_pleth:
        if is_true == 1:
            arrhythmia_records.append(rec)
        else:
            normal_records.append(rec)

# Prioritized list: all 231 true arrhythmias + 120 normal records = 351 balanced records
priority_list = arrhythmia_records + normal_records[:120]
print(f"Prioritized download queue: {len(arrhythmia_records)} Arrhythmias + 120 Normals = {len(priority_list)} records total.", flush=True)

# Thread-local session for high throughput
thread_local = {}

def get_session():
    import threading
    tid = threading.get_ident()
    if tid not in thread_local:
        s = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20, max_retries=3)
        s.mount('https://', adapter)
        thread_local[tid] = s
    return thread_local[tid]

def download_one(rec_name):
    mat_filename = f"{rec_name}.mat"
    mat_path = os.path.join(DATASET_DIR, mat_filename)
    if os.path.exists(mat_path) and os.path.getsize(mat_path) > 1000:
        return rec_name, "exists"
    
    url = f"{BASE_URL}{mat_filename}"
    session = get_session()
    try:
        r = session.get(url, timeout=25)
        if r.status_code == 200:
            with open(mat_path, "wb") as f:
                f.write(r.content)
            return rec_name, "ok"
        else:
            return rec_name, f"status_{r.status_code}"
    except Exception as e:
        return rec_name, f"err_{e}"

completed = 0
failed = 0
print("Launching 20 worker threads...", flush=True)

with ThreadPoolExecutor(max_workers=20) as executor:
    futures = {executor.submit(download_one, rec): rec for rec in priority_list}
    for future in as_completed(futures):
        rec_name, status = future.result()
        if status in ("ok", "exists"):
            completed += 1
        else:
            failed += 1
        if completed % 25 == 0 or completed == len(priority_list):
            print(f"  Downloaded: {completed}/{len(priority_list)} records (Failed: {failed})", flush=True)

print(f"\nPhase 1 Download Complete! {completed} records ready for training.", flush=True)
