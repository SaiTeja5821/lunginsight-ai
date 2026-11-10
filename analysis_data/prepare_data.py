
import pandas as pd
from sklearn.model_selection import train_test_split

DATA_DIR = "dataset"

# Load the files created by inspect_dataset.py
X = pd.read_csv(
    f"{DATA_DIR}/expression_samples.csv",
    index_col=0
)

y = pd.read_csv(
    f"{DATA_DIR}/sample_labels.csv",
    index_col=0
).squeeze("columns")

# Ensure the sample IDs and labels match
y = y.loc[X.index].astype(int)

# 60% training, 20% validation, 20% testing
X_train, X_temp, y_train, y_temp = train_test_split(
    X,
    y,
    test_size=0.40,
    random_state=42,
    stratify=y
)

X_val, X_test, y_val, y_test = train_test_split(
    X_temp,
    y_temp,
    test_size=0.50,
    random_state=42,
    stratify=y_temp
)

print("Training set:", X_train.shape)
print("Validation set:", X_val.shape)
print("Test set:", X_test.shape)

print("\nTraining labels:")
print(y_train.value_counts())

print("\nValidation labels:")
print(y_val.value_counts())

print("\nTest labels:")
print(y_test.value_counts())

print("\nSample overlap checks:")
print("Train/validation:", len(set(X_train.index) & set(X_val.index)))
print("Train/test:", len(set(X_train.index) & set(X_test.index)))
print("Validation/test:", len(set(X_val.index) & set(X_test.index)))
