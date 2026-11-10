
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split

# Load expression data and labels
X_df = pd.read_csv("dataset/expression_samples.csv")
y_df = pd.read_csv("dataset/sample_labels.csv")

sample_ids = X_df["Unnamed: 0"].astype(str).to_numpy()
label_ids = y_df["Unnamed: 0"].astype(str).to_numpy()
y = y_df["label"].to_numpy()

# Stop if the rows are not aligned
assert np.array_equal(sample_ids, label_ids), (
    "ERROR: Sample IDs do not match in order."
)

# Reproduce the original split
indices = np.arange(len(y))

train_idx, temp_idx = train_test_split(
    indices,
    test_size=0.40,
    random_state=42,
    stratify=y,
)

val_idx, test_idx = train_test_split(
    temp_idx,
    test_size=0.50,
    random_state=42,
    stratify=y[temp_idx],
)

train_ids = set(sample_ids[train_idx])
val_ids = set(sample_ids[val_idx])
test_ids = set(sample_ids[test_idx])

print("Train samples:", len(train_ids))
print("Validation samples:", len(val_ids))
print("Final test samples:", len(test_ids))

print("\nOverlap checks:")
print("Train / validation:", len(train_ids & val_ids))
print("Train / test:", len(train_ids & test_ids))
print("Validation / test:", len(val_ids & test_ids))

print("\nClass counts in final test set:")
print(pd.Series(y[test_idx]).value_counts().sort_index()
      .rename(index={0: "Normal (0)", 1: "Tumour (1)"}))

print("\nFinal test sample IDs:")
print(sorted(test_ids))
