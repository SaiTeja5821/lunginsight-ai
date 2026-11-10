
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.feature_selection import SelectKBest, f_classif
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    f1_score,
    classification_report,
    confusion_matrix
)

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "dataset_luad_lusc" / "processed"
OUTPUT_DIR = ROOT / "dataset_luad_lusc" / "results"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

print("Loading combined LUAD-LUSC dataset...")

X = pd.read_csv(
    DATA_DIR / "expression_combined.csv",
    index_col=0
)
y = pd.read_csv(
    DATA_DIR / "labels_combined.csv",
    index_col=0
)["label"]

y = y.loc[X.index].astype(int)

print("Dataset shape:", X.shape)
print("Labels:")
print(y.value_counts().sort_index())

# Hold out 20% for final evaluation.
# Do not use this test set to tune the model.
X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.20,
    stratify=y,
    random_state=42
)

print("\nTraining samples:", len(X_train))
print("Test samples:", len(X_test))

# Feature selection is fitted only on training data.
model = Pipeline([
    ("imputer", SimpleImputer(strategy="median")),
    ("feature_selection", SelectKBest(
        score_func=f_classif,
        k=min(500, X_train.shape[1])
    )),
    ("classifier", DecisionTreeClassifier(
        max_depth=5,
        min_samples_leaf=5,
        random_state=42
    ))
])

print("\nTraining baseline Decision Tree...")
model.fit(X_train, y_train)

predictions = model.predict(X_test)

accuracy = accuracy_score(y_test, predictions)
balanced_accuracy = balanced_accuracy_score(y_test, predictions)
macro_f1 = f1_score(
    y_test,
    predictions,
    average="macro"
)

print("\n" + "=" * 55)
print("LUAD VS LUSC - BASELINE RESULTS")
print("=" * 55)
print(f"Accuracy:          {accuracy:.4f} ({accuracy * 100:.2f}%)")
print(f"Balanced accuracy: {balanced_accuracy:.4f}")
print(f"Macro F1:          {macro_f1:.4f}")

print("\nClassification report:")
print(classification_report(
    y_test,
    predictions,
    labels=[0, 1],
    target_names=["LUAD", "LUSC"],
    zero_division=0
))

print("Confusion matrix (rows=true, columns=predicted):")
print(confusion_matrix(y_test, predictions, labels=[0, 1]))

# Save baseline results separately.
pd.DataFrame({
    "sample_id": X_test.index,
    "true_label": y_test.to_numpy(),
    "predicted_label": predictions
}).to_csv(OUTPUT_DIR / "baseline_test_predictions.csv", index=False)

pd.DataFrame([{
    "model": "Decision Tree baseline",
    "accuracy": accuracy,
    "balanced_accuracy": balanced_accuracy,
    "macro_f1": macro_f1,
    "training_samples": len(X_train),
    "test_samples": len(X_test)
}]).to_csv(OUTPUT_DIR / "baseline_metrics.csv", index=False)

print("\nResults saved in:", OUTPUT_DIR)
print("Existing LungInsight AI artifacts were not modified.")
