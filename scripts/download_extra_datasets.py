"""
Download open-access PPG datasets from PhysioNet:
1. BIDMC PPG and Respiration Dataset (bidmc) - 53 ICU records with clean PPG & vitals
2. Pulse Transit Time PPG Dataset (pulse-transit-time-ppg) - 66 records across diverse activities

Run with:
    python download_extra_datasets.py
"""

import os
import wfdb

DATASETS = [
    {
        "name": "bidmc",
        "dir": "bidmc_ppg",
        "records_limit": 53 # All 53 records
    },
    {
        "name": "pulse-transit-time-ppg",
        "dir": "ptt_ppg",
        "records_limit": 20 # Subset for diverse healthy baseline
    }
]

def download_datasets():
    for ds in DATASETS:
        target_dir = ds["dir"]
        os.makedirs(target_dir, exist_ok=True)
        print(f"\n=======================================================")
        print(f"Downloading {ds['name']} to '{target_dir}'...")
        print(f"=======================================================")
        try:
            records = wfdb.get_record_list(ds["name"])
            print(f"Found {len(records)} records in {ds['name']}.")
            
            # Select up to records_limit
            records_to_dl = records[:ds["records_limit"]]
            print(f"Downloading {len(records_to_dl)} records...")
            
            wfdb.dl_database(
                ds["name"],
                dl_dir=target_dir,
                records=records_to_dl
            )
            print(f"Successfully downloaded {ds['name']}!")
        except Exception as e:
            print(f"Error downloading {ds['name']}: {e}")

if __name__ == "__main__":
    download_datasets()
