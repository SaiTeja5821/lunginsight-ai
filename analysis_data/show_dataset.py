
import pandas as pd
from pathlib import Path

data_dir = Path("dataset")

X = pd.read_csv(
    data_dir / "expression_samples.csv",
    index_col=0
)

y = pd.read_csv(
    data_dir / "sample_labels.csv",
    index_col=0
).squeeze("columns")

# Show a small, readable preview
print("DATASET OVERVIEW")
print("----------------")
print("Number of samples:", X.shape[0])
print("Number of gene features:", X.shape[1])
print("Tumour samples:", int((y == 1).sum()))
print("Normal samples:", int((y == 0).sum()))

print("\nFIRST 5 SAMPLES AND FIRST 8 GENES")
print(X.iloc[:5, :8].to_string())

print("\nSAMPLE LABELS")
print(y.head())

# Save a small preview that opens easily in Excel
preview = X.iloc[:, :8].copy()
preview.insert(0, "Class", y.map({1: "Tumour", 0: "Normal"}))
preview.to_csv(data_dir / "dataset_preview.csv")

print("\nPreview saved to dataset/dataset_preview.csv")
