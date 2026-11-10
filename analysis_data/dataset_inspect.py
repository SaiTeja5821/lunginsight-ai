
from pathlib import Path
import gzip
import pandas as pd

# Project root: folder containing this script
ROOT = Path(__file__).resolve().parent

# --------------------------------------------------
# FILE PATHS
# --------------------------------------------------
raw_dir = ROOT / "dataset_luad_lusc" / "raw"
luad_file = ROOT / "dataset" / "expression_samples.csv"
labels_file = ROOT / "dataset" / "sample_labels.csv"

print("=" * 65)
print("LUNGINSIGHT AI - DATASET INSPECTION")
print("=" * 65)

# --------------------------------------------------
# 1. FIND THE DOWNLOADED LUSC FILE
# --------------------------------------------------
if not raw_dir.exists():
    raise FileNotFoundError(
        f"Folder not found: {raw_dir}\n"
        "Create dataset_luad_lusc/raw inside your project."
    )

matches = [
    p for p in raw_dir.iterdir()
    if p.is_file() and p.name.startswith("HiSeqV2")
]

if not matches:
    raise FileNotFoundError(
        f"No file starting with 'HiSeqV2' found in {raw_dir}\n"
        "Check the downloaded filename."
    )

if len(matches) > 1:
    print("Multiple matching files found:")
    for p in matches:
        print(" -", p.name)
    raise RuntimeError(
        "Keep only the intended LUSC expression file in raw, "
        "or update the script to select the correct file."
    )

lusc_file = matches[0]

print("\nLUSC file found:", lusc_file.name)
print("File size:", round(lusc_file.stat().st_size / (1024 * 1024), 2), "MB")

# --------------------------------------------------
# 2. READ THE FIRST FIVE LUSC LINES
#    Detect gzip from the actual file contents.
# --------------------------------------------------
print("\n" + "=" * 65)
print("LUSC FILE PREVIEW")
print("=" * 65)

with open(lusc_file, "rb") as f:
    magic = f.read(2)

is_gzip = magic == b"\x1f\x8b"

try:
    if is_gzip:
        opener = lambda: gzip.open(
            lusc_file, "rt", encoding="utf-8-sig", errors="replace"
        )
        print("Detected format: gzip-compressed text")
    else:
        opener = lambda: open(
            lusc_file, "rt", encoding="utf-8-sig", errors="replace"
        )
        print("Detected format: uncompressed text")

    with opener() as f:
        for i in range(5):
            line = f.readline()
            if not line:
                break
            print(line[:500].rstrip())

except (OSError, EOFError) as e:
    print("Could not preview the file:", e)
    raise

# --------------------------------------------------
# 3. INSPECT THE EXISTING LUAD DATASET
# --------------------------------------------------
print("\n" + "=" * 65)
print("EXISTING LUAD EXPRESSION DATA")
print("=" * 65)

if not luad_file.exists():
    raise FileNotFoundError(f"LUAD file not found: {luad_file}")

X_luad = pd.read_csv(luad_file, index_col=0)

print("File:", luad_file.name)
print("Shape:", X_luad.shape)
print("First 5 row IDs:", X_luad.index[:5].tolist())
print("First 8 column names:", X_luad.columns[:8].tolist())
print("\nFirst 3 rows and 5 columns:")
print(X_luad.iloc[:3, :5])
print("\nFirst column data type:", X_luad.dtypes.iloc[0])

# --------------------------------------------------
# 4. INSPECT THE EXISTING LABELS
# --------------------------------------------------
print("\n" + "=" * 65)
print("EXISTING LUAD LABELS")
print("=" * 65)

if not labels_file.exists():
    raise FileNotFoundError(f"Label file not found: {labels_file}")

y_luad = pd.read_csv(labels_file, index_col=0)

print("Label file:", labels_file.name)
print("Shape:", y_luad.shape)
print("Label columns:", y_luad.columns.tolist())
print("First 5 label rows:")
print(y_luad.head())

if y_luad.shape[1] > 0:
    print("\nLabel counts:")
    print(y_luad.iloc[:, 0].value_counts(dropna=False))

# --------------------------------------------------
# 5. SUMMARY
# --------------------------------------------------
print("\n" + "=" * 65)
print("INSPECTION COMPLETE - NO FILES MODIFIED")
print("=" * 65)
print("LUSC file:", lusc_file.name)
print("Gzip compressed:", is_gzip)
print("LUAD expression shape:", X_luad.shape)
print("LUAD label shape:", y_luad.shape)
print("\nNext: share this terminal output so we can")
print("verify gene IDs and expression format before combining.")
