import joblib
from pathlib import Path
import warnings

import numpy as np
import pandas as pd

from sklearn.base import clone
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.feature_selection import VarianceThreshold, SelectKBest, f_classif
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier, AdaBoostClassifier
from sklearn.naive_bayes import GaussianNB
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    f1_score,
    recall_score,
    roc_auc_score,
    classification_report,
    confusion_matrix,
    log_loss
)

warnings.filterwarnings("ignore", category=RuntimeWarning)

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "dataset_luad_lusc" / "processed"
OUT_DIR = ROOT / "dataset_luad_lusc" / "results"
OUT_DIR.mkdir(parents=True, exist_ok=True)
ARTIFACT_DIR = ROOT / "artifacts"
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

ARTIFACT_PATH = ARTIFACT_DIR / "luad_lusc_ensemble.joblib"
RANDOM_STATE = 42
N_SPLITS = 3

# --------------------------------------------------
# 1. LOAD DATA
# --------------------------------------------------
print("=" * 65)
print("LUAD VS LUSC - SIX-MODEL ENSEMBLE EXPERIMENT")
print("=" * 65)

X = pd.read_csv(
    DATA_DIR / "expression_combined.csv",
    index_col=0
)
y = pd.read_csv(
    DATA_DIR / "labels_combined.csv",
    index_col=0
)["label"]

y = y.loc[X.index].astype(int)

if not set(y.unique()).issubset({0, 1}) or y.nunique() != 2:
    raise ValueError("Labels must be 0=LUAD and 1=LUSC.")

print("Dataset:", X.shape)
print("Class counts:\n", y.value_counts().sort_index())

# Same split settings as the Decision Tree baseline
X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.20,
    stratify=y,
    random_state=RANDOM_STATE
)

print("\nTraining samples:", len(X_train))
print("Test samples:", len(X_test))

# --------------------------------------------------
# 2. DEFINE MODELS
# --------------------------------------------------
models = {
    "Decision Tree": DecisionTreeClassifier(
        max_depth=5,
        min_samples_leaf=5,
        random_state=RANDOM_STATE
    ),
    "Random Forest": RandomForestClassifier(
        n_estimators=200,
        min_samples_leaf=2,
        class_weight="balanced",
        random_state=RANDOM_STATE,
        n_jobs=-1
    ),
    "AdaBoost": AdaBoostClassifier(
        n_estimators=100,
        learning_rate=0.5,
        random_state=RANDOM_STATE
    ),
    "Gaussian NB": GaussianNB(),
    "Logistic Regression": LogisticRegression(
        max_iter=2000,
        class_weight="balanced",
        random_state=RANDOM_STATE
    )
}

# Add XGBoost if installed
try:
    from xgboost import XGBClassifier

    models["XGBoost"] = XGBClassifier(
        n_estimators=150,
        max_depth=3,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.8,
        eval_metric="logloss",
        random_state=RANDOM_STATE,
        n_jobs=-1
    )
except ImportError:
    print("\nXGBoost is not installed; other models will still run.")
    print("To install it later: python -m pip install xgboost")

# --------------------------------------------------
# 3. BUILD PREPROCESSING PIPELINES
# --------------------------------------------------
def make_pipeline(classifier, model_name):
    steps = [
        ("imputer", SimpleImputer(strategy="median")),
        ("remove_constant", VarianceThreshold(threshold=0.0)),
        ("feature_selection", SelectKBest(
            score_func=f_classif,
            k=500
        ))
    ]

    if model_name == "Logistic Regression":
        steps.append(("scaler", StandardScaler()))

    steps.append(("classifier", clone(classifier)))
    return Pipeline(steps)


pipelines = {
    name: make_pipeline(model, name)
    for name, model in models.items()
}

# --------------------------------------------------
# 4. OUT-OF-FOLD TRAINING PREDICTIONS
#    Used only to estimate ensemble weights.
# --------------------------------------------------
cv = StratifiedKFold(
    n_splits=N_SPLITS,
    shuffle=True,
    random_state=2026
)

oof_probabilities = {}
oof_scores = {}

print("\nGenerating training-only out-of-fold predictions...")

for name, pipeline in pipelines.items():
    print("Cross-validating:", name)

    probabilities = cross_val_predict(
        pipeline,
        X_train,
        y_train,
        cv=cv,
        method="predict_proba",
        n_jobs=1
    )

    # Probability of class 1 = LUSC
    fitted_classes = np.unique(y_train)
    positive_index = list(fitted_classes).index(1)
    p_lusc = probabilities[:, positive_index]

    oof_probabilities[name] = p_lusc

    oof_predictions = (p_lusc >= 0.5).astype(int)
    score = f1_score(
        y_train,
        oof_predictions,
        average="macro"
    )
    oof_scores[name] = score

    print(f"  OOF macro F1: {score:.4f}")

# --------------------------------------------------
# 5. CALCULATE TRAINING-ONLY WEIGHTS
# --------------------------------------------------
scores = pd.Series(oof_scores, dtype=float).clip(lower=0)
weights = scores / scores.sum()

print("\nWeights learned from training-only OOF predictions:")
print(weights.sort_values(ascending=False).round(4))

weights.rename("weight").to_csv(
    OUT_DIR / "luad_lusc_ensemble_weights.csv"
)

# --------------------------------------------------
# 6. FIT INDIVIDUAL MODELS AND EVALUATE TEST SET
# --------------------------------------------------
rows = []
test_probabilities = {}
test_predictions = {}

def evaluate(name, y_true, predictions, probabilities):
    return {
        "model": name,
        "accuracy": accuracy_score(y_true, predictions),
        "balanced_accuracy": balanced_accuracy_score(
            y_true, predictions
        ),
        "macro_f1": f1_score(
            y_true, predictions, average="macro"
        ),
        "luad_recall": recall_score(
            y_true, predictions, pos_label=0
        ),
        "lusc_recall": recall_score(
            y_true, predictions, pos_label=1
        ),
        "roc_auc": roc_auc_score(y_true, probabilities),
        "log_loss": log_loss(
            y_true,
            np.column_stack([1 - probabilities, probabilities]),
            labels=[0, 1]
        )
    }

print("\nFitting models and evaluating the held-out test set...")

for name, pipeline in pipelines.items():
    print("Training:", name)
    pipeline.fit(X_train, y_train)

    probabilities = pipeline.predict_proba(X_test)
    positive_index = list(pipeline.classes_).index(1)
    p_lusc = probabilities[:, positive_index]
    predictions = (p_lusc >= 0.5).astype(int)

    test_probabilities[name] = p_lusc
    test_predictions[name] = predictions

    rows.append(evaluate(name, y_test, predictions, p_lusc))

# --------------------------------------------------
# 7. SIX-MODEL WEIGHTED ENSEMBLE
# --------------------------------------------------
ensemble_probability = np.zeros(len(X_test))

for name, weight in weights.items():
    ensemble_probability += weight * test_probabilities[name]

ensemble_prediction = (
    ensemble_probability >= 0.5
).astype(int)

rows.append(evaluate(
    "Adaptive Weighted Ensemble",
    y_test,
    ensemble_prediction,
    ensemble_probability
))

# Also evaluate equal-weight ensemble
equal_probability = np.mean(
    np.column_stack(list(test_probabilities.values())),
    axis=1
)
equal_prediction = (equal_probability >= 0.5).astype(int)

rows.append(evaluate(
    "Equal-Weight Ensemble",
    y_test,
    equal_prediction,
    equal_probability
))

# --------------------------------------------------
# 8. SAVE RESULTS
# --------------------------------------------------
results = pd.DataFrame(rows).sort_values(
    "macro_f1",
    ascending=False
)

results.to_csv(
    OUT_DIR / "luad_lusc_ensemble_comparison.csv",
    index=False
)

predictions_df = pd.DataFrame({
    "sample_id": X_test.index,
    "true_label": y_test.to_numpy(),
    **{
        f"pred_{name}": pred
        for name, pred in test_predictions.items()
    },
    "pred_adaptive_ensemble": ensemble_prediction,
    "pred_equal_ensemble": equal_prediction
})

predictions_df.to_csv(
    OUT_DIR / "luad_lusc_ensemble_predictions.csv",
    index=False
)
# --------------------------------------------------
# 10. SAVE FINAL SUBTYPE MODEL FOR STREAMLIT
# --------------------------------------------------
print("\nPreparing final subtype model for deployment...")

# Refit the pipelines on the complete dataset only after
# the held-out test evaluation and result files are saved.
# This does not change the previously calculated test metrics.
fitted_models = {}

for name, pipeline in pipelines.items():
    print("Refitting for deployment:", name)
    pipeline.fit(X, y)
    fitted_models[name] = pipeline

artifact = {
    "task": "LUAD_vs_LUSC",
    "feature_names": list(X.columns),
    "model_names": list(fitted_models.keys()),
    "models": fitted_models,
    "optimized_weights": weights.to_dict(),
    "class_names": {
        0: "LUAD",
        1: "LUSC"
    },
    "decision_threshold": 0.5,
    "weight_method": "Normalized training-only OOF macro-F1"
}

joblib.dump(artifact, ARTIFACT_PATH)

print("\nSubtype model artifact saved successfully:")
print(ARTIFACT_PATH)
print("Models saved:", list(fitted_models.keys()))
print("Weights saved:", artifact["optimized_weights"])
# --------------------------------------------------
# 9. PRINT DETAILED REPORTS
# --------------------------------------------------
print("\n" + "=" * 65)
print("MODEL COMPARISON - HELD-OUT TEST SET")
print("=" * 65)

print(results.to_string(
    index=False,
    formatters={
        col: "{:.4f}".format
        for col in results.select_dtypes(include="number").columns
    }
))

print("\nAdaptive ensemble classification report:")
print(classification_report(
    y_test,
    ensemble_prediction,
    labels=[0, 1],
    target_names=["LUAD", "LUSC"],
    zero_division=0
))

print("Adaptive ensemble confusion matrix:")
print(confusion_matrix(
    y_test,
    ensemble_prediction,
    labels=[0, 1]
))

print("\nFiles saved:")
print(OUT_DIR / "luad_lusc_ensemble_comparison.csv")
print(OUT_DIR / "luad_lusc_ensemble_weights.csv")
print(OUT_DIR / "luad_lusc_ensemble_predictions.csv")

print("\nExperiment complete. Existing project artifacts were not changed.")
