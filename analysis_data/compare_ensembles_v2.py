
import warnings
import numpy as np
import pandas as pd

from sklearn.model_selection import train_test_split, StratifiedKFold
from sklearn.base import clone
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.feature_selection import SelectKBest, f_classif

from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier, AdaBoostClassifier
from sklearn.naive_bayes import GaussianNB
from xgboost import XGBClassifier

from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    f1_score,
    recall_score,
    roc_auc_score,
)

warnings.filterwarnings("ignore")

# 1. Load data
DATA_DIR = "dataset"

X = pd.read_csv(
    f"{DATA_DIR}/expression_samples.csv", index_col=0
)
y = pd.read_csv(
    f"{DATA_DIR}/sample_labels.csv", index_col=0
).squeeze("columns")

y = y.loc[X.index].astype(int)

assert X.index.is_unique
assert X.index.equals(y.index)
assert set(y.unique()) == {0, 1}

# 2. Reproduce the original split exactly
X_train, X_temp, y_train, y_temp = train_test_split(
    X, y,
    test_size=0.40,
    random_state=42,
    stratify=y,
)

X_val, X_test, y_val, y_test = train_test_split(
    X_temp, y_temp,
    test_size=0.50,
    random_state=42,
    stratify=y_temp,
)

# Development data = original training + validation.
# Original test data remains separate.
X_dev = pd.concat([X_train, X_val])
y_dev = pd.concat([y_train, y_val])

print("Development samples:", len(X_dev))
print("Final test samples:", len(X_test))
print("Test sample IDs preserved:", X_test.index.is_unique)

# 3. Define models
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

def metrics(y_true, probabilities):
    predictions = (probabilities >= 0.5).astype(int)

    return {
        "Accuracy": accuracy_score(y_true, predictions),
        "Balanced_Accuracy": balanced_accuracy_score(
            y_true, predictions
        ),
        "Macro_F1": f1_score(
            y_true, predictions,
            average="macro", zero_division=0,
        ),
        "Normal_Recall": recall_score(
            y_true, predictions,
            pos_label=0, zero_division=0,
        ),
        "Tumour_Recall": recall_score(
            y_true, predictions,
            pos_label=1, zero_division=0,
        ),
        "ROC_AUC": roc_auc_score(y_true, probabilities),
    }

# 4. Cross-validation on development data ONLY
cv = StratifiedKFold(
    n_splits=5,
    shuffle=True,
    random_state=42,
)

fold_results = []

for fold, (train_idx, val_idx) in enumerate(
    cv.split(X_dev, y_dev), start=1
):
    print(f"\nDevelopment fold {fold}/5")

    X_fold_train = X_dev.iloc[train_idx]
    y_fold_train = y_dev.iloc[train_idx]

    X_fold_val = X_dev.iloc[val_idx]
    y_fold_val = y_dev.iloc[val_idx]

    val_probabilities = {}

    for name, model in models.items():
        pipeline = build_pipeline(model)
        pipeline.fit(X_fold_train, y_fold_train)

        val_probabilities[name] = (
            pipeline.predict_proba(X_fold_val)[:, 1]
        )

    # Equal-weight ensemble
    equal_probs = np.mean(
        np.column_stack(list(val_probabilities.values())),
        axis=1,
    )

    # Adaptive weights calculated ONLY from this fold's
    # training data using three-fold out-of-fold predictions.
    inner_cv = StratifiedKFold(
        n_splits=3,
        shuffle=True,
        random_state=100 + fold,
    )

    from sklearn.model_selection import cross_val_predict

    oof_probabilities = {}

    for name, model in models.items():
        oof_probabilities[name] = cross_val_predict(
            build_pipeline(model),
            X_fold_train,
            y_fold_train,
            cv=inner_cv,
            method="predict_proba",
            n_jobs=1,
        )[:, 1]

    inner_f1 = np.array([
        f1_score(
            y_fold_train,
            (oof_probabilities[name] >= 0.5).astype(int),
            zero_division=0,
        )
        for name in models
    ])

    if inner_f1.sum() == 0:
        weights = np.ones(len(models)) / len(models)
    else:
        weights = inner_f1 / inner_f1.sum()

    adaptive_probs = np.zeros(len(X_fold_val))

    for weight, name in zip(weights, models):
        adaptive_probs += weight * val_probabilities[name]

    approaches = {
        **val_probabilities,
        "Equal-weight Ensemble": equal_probs,
        "Adaptive Weighted Ensemble": adaptive_probs,
    }

    for name, probs in approaches.items():
        fold_results.append({
            "Fold": fold,
            "Model": name,
            **metrics(y_fold_val, probs),
        })

# 5. Save development comparison
results_df = pd.DataFrame(fold_results)
results_df.to_csv(
    "ensemble_v2_development_folds.csv",
    index=False,
)

summary = results_df.groupby("Model")[
    [
        "Accuracy",
        "Balanced_Accuracy",
        "Macro_F1",
        "Normal_Recall",
        "Tumour_Recall",
        "ROC_AUC",
    ]
].agg(["mean", "std"])

summary.to_csv("ensemble_v2_development_summary.csv")

print("\nDEVELOPMENT CROSS-VALIDATION SUMMARY")
print(summary.round(4).to_string())

print("\nSaved:")
print("- ensemble_v2_development_folds.csv")
print("- ensemble_v2_development_summary.csv")
print("\nThe final test set has not been evaluated.")
