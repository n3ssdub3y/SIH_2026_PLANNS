"""
Download Volve data from ACTUALLY WORKING sources
Run this script to get the data you need for the SIH demo.
"""
import subprocess
import sys
import os

OUTPUT_DIR = r"d:\New_folder\Desktop\SIH\volve_data"
os.makedirs(OUTPUT_DIR, exist_ok=True)

print("=" * 60)
print("Volve Data - Direct Download Guide")
print("=" * 60)

# ============================================================
# SOURCE 1: Volve DDRs for NLP (Hugging Face - BEST for your NLP module)
# ============================================================
print("""
[SOURCE 1] Volve DDRs - 1,759 Daily Drilling Reports (text)
-------------------------------------------------------------
Best for: NLP extraction pipeline, text processing

Run this in Python:

    from datasets import load_dataset
    ds = load_dataset("bengsoon/volve_alpaca")
    print(f"Train: {len(ds['train'])} reports")
    print(f"Test: {len(ds['test'])} reports")
    
    # Save to CSV
    ds['train'].to_csv("volve_ddrs_train.csv")
    ds['test'].to_csv("volve_ddrs_test.csv")

Or install datasets first:
    pip install datasets
""")

# ============================================================
# SOURCE 2: Volve Drilling Parameters (Kaggle - BEST for telemetry sim)
# ============================================================
print("""
[SOURCE 2] Volve Real-Time Drilling Data (CSV)
-------------------------------------------------------------
Best for: Telemetry simulator, drilling parameter analysis

Download from:
    https://www.kaggle.com/datasets/atunkiel/volve-dataset-well-f-9-a

Steps:
    1. Go to the URL above
    2. Click "Download" (need free Kaggle account)
    3. Extract ZIP to: d:\\New_folder\\Desktop\\SIH\\volve_data\\
    
Contains: ROP, WOB, torque, pressure, flow rate as time-series CSV
""")

# ============================================================
# SOURCE 3: 3W Dataset (GitHub - BEST for labeled drilling events)
# ============================================================
print("""
[SOURCE 3] Petrobras 3W - Labeled Drilling Events
-------------------------------------------------------------
Best for: Mud loss, kicks, stuck pipe EVENT labels

Clone from GitHub:
    git clone https://github.com/petrobras/3W.git d:\\New_folder\\Desktop\\SIH\\3W

Contains: Multivariate sensor data with labels for:
    - Kick
    - Loss of circulation (mud loss)
    - Stuck pipe
    - Flow instability
    - Other undesirable events
""")

# ============================================================
# SOURCE 4: DataDRILL (Zenodo - BEST for kick detection demo)
# ============================================================
print("""
[SOURCE 4] DataDRILL - Simulated Drilling Scenarios
-------------------------------------------------------------
Best for: Kick detection, formation pressure, demo telemetry

Download from:
    https://doi.org/10.5281/zenodo.12759014

Contains: 2,000+ scenarios, 28 drilling parameters each
""")

# ============================================================
# Try to auto-download Source 1 (HuggingFace DDRs)
# ============================================================
print("=" * 60)
print("Attempting auto-download of Source 1 (HuggingFace DDRs)...")
print("=" * 60)

try:
    # Check if datasets library is available
    from datasets import load_dataset
    
    print("Loading Volve DDRs from HuggingFace...")
    ds = load_dataset("bengsoon/volve_alpaca")
    
    train_path = os.path.join(OUTPUT_DIR, "volve_ddrs_train.csv")
    test_path = os.path.join(OUTPUT_DIR, "volve_ddrs_test.csv")
    
    ds['train'].to_csv(train_path)
    ds['test'].to_csv(test_path)
    
    print(f"[OK] Train set: {len(ds['train'])} reports -> {train_path}")
    print(f"[OK] Test set:  {len(ds['test'])} reports -> {test_path}")
    print(f"\nSample report:\n{'-'*40}")
    print(f"Input:  {ds['train'][0]['input'][:200]}...")
    print(f"Output: {ds['train'][0]['output'][:200]}...")
    
except ImportError:
    print("[INFO] 'datasets' library not installed. Installing...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "datasets"])
    print("[INFO] Installed! Re-run this script to download.")
    
except Exception as e:
    print(f"[ERROR] {e}")
    print("[INFO] Manual download: https://huggingface.co/datasets/bengsoon/volve_alpaca")

# ============================================================
# Try to auto-clone Source 3 (3W Dataset)
# ============================================================
print(f"\n{'='*60}")
print("Attempting auto-clone of Source 3 (3W Dataset)...")
print("=" * 60)

three_w_dir = r"d:\New_folder\Desktop\SIH\3W"
if os.path.exists(three_w_dir):
    print(f"[SKIP] 3W already exists at {three_w_dir}")
else:
    try:
        subprocess.check_call(["git", "clone", "--depth", "1", 
                              "https://github.com/petrobras/3W.git", three_w_dir])
        print(f"[OK] 3W dataset cloned to {three_w_dir}")
    except Exception as e:
        print(f"[ERROR] {e}")
        print("[INFO] Manual clone: git clone https://github.com/petrobras/3W.git")

print(f"\n{'='*60}")
print("[DONE] Check your data in:")
print(f"  DDRs:   {OUTPUT_DIR}")
print(f"  Events: {three_w_dir}")
print("=" * 60)
