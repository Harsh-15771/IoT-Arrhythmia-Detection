"""
Download and extract BUT PPG v2.0 (Brno University of Technology Smartphone PPG Database)
Open Access dataset from PhysioNet (CC BY 4.0)
Size: ~86.7 MB compressed (203 MB uncompressed)
3,888 recordings of 10-second smartphone PPG + reference 1000 Hz ECG + Accelerometry + Expert SQI
"""

import os
import sys
import zipfile
import urllib.request
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
TARGET_DIR = os.path.join(ROOT_DIR, "data", "raw", "but_ppg")
ZIP_PATH = os.path.join(ROOT_DIR, "data", "raw", "but_ppg_v2.zip")
URL = "https://physionet.org/content/butppg/get-zip/2.0.0/"

def reporthook(count, block_size, total_size):
    global start_time
    if count == 0:
        start_time = time.time()
        return
    duration = time.time() - start_time
    progress_size = int(count * block_size)
    speed = int(progress_size / (1024 * max(duration, 0.001)))
    percent = int(count * block_size * 100 / total_size) if total_size > 0 else 0
    sys.stdout.write(f"\rDownloading BUT PPG: {progress_size / (1024*1024):.1f} MB / {total_size / (1024*1024):.1f} MB ({percent}%) at {speed} KB/s")
    sys.stdout.flush()

def main():
    os.makedirs(os.path.dirname(TARGET_DIR), exist_ok=True)
    
    if not os.path.exists(ZIP_PATH):
        print(f"[INFO] Connecting to PhysioNet: {URL}")
        opener = urllib.request.build_opener()
        opener.addheaders = [('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)')]
        urllib.request.install_opener(opener)
        
        print(f"[INFO] Downloading to '{ZIP_PATH}' (~86.7 MB)...")
        urllib.request.urlretrieve(URL, ZIP_PATH, reporthook=reporthook)
        print("\n[SUCCESS] Download completed!")
    else:
        print(f"[INFO] Archive already exists at '{ZIP_PATH}'. Skipping download.")

    print(f"[INFO] Extracting to '{TARGET_DIR}'...")
    os.makedirs(TARGET_DIR, exist_ok=True)
    with zipfile.ZipFile(ZIP_PATH, 'r') as zip_ref:
        zip_ref.extractall(TARGET_DIR)
    
    print("[SUCCESS] Extraction completed!")
    extracted_files = [os.path.join(dp, f) for dp, dn, filenames in os.walk(TARGET_DIR) for f in filenames]
    print(f"[INFO] Total files in BUT PPG directory: {len(extracted_files)}")

if __name__ == "__main__":
    main()
