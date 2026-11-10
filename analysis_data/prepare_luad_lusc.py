
from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parent

# Existing LUAD files
LUAD_FILE = ROOT / "dataset" / "expression_samples.csv"
LABEL_FILE = ROOT / "dataset" / "sample_labels.csv"

# Downloaded LUSC file
LUSC_FILE = ROOT / "dataset_luad_lusc" / "raw" / "HiSeqV2"

# New output folder
OUTPUT_DIR = ROOT / "dataset_luad_lusc" / "processed"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

print("=" * 60)
print("PREPARING LUAD VS LUSC DATASET")
print("=" * 60)

# --------------------------------------------------
# 1. LOAD LUAD DATA
# --------------------------------------------------
print("\nLoading LUAD data...")

X_luad = pd.read_csv(LUAD_FILE, index_col=0)
y_luad = pd.read_csv(LABEL_FILE, index_col=0)

# Align existing labels
y_luad = y_luad.loc[X_luad.index]

# Keep only LUAD tumour samples
# Existing labels: 1 = tumour, 0 = normal
X_luad = X_luad.loc[y_luad["label"] == 1].copy()

print("LUAD tumour samples:", X_luad.shape[0])
print("LUAD genes:", X_luad.shape[1])

# --------------------------------------------------
# 2. LOAD LUSC DATA
# --------------------------------------------------
print("\nLoading LUSC data...")

# Xena HiSeqV2 is tab-separated, genes x samples
X_lusc = pd.read_csv(
    LUSC_FILE,
    sep="\t",
    index_col=0
).T

print("LUSC original shape:", X_lusc.shape)

# --------------------------------------------------
# 3. SELECT LUSC TUMOUR SAMPLES
# --------------------------------------------------
# TCGA sample type:
# 01-09 = primary/recurrent/metastatic tumour categories
# 11 = solid tissue normal
#
# For a consistent comparison, keep only type 01
# (primary solid tumour).

def sample_type(sample_id):
    parts = str(sample_id).split("-")
    if len(parts) < 4:
        return None
    return parts[3][:2]

X_lusc = X_lusc.loc[
    [sample_type(s) == "01" for s in X_lusc.index]
].copy()

# Apply the same primary-tumour criterion to LUAD
X_luad = X_luad.loc[
    [sample_type(s) == "01" for s in X_luad.index]
].copy()

print("LUSC primary tumour samples:", len(X_lusc))
print("LUAD primary tumour samples:", len(X_luad))

# --------------------------------------------------
# 4. ALIGN GENES
# --------------------------------------------------
print("\nAligning genes...")

if X_luad.columns.has_duplicates:
    raise ValueError("Duplicate gene names in LUAD data")

if X_lusc.columns.has_duplicates:
    raise ValueError("Duplicate gene names in LUSC data")

common_genes = X_luad.columns.intersection(
    X_lusc.columns,
    sort=False
)

print("LUAD genes:", X_luad.shape[1])
print("LUSC genes:", X_lusc.shape[1])
print("Common genes:", len(common_genes))

if len(common_genes) < 1000:
    raise ValueError(
        "Very low gene overlap. Check dataset compatibility."
    )

X_luad = X_luad.loc[:, common_genes]
X_lusc = X_lusc.loc[:, common_genes]

# --------------------------------------------------
# 5. CONVERT TO NUMERIC
# --------------------------------------------------
X_luad = X_luad.apply(pd.to_numeric, errors="coerce")
X_lusc = X_lusc.apply(pd.to_numeric, errors="coerce")

print("LUAD missing values:", int(X_luad.isna().sum().sum()))
print("LUSC missing values:", int(X_lusc.isna().sum().sum()))

# --------------------------------------------------
# 6. CHECK FOR OVERLAPPING PATIENTS
# --------------------------------------------------
luad_patients = set(
    X_luad.index.astype(str).str[:12]
)
lusc_patients = set(
    X_lusc.index.astype(str).str[:12]
)

overlap = luad_patients.intersection(lusc_patients)

if overlap:
    raise ValueError(
        f"Overlapping patient IDs between cohorts: {overlap}"
    )

# --------------------------------------------------
# 7. CREATE CLASS LABELS
# --------------------------------------------------
# LUAD = 0
# LUSC = 1

y_luad_new = pd.Series(
    0,
    index=X_luad.index,
    name="label"
)

y_lusc_new = pd.Series(
    1,
    index=X_lusc.index,
    name="label"
)

# --------------------------------------------------
# 8. COMBINE DATASETS
# --------------------------------------------------
X_combined = pd.concat(
    [X_luad, X_lusc],
    axis=0
)

y_combined = pd.concat(
    [y_luad_new, y_lusc_new],
    axis=0
).to_frame()

if X_combined.index.has_duplicates:
    raise ValueError("Duplicate sample IDs detected")

assert X_combined.index.equals(y_combined.index)

# --------------------------------------------------
# 9. SAVE PROCESSED DATA
# --------------------------------------------------
X_combined.to_csv(
    OUTPUT_DIR / "expression_combined.csv"
)

y_combined.to_csv(
    OUTPUT_DIR / "labels_combined.csv"
)

print("\n" + "=" * 60)
print("COMBINED DATASET CREATED")
print("=" * 60)

print("Dataset shape:", X_combined.shape)
print("\nClass distribution:")
print(y_combined["label"].value_counts())

print("\nClass mapping:")
print("0 = LUAD")
print("1 = LUSC")

print("\nFiles saved:")
print(OUTPUT_DIR / "expression_combined.csv")
print(OUTPUT_DIR / "labels_combined.csv")

print("\nExisting LungInsight AI files were not modified.")
