
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

from scipy.optimize import minimize

from sklearn.model_selection import train_test_split, StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.feature_selection import SelectKBest, f_classif
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
    log_loss,
)
from xgboost import XGBClassifier


# ============================================================
# 1. LOAD DATA
# ============================================================

DATA_DIR = "dataset"

X_df = pd.read_csv(f"{DATA_DIR}/expression_samples.csv")
y_df = pd.read_csv(f"{DATA_DIR}/sample_labels.csv")

# Remove CSV index columns if they were saved accidentally.
X_df = X_df.loc[:, ~X_df.columns.astype(str).str.startswith("Unnamed:")]
y_df = y_df.loc[:, ~y_df.columns.astype(str).str.startswith("Unnamed:")]

# Identify the label column.
label_candidates = [
    c for c in y_df.columns
    if str(c).lower() in ["label", "labels", "target", "class", "y"]
]

if label_candidates:
    label_col = label_candidates[0]
else:
    # Assumes the final column contains the labels.
    label_col = y_df.columns[-1]

y_series = y_df[label_col]

# Align rows by sample IDs if both files contain a matching ID column.
id_candidates = ["sample_id", "sample", "sampleid", "sample_name"]

x_id_col = next(
    (c for c in X_df.columns if str(c).lower() in id_candidates), None
)
y_id_col = next(
    (c for c in y_df.columns if str(c).lower() in id_candidates), None
)

if x_id_col is not None and y_id_col is not None:
    X_df = X_df.set_index(x_id_col)
    y_df = y_df.set_index(y_id_col)
    y_series = y_df[label_col]
    common_ids = X_df.index.intersection(y_series.index)

    X_df = X_df.loc[common_ids]
    y_series = y_series.loc[common_ids]

elif len(X_df) != len(y_series):
    raise ValueError(
        "The expression and label files have different row counts. "
        "Check their sample IDs and alignment."
    )

# Keep numeric gene-expression features only.
X_df = X_df.select_dtypes(include=[np.number])

X = X_df.to_numpy(dtype=float)
y = y_series.to_numpy()

# Convert text labels if necessary.
if not np.issubdtype(y.dtype, np.number):
    label_map = {
        "normal": 0,
        "tumour": 1,
        "tumor": 1,
        "0": 0,
        "1": 1,
    }
    y = np.array([
        label_map.get(str(v).strip().lower(), v) for v in y
    ], dtype=int)
else:
    y = y.astype(int)

if set(np.unique(y)) != {0, 1}:
    raise ValueError(
        f"Expected binary labels 0 and 1, but found {np.unique(y)}"
    )

print("Dataset shape:", X.shape)
print("Class counts (0=normal, 1=tumour):", np.bincount(y))


# ============================================================
# 2. REPRODUCE THE ORIGINAL SPLIT
# ============================================================

X_train, X_temp, y_train, y_temp = train_test_split(
    X,
    y,
    test_size=0.40,
    random_state=42,
    stratify=y,
)

X_val, X_test, y_val, y_test = train_test_split(
    X_temp,
    y_temp,
    test_size=0.50,
    random_state=42,
    stratify=y_temp,
)

# Only training + validation data are used in this experiment.
X_dev = np.concatenate([X_train, X_val], axis=0)
y_dev = np.concatenate([y_train, y_val], axis=0)

print("\nDevelopment samples:", len(y_dev))
print("Final test samples reserved and untouched:", len(y_test))


# ============================================================
# 3. DEFINE THE SIX BASE MODELS
# ============================================================

def build_models():
    models = {
        "Decision Tree": Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("select", SelectKBest(score_func=f_classif, k=500)),
            ("model", DecisionTreeClassifier(
                max_depth=5,
                class_weight="balanced",
                random_state=42,
            )),
        ]),

        "Random Forest": Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("select", SelectKBest(score_func=f_classif, k=500)),
            ("model", RandomForestClassifier(
                n_estimators=200,
                class_weight="balanced",
                random_state=42,
                n_jobs=-1,
            )),
        ]),

        "XGBoost": Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("select", SelectKBest(score_func=f_classif, k=500)),
            ("model", XGBClassifier(
                n_estimators=100,
                max_depth=3,
                learning_rate=0.05,
                eval_metric="logloss",
                random_state=42,
                n_jobs=-1,
            )),
        ]),

        "AdaBoost": Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("select", SelectKBest(score_func=f_classif, k=500)),
            ("model", AdaBoostClassifier(
                n_estimators=100,
                random_state=42,
            )),
        ]),

        "Gaussian NB": Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("select", SelectKBest(score_func=f_classif, k=500)),
            ("model", GaussianNB()),
        ]),

        "Logistic Regression": Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("select", SelectKBest(score_func=f_classif, k=500)),
            ("scale", StandardScaler()),
            ("model", LogisticRegression(
                class_weight="balanced",
                max_iter=2000,
                random_state=42,
            )),
        ]),
    }

    return models


# ============================================================
# 4. HELPER FUNCTIONS
# ============================================================

def positive_probabilities(model, X_part):
    """Return probabilities for class 1 (tumour)."""
    probabilities = model.predict_proba(X_part)
    class_one_index = list(model.classes_).index(1)
    return probabilities[:, class_one_index]


def normalize_weights(scores):
    """Convert non-negative model scores into weights summing to 1."""
    scores = np.asarray(scores, dtype=float)
    scores = np.maximum(scores, 0)

    if scores.sum() == 0:
        return np.ones(len(scores)) / len(scores)

    return scores / scores.sum()


def learn_logloss_weights(oof_probs, y_true, regularization=0.05):
    """
    Learn non-negative weights that sum to 1.

    Minimize out-of-fold log loss, with a penalty for moving too far
    from equal weights. These weights are learned only on the
    outer-training fold's inner OOF predictions.
    """
    n_models = oof_probs.shape[1]
    equal_weights = np.ones(n_models) / n_models
    epsilon = 1e-7

    def objective(weights):
        combined = np.clip(
            oof_probs @ weights, epsilon, 1 - epsilon
        )

        data_loss = log_loss(
            y_true,
            combined,
            labels=[0, 1],
        )

        penalty = regularization * np.sum(
            (weights - equal_weights) ** 2
        )

        return data_loss + penalty

    result = minimize(
        objective,
        x0=equal_weights,
        method="SLSQP",
        bounds=[(0.0, 1.0)] * n_models,
        constraints={
            "type": "eq",
            "fun": lambda weights: np.sum(weights) - 1.0,
        },
        options={"maxiter": 500, "ftol": 1e-10},
    )

    if result.success:
        weights = np.maximum(result.x, 0)
        return weights / weights.sum()

    # Safe fallback if optimization fails.
    return equal_weights.copy()


def calculate_metrics(y_true, probabilities):
    predictions = (probabilities >= 0.5).astype(int)

    return {
        "Accuracy": accuracy_score(y_true, predictions),
        "Balanced Accuracy": balanced_accuracy_score(
            y_true, predictions
        ),
        "Macro F1": f1_score(
            y_true, predictions, average="macro", zero_division=0
        ),
        "Normal Recall": recall_score(
            y_true, predictions, pos_label=0, zero_division=0
        ),
        "Tumour Recall": recall_score(
            y_true, predictions, pos_label=1, zero_division=0
        ),
        "ROC AUC": roc_auc_score(y_true, probabilities),
        "Log Loss": log_loss(
            y_true,
            np.clip(probabilities, 1e-7, 1 - 1e-7),
            labels=[0, 1],
        ),
    }


# ============================================================
# 5. NESTED DEVELOPMENT CROSS-VALIDATION
# ============================================================

outer_cv = StratifiedKFold(
    n_splits=5, shuffle=True, random_state=42
)

all_fold_results = []
all_fold_weights = []

for fold_number, (outer_train_idx, outer_val_idx) in enumerate(
    outer_cv.split(X_dev, y_dev), start=1
):
    print(f"\n========== OUTER FOLD {fold_number}/5 ==========")

    X_outer_train = X_dev[outer_train_idx]
    y_outer_train = y_dev[outer_train_idx]
    X_outer_val = X_dev[outer_val_idx]
    y_outer_val = y_dev[outer_val_idx]

    model_names = list(build_models().keys())
    n_models = len(model_names)

    # Inner out-of-fold probabilities for learning weights.
    inner_oof_probs = np.zeros(
        (len(y_outer_train), n_models), dtype=float
    )

    inner_cv = StratifiedKFold(
        n_splits=3, shuffle=True, random_state=100 + fold_number
    )

    for inner_train_idx, inner_val_idx in inner_cv.split(
        X_outer_train, y_outer_train
    ):
        inner_models = build_models()

        for model_index, model_name in enumerate(model_names):
            model = inner_models[model_name]

            model.fit(
                X_outer_train[inner_train_idx],
                y_outer_train[inner_train_idx],
            )

            inner_oof_probs[inner_val_idx, model_index] = (
                positive_probabilities(
                    model, X_outer_train[inner_val_idx]
                )
            )

    # Learn weights only from inner OOF predictions.
    f1_scores = []
    balanced_scores = []

    for model_index in range(n_models):
        probs = inner_oof_probs[:, model_index]
        preds = (probs >= 0.5).astype(int)

        f1_scores.append(
            f1_score(
                y_outer_train, preds, pos_label=1, zero_division=0
            )
        )

        balanced_scores.append(
            balanced_accuracy_score(y_outer_train, preds)
        )

    f1_weights = normalize_weights(f1_scores)
    balanced_weights = normalize_weights(balanced_scores)
    logloss_weights = learn_logloss_weights(
        inner_oof_probs, y_outer_train, regularization=0.05
    )
    equal_weights = np.ones(n_models) / n_models

    print("Learned log-loss weights:")
    for name, weight in zip(model_names, logloss_weights):
        print(f"  {name}: {weight:.4f}")

    # Fit each model on the full outer-training fold and evaluate
    # on its held-out outer-validation fold.
    outer_val_probs = np.zeros(
        (len(y_outer_val), n_models), dtype=float
    )

    final_outer_models = build_models()

    for model_index, model_name in enumerate(model_names):
        model = final_outer_models[model_name]

        model.fit(X_outer_train, y_outer_train)

        outer_val_probs[:, model_index] = positive_probabilities(
            model, X_outer_val
        )

        metrics = calculate_metrics(
            y_outer_val, outer_val_probs[:, model_index]
        )

        all_fold_results.append({
            "Fold": fold_number,
            "Method": model_name,
            **metrics,
        })

    # Compare the four ensemble approaches.
    ensemble_probabilities = {
        "Equal Ensemble": outer_val_probs @ equal_weights,
        "F1 Weighted Ensemble": outer_val_probs @ f1_weights,
        "Balanced Accuracy Weighted Ensemble":
            outer_val_probs @ balanced_weights,
        "Optimized Log-Loss Ensemble":
            outer_val_probs @ logloss_weights,
    }

    for method_name, probs in ensemble_probabilities.items():
        metrics = calculate_metrics(y_outer_val, probs)

        all_fold_results.append({
            "Fold": fold_number,
            "Method": method_name,
            **metrics,
        })

    # Record weights for transparency.
    for model_index, model_name in enumerate(model_names):
        all_fold_weights.append({
            "Fold": fold_number,
            "Model": model_name,
            "Equal Weight": equal_weights[model_index],
            "F1 Weight": f1_weights[model_index],
            "Balanced Accuracy Weight":
                balanced_weights[model_index],
            "Optimized Log-Loss Weight":
                logloss_weights[model_index],
        })


# ============================================================
# 6. SUMMARIZE RESULTS
# ============================================================

results_df = pd.DataFrame(all_fold_results)
weights_df = pd.DataFrame(all_fold_weights)

metrics_columns = [
    "Accuracy",
    "Balanced Accuracy",
    "Macro F1",
    "Normal Recall",
    "Tumour Recall",
    "ROC AUC",
    "Log Loss",
]

summary = results_df.groupby("Method")[metrics_columns].agg(
    ["mean", "std"]
)

summary.columns = [
    f"{metric}_{stat}" for metric, stat in summary.columns
]
summary = summary.reset_index()

results_df.to_csv(
    "probability_weights_fold_results.csv", index=False
)
weights_df.to_csv(
    "probability_weights_per_fold.csv", index=False
)
summary.to_csv(
    "probability_weights_summary.csv", index=False
)

print("\n\n========== DEVELOPMENT CV SUMMARY ==========")

display_columns = [
    "Method",
    "Accuracy_mean",
    "Balanced Accuracy_mean",
    "Macro F1_mean",
    "Normal Recall_mean",
    "Tumour Recall_mean",
    "ROC AUC_mean",
    "Log Loss_mean",
]

print(
    summary[display_columns]
    .sort_values("Balanced Accuracy_mean", ascending=False)
    .round(4)
    .to_string(index=False)
)

print("\nSaved files:")
print("1. probability_weights_fold_results.csv")
print("2. probability_weights_per_fold.csv")
print("3. probability_weights_summary.csv")

print(
    "\nIMPORTANT: The reserved final test set was not used "
    "for training, weight selection, or this comparison."
)
