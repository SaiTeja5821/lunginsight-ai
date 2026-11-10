import warnings
import numpy as np
import pandas as pd

from sklearn.base import clone
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.feature_selection import SelectKBest, f_classif
from sklearn.preprocessing import StandardScaler

from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier, AdaBoostClassifier
from sklearn.naive_bayes import GaussianNB
from sklearn.linear_model import LogisticRegression
from xgboost import XGBClassifier

from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    f1_score,
    recall_score,
    roc_auc_score,
)

warnings.filterwarnings("ignore")

# --------------------------------------------------
# 1. Load data and reproduce the original split
# --------------------------------------------------
DATA_DIR = "dataset"

X = pd.read_csv(
    f"{DATA_DIR}/expression_samples.csv", index_col=0
)
y = pd.read_csv(
    f"{DATA_DIR}/sample_labels.csv", index_col=0
).squeeze("columns")

y = y.loc[X.index].astype(int)

X_train, X_temp, y_train, y_temp = train_test_split(
    X, y, test_size=0.40, random_state=42, stratify=y
)
X_val, X_test, y_val, y_test = train_test_split(
    X_temp, y_temp, test_size=0.50,
    random_state=42, stratify=y_temp
)

# Use training + validation for development.
# Do not use the final test set for model selection.
X_dev = pd.concat([X_train, X_val])
y_dev = pd.concat([y_train, y_val])

print("Development samples:", len(X_dev))
print("Final test samples reserved:", len(X_test))

# --------------------------------------------------
# 2. Define five original models + Logistic Regression
# --------------------------------------------------
models = {
    "Decision Tree": DecisionTreeClassifier(
        max_depth=5, class_weight="balanced", random_state=42
    ),
    "Random Forest": RandomForestClassifier(
        n_estimators=200, class_weight="balanced",
        random_state=42, n_jobs=-1
    ),
    "XGBoost": XGBClassifier(
        n_estimators=100, max_depth=3, learning_rate=0.05,
        eval_metric="logloss", random_state=42, n_jobs=-1
    ),
    "AdaBoost": AdaBoostClassifier(
        n_estimators=100, random_state=42
    ),
    "Gaussian NB": GaussianNB(),
    "Logistic Regression": LogisticRegression(
        class_weight="balanced", max_iter=2000,
        random_state=42
    ),
}

def build_pipeline(model, scale=False):
    steps = [
        ("imputer", SimpleImputer(strategy="median")),
        ("select", SelectKBest(score_func=f_classif, k=500)),
    ]

    if scale:
        steps.append(("scaler", StandardScaler()))

    steps.append(("model", clone(model)))
    return Pipeline(steps)

def get_metrics(y_true, probabilities):
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

def adaptive_weights(oof_probs, y_true, names, metric):
    scores = []

    for name in names:
        predictions = (oof_probs[name] >= 0.5).astype(int)

        if metric == "f1":
            score = f1_score(
                y_true, predictions, pos_label=1,
                zero_division=0
            )
        elif metric == "balanced_accuracy":
            score = balanced_accuracy_score(
                y_true, predictions
            )
        else:
            raise ValueError("Unknown weighting metric")

        scores.append(score)

    scores = np.asarray(scores, dtype=float)

    if scores.sum() == 0:
        return np.ones(len(names)) / len(names)

    return scores / scores.sum()

# --------------------------------------------------
# 3. Development cross-validation
# --------------------------------------------------
outer_cv = StratifiedKFold(
    n_splits=5, shuffle=True, random_state=42
)

fold_results = []

for fold, (train_idx, val_idx) in enumerate(
    outer_cv.split(X_dev, y_dev), start=1
):
    print(f"\nDevelopment fold {fold}/5")

    X_fold_train = X_dev.iloc[train_idx]
    y_fold_train = y_dev.iloc[train_idx]
    X_fold_val = X_dev.iloc[val_idx]
    y_fold_val = y_dev.iloc[val_idx]

    # Generate validation probabilities for both ensembles.
    validation_probs = {}

    for name, model in models.items():
        pipeline = build_pipeline(
            model, scale=(name == "Logistic Regression")
        )
        pipeline.fit(X_fold_train, y_fold_train)

        validation_probs[name] = (
            pipeline.predict_proba(X_fold_val)[:, 1]
        )

    # Out-of-fold probabilities on outer training data
    # are used to calculate weights, never outer validation.
    inner_cv = StratifiedKFold(
        n_splits=3, shuffle=True, random_state=100 + fold
    )

    oof_probs = {}

    for name, model in models.items():
        oof_probs[name] = cross_val_predict(
            build_pipeline(
                model, scale=(name == "Logistic Regression")
            ),
            X_fold_train,
            y_fold_train,
            cv=inner_cv,
            method="predict_proba",
            n_jobs=1,
        )[:, 1]

    five_names = list(models.keys())[:5]
    six_names = list(models.keys())

    # Compare original five-model and new six-model ensembles.
    for ensemble_size, names in [
        ("Five-model", five_names),
        ("Six-model", six_names),
    ]:
        probs_matrix = np.column_stack(
            [validation_probs[name] for name in names]
        )

        approaches = {
            f"{ensemble_size} Equal-weight": probs_matrix.mean(axis=1)
        }

        for metric in ["f1", "balanced_accuracy"]:
            weights = adaptive_weights(
                oof_probs, y_fold_train, names, metric
            )

            weighted_probs = probs_matrix @ weights

            approaches[
                f"{ensemble_size} Adaptive {metric}"
            ] = weighted_probs

        for approach_name, probs in approaches.items():
            fold_results.append({
                "Fold": fold,
                "Model": approach_name,
                **get_metrics(y_fold_val, probs),
            })

    # Individual-model results
    for name, probs in validation_probs.items():
        fold_results.append({
            "Fold": fold,
            "Model": name,
            **get_metrics(y_fold_val, probs),
        })

    print("Completed fold", fold)

# --------------------------------------------------
# 4. Save and summarize results
# --------------------------------------------------
results_df = pd.DataFrame(fold_results)
results_df.to_csv(
    "ensemble_v3_development_folds.csv", index=False
)

metric_columns = [
    "Accuracy", "Balanced_Accuracy", "Macro_F1",
    "Normal_Recall", "Tumour_Recall", "ROC_AUC"
]

summary = results_df.groupby("Model")[metric_columns].agg(
    ["mean", "std"]
)
summary.to_csv("ensemble_v3_development_summary.csv")

print("\nDEVELOPMENT CROSS-VALIDATION SUMMARY")
print(summary.round(4).to_string())

print("\nSaved:")
print("- ensemble_v3_development_folds.csv")
print("- ensemble_v3_development_summary.csv")
print("\nFinal test set has NOT been evaluated.")