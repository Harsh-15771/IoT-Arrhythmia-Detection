import os
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

DATASET_DIR = "physionet_2015"
BASE_URL = "https://physionet.org/files/challenge-2015/1.0.0/training/"

# Find all records with PLETH channel from .hea files
records_with_pleth = []
hea_files = sorted([f[:-4] for f in os.listdir(DATASET_DIR) if f.endswith(".hea")])

for rec_name in hea_files:
    hea_path = os.path.join(DATASET_DIR, rec_name + ".hea")
    channels = []
    with open(hea_path, "r", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) >= 9:
                channels.append(parts[-1].upper())
    
    if any(kw in ch for kw in ["PLETH", "PPG", "PULSE", "SPO2"] for ch in channels):
        records_with_pleth.append(rec_name)

print(f"Total records with PLETH channel to download: {len(records_with_pleth)}")

def download_record(rec_name):
    mat_filename = f"{rec_name}.mat"
    mat_path = os.path.join(DATASET_DIR, mat_filename)
    if os.path.exists(mat_path) and os.path.getsize(mat_path) > 1000:
        return rec_name, "already_exists"
    
    url = f"{BASE_URL}{mat_filename}"
    try:
        r = requests.get(url, timeout=30)
        if r.status_code == 200:
            with open(mat_path, "wb") as f:
                f.write(r.content)
            return rec_name, "downloaded"
        else:
            return rec_name, f"failed_status_{r.status_code}"
    except Exception as e:
        return rec_name, f"error_{e}"

# Download with 16 parallel threads
print("Starting high-speed parallel download...")
completed = 0
failed = 0

with ThreadPoolExecutor(max_workers=16) as executor:
    futures = {executor.submit(download_record, rec): rec for rec in records_with_pleth}
    for future in as_completed(futures):
        rec_name, status = future.result()
        if "downloaded" in status or "already_exists" in status:
            completed += 1
        else:
            failed += 1
        if completed % 50 == 0 or completed == len(records_with_pleth):
            print(f"  Progress: {completed}/{len(records_with_pleth)} records ready (Failed: {failed})...")

print(f"\nDownload finished! {completed} records available in '{DATASET_DIR}'.")
