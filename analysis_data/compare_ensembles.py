
import warnings
import numpy as np
import pandas as pd

from sklearn.base import clone
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.feature_selection import SelectKBest, f_classif
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier, AdaBoostClassifier
from sklearn.naive_bayes import GaussianNB
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    f1_score,
    roc_auc_score,
    recall_score,
)
from xgboost import XGBClassifier

warnings.filterwarnings("ignore")

# --------------------------------------------------
# 1. Load the dataset
# --------------------------------------------------
DATA_DIR = "dataset"

X = pd.read_csv(
    f"{DATA_DIR}/expression_samples.csv", index_col=0
)
y = pd.read_csv(
    f"{DATA_DIR}/sample_labels.csv", index_col=0
).squeeze("columns")

y = y.loc[X.index].astype(int)

assert X.index.is_unique, "Duplicate sample IDs found."
assert X.index.equals(y.index), "Sample/label alignment failed."
assert set(y.unique()) == {0, 1}, "Expected labels 0 and 1."

print("Dataset:", X.shape)
print("Class counts:")
print(y.value_counts().sort_index().rename(
    index={0: "Normal", 1: "Tumour"}
))

# --------------------------------------------------
# 2. Define the same five classifiers
# --------------------------------------------------
models = {
    "Decision Tree": DecisionTreeClassifier(
        max_depth=5,
        class_weight="balanced",
        random_state=42,
    ),
    "Random Forest": RandomForestClassifier(
        n_estimators=200,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    ),
    "XGBoost": XGBClassifier(
        n_estimators=100,
        max_depth=3,
        learning_rate=0.05,
        eval_metric="logloss",
        random_state=42,
        n_jobs=-1,
    ),
    "AdaBoost": AdaBoostClassifier(
        n_estimators=100,
        random_state=42,
    ),
    "Gaussian NB": GaussianNB(),
}


def build_pipeline(model):
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("select", SelectKBest(score_func=f_classif, k=500)),
        ("model", clone(model)),
    ])


def calculate_metrics(y_true, probabilities):
    predictions = (probabilities >= 0.5).astype(int)

    return {
        "Accuracy": accuracy_score(y_true, predictions),
        "Balanced_Accuracy": balanced_accuracy_score(
            y_true, predictions
        ),
        "Macro_F1": f1_score(
            y_true, predictions, average="macro",
            zero_division=0
        ),
        "Normal_Recall": recall_score(
            y_true, predictions, pos_label=0,
            zero_division=0
        ),
        "Tumour_Recall": recall_score(
            y_true, predictions, pos_label=1,
            zero_division=0
        ),
        "ROC_AUC": roc_auc_score(y_true, probabilities),
    }


# --------------------------------------------------
# 3. Nested cross-validation comparison
# --------------------------------------------------
outer_cv = StratifiedKFold(
    n_splits=5, shuffle=True, random_state=42
)

results = []

for fold, (train_idx, test_idx) in enumerate(
    outer_cv.split(X, y), start=1
):
    print(f"\n========== OUTER FOLD {fold}/5 ==========")

    X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
    y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]

    # Inner OOF predictions determine weights using
    # only the outer training partition.
    inner_cv = StratifiedKFold(
        n_splits=3, shuffle=True, random_state=100 + fold
    )

    inner_probabilities = {}
    outer_test_probabilities = {}

    for name, model in models.items():
        print(f"Training/evaluating {name}...")

        pipeline = build_pipeline(model)

        # Every training fold fits its own imputer,
        # feature selector, and classifier.
        oof_probs = cross_val_predict(
            pipeline,
            X_train,
            y_train,
            cv=inner_cv,
            method="predict_proba",
            n_jobs=1,
        )[:, 1]

        inner_probabilities[name] = oof_probs

        # Fit only on the outer training partition.
        fitted = build_pipeline(model)
        fitted.fit(X_train, y_train)

        outer_test_probabilities[name] = (
            fitted.predict_proba(X_test)[:, 1]
        )

    # Calculate adaptive weights from inner out-of-fold F1.
    validation_f1 = {
        name: f1_score(
            y_train,
            (inner_probabilities[name] >= 0.5).astype(int),
            pos_label=1,
            zero_division=0,
        )
        for name in models
    }

    scores = np.array(
        [validation_f1[name] for name in models],
        dtype=float,
    )

    if scores.sum() == 0:
        weights = np.ones(len(scores)) / len(scores)
    else:
        weights = scores / scores.sum()

    print("Adaptive weights:")
    for name, weight in zip(models, weights):
        print(f"  {name}: {weight:.4f}")

    # Both ensembles use the same outer test samples.
    equal_probs = np.mean(
        np.column_stack(
            [outer_test_probabilities[n] for n in models]
        ),
        axis=1,
    )

    adaptive_probs = sum(
        weight * outer_test_probabilities[name]
        for name, weight in zip(models, weights)
    )

    approaches = {
        **outer_test_probabilities,
        "Equal-weight Ensemble": equal_probs,
        "Adaptive Weighted Ensemble": adaptive_probs,
    }

    for name, probabilities in approaches.items():
        row = {
            "Fold": fold,
            "Model": name,
            **calculate_metrics(y_test, probabilities),
        }
        results.append(row)

# --------------------------------------------------
# 4. Save fold-by-fold and summary results
# --------------------------------------------------
results_df = pd.DataFrame(results)
results_df.to_csv("ensemble_cv_fold_results.csv", index=False)

metric_columns = [
    "Accuracy",
    "Balanced_Accuracy",
    "Macro_F1",
    "Normal_Recall",
    "Tumour_Recall",
    "ROC_AUC",
]

summary = results_df.groupby("Model")[metric_columns].agg(
    ["mean", "std"]
)

summary.to_csv("ensemble_cv_summary.csv")

print("\n========== CROSS-VALIDATION SUMMARY ==========")
print(summary.round(4).to_string())

print("\nSaved:")
print("- ensemble_cv_fold_results.csv")
print("- ensemble_cv_summary.csv")
