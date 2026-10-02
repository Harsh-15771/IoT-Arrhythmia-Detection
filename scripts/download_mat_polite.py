import os
import sys
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

DATASET_DIR = "physionet_2015"
BASE_URL = "https://physionet.org/files/challenge-2015/1.0.0/training/"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

alarm_dict = {}
with open(os.path.join(DATASET_DIR, "ALARMS"), "r") as f:
    for line in f:
        line = line.strip()
        if not line: continue
        parts = line.split(",")
        if len(parts) == 3:
            alarm_dict[parts[0]] = (parts[1], int(parts[2]))

hea_files = sorted([f[:-4] for f in os.listdir(DATASET_DIR) if f.endswith(".hea")])

arrhythmias = []
normals = []

for rec in hea_files:
    if rec not in alarm_dict:
        continue
    alarm_type, is_true = alarm_dict[rec]
    
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
            arrhythmias.append(rec)
        else:
            normals.append(rec)

# Queue: all 231 arrhythmias + 70 normals = 301 records
download_queue = arrhythmias + normals[:70]
print(f"Target Queue: {len(arrhythmias)} Arrhythmias + 70 Normals = {len(download_queue)} records.", flush=True)

def download_one(rec):
    mat_file = f"{rec}.mat"
    mat_path = os.path.join(DATASET_DIR, mat_file)
    if os.path.exists(mat_path) and os.path.getsize(mat_path) > 1000:
        return rec, "exists"
    
    url = f"{BASE_URL}{mat_file}"
    for attempt in range(3):
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            if r.status_code == 200 and len(r.content) > 1000:
                with open(mat_path, "wb") as f:
                    f.write(r.content)
                return rec, "ok"
            elif r.status_code == 429: # Rate limited
                time.sleep(3)
        except Exception:
            time.sleep(2)
    return rec, "failed"

completed = 0
failed = 0
# Use 4 parallel workers with retry
with ThreadPoolExecutor(max_workers=4) as executor:
    futures = {executor.submit(download_one, rec): rec for rec in download_queue}
    for future in as_completed(futures):
        rec, status = future.result()
        if status in ("ok", "exists"):
            completed += 1
        else:
            failed += 1
        if completed % 10 == 0 or completed == len(download_queue):
            print(f"  [PhysioNet] Progress: {completed}/{len(download_queue)} ready (Failed: {failed})", flush=True)

print(f"\n[PhysioNet] Download task complete! Total records ready: {completed}", flush=True)
