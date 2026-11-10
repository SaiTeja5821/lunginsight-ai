
from pathlib import Path
import gzip
import pandas as pd

DATA_DIR = Path("dataset")

expression_file = next(DATA_DIR.glob("*.gz"))

# Read the expression matrix:
# rows = genes, columns = samples
with gzip.open(expression_file, "rt", encoding="utf-8") as file:
    expression = pd.read_csv(file, sep="\t", index_col=0)

print("Original dataset shape (genes, samples):", expression.shape)

# Transpose so rows = samples and columns = genes
X = expression.T

# TCGA sample type is encoded in characters 14-15
# 01 = primary solid tumour
# 11 = solid tissue normal
sample_type = X.index.to_series().str[13:15]

# Keep only the two classes required for this task
mask = sample_type.isin(["01", "11"])
X = X.loc[mask]
sample_type = sample_type.loc[mask]

# 1 = tumour, 0 = normal
y = (sample_type == "01").astype(int)

print("\nSamples x genes:", X.shape)
print("\nSample counts:")
print(sample_type.value_counts().rename(
    index={"01": "Tumour", "11": "Normal"}
))

print("\nClass counts:")
print(y.value_counts().rename(
    index={1: "Tumour (1)", 0: "Normal (0)"}
))

print("\nMissing values:", X.isna().sum().sum())
print("Duplicate gene columns:", X.columns.duplicated().sum())

print("\nFirst 5 samples and first 5 genes:")
print(X.iloc[:5, :5])

# Save the sample-level expression matrix and labels
X.to_csv(DATA_DIR / "expression_samples.csv")
y.rename("label").to_csv(DATA_DIR / "sample_labels.csv")

print("\nSaved expression_samples.csv and sample_labels.csv")
