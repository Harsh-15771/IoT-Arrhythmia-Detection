import os
import wfdb

target_dir = "bidmc_ppg"
os.makedirs(target_dir, exist_ok=True)
records = wfdb.get_record_list("bidmc")
print(f"Total BIDMC records: {len(records)}")

for rec in records:
    hea_file = os.path.join(target_dir, f"{rec}.hea")
    dat_file = os.path.join(target_dir, f"{rec}.dat")
    if os.path.exists(hea_file) and os.path.exists(dat_file):
        continue
    try:
        wfdb.dl_files("bidmc", target_dir, [f"{rec}.hea", f"{rec}.dat"])
        print(f"Downloaded {rec}")
    except Exception as e:
        print(f"Failed {rec}: {e}")

print("BIDMC download complete!")
