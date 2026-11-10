
import warnings
warnings.filterwarnings("ignore")

from pathlib import Path

import joblib
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
from sklearn.metrics import f1_score, log_loss

from xgboost import XGBClassifier


# ==========================================
# 1. LOAD DATA
# ==========================================

X = pd.read_csv("dataset/expression_samples.csv", index_col=0)

y = pd.read_csv(
    "dataset/sample_labels.csv", index_col=0
).squeeze("columns")

y = y.loc[X.index].astype(int)

X_train, X_temp, y_train, y_temp = train_test_split(
    X, y,
    test_size=0.40,
    random_state=42,
    stratify=y
)

X_val, _, y_val, _ = train_test_split(
    X_temp, y_temp,
    test_size=0.50,
    random_state=42,
    stratify=y_temp
)

X_dev = pd.concat([X_train, X_val])
y_dev = pd.concat([y_train, y_val])

print("Development samples:", len(X_dev))
print("Gene features:", X.shape[1])


# ==========================================
# 2. DEFINE MODELS
# ==========================================

def build_models():
    return {
        "Decision Tree": DecisionTreeClassifier(
            max_depth=5,
            class_weight="balanced",
            random_state=42
        ),

        "Random Forest": RandomForestClassifier(
            n_estimators=200,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1
        ),

        "XGBoost": XGBClassifier(
            n_estimators=100,
            max_depth=3,
            learning_rate=0.05,
            eval_metric="logloss",
            random_state=42,
            n_jobs=-1
        ),

        "AdaBoost": AdaBoostClassifier(
            n_estimators=100,
            random_state=42
        ),

        "Gaussian NB": GaussianNB(),

        "Logistic Regression": LogisticRegression(
            class_weight="balanced",
            max_iter=2000,
            random_state=42
        )
    }


# ==========================================
# 3. BUILD PIPELINES
# ==========================================

def build_pipeline(name, model):
    steps = [
        ("imputer", SimpleImputer(strategy="median")),
        ("select", SelectKBest(score_func=f_classif, k=500))
    ]

    if name == "Logistic Regression":
        steps.append(("scale", StandardScaler()))

    steps.append(("model", model))

    return Pipeline(steps)


def get_positive_probability(model, data):
    probabilities = model.predict_proba(data)
    class_index = list(model.classes_).index(1)
    return probabilities[:, class_index]


# ==========================================
# 4. GENERATE OOF PROBABILITIES
# ==========================================

models = build_models()
model_names = list(models.keys())

oof_probs = np.zeros((len(y_dev), len(model_names)))

cv = StratifiedKFold(
    n_splits=5,
    shuffle=True,
    random_state=42
)

print("\nGenerating OOF probabilities...")

for fold, (train_idx, holdout_idx) in enumerate(
    cv.split(X_dev, y_dev), start=1
):
    print(f"Fold {fold}/5")

    X_fold_train = X_dev.iloc[train_idx]
    y_fold_train = y_dev.iloc[train_idx]
    X_fold_holdout = X_dev.iloc[holdout_idx]

    for j, name in enumerate(model_names):
        pipeline = build_pipeline(name, build_models()[name])

        pipeline.fit(X_fold_train, y_fold_train)

        oof_probs[holdout_idx, j] = get_positive_probability(
            pipeline, X_fold_holdout
        )


# ==========================================
# 5. LEARN ENSEMBLE WEIGHTS
# ==========================================

def optimize_logloss_weights(
    probabilities, labels, regularization=0.05
):
    n_models = probabilities.shape[1]
    initial_weights = np.ones(n_models) / n_models
    epsilon = 1e-7

    def objective(weights):
        combined = np.clip(
            probabilities @ weights,
            epsilon,
            1 - epsilon
        )

        loss = log_loss(labels, combined, labels=[0, 1])

        penalty = regularization * np.sum(
            (weights - initial_weights) ** 2
        )

        return loss + penalty

    result = minimize(
        objective,
        x0=initial_weights,
        method="SLSQP",
        bounds=[(0.0, 1.0)] * n_models,
        constraints={
            "type": "eq",
            "fun": lambda weights: weights.sum() - 1.0
        },
        options={"maxiter": 500, "ftol": 1e-10}
    )

    if not result.success:
        print("Optimization failed; using equal weights.")
        return initial_weights

    weights = np.maximum(result.x, 0)
    return weights / weights.sum()


optimized_weights = optimize_logloss_weights(
    oof_probs, y_dev
)

equal_weights = np.ones(len(model_names)) / len(model_names)

f1_scores = []

for j in range(len(model_names)):
    predictions = (oof_probs[:, j] >= 0.5).astype(int)

    f1_scores.append(
        f1_score(
            y_dev,
            predictions,
            pos_label=1,
            zero_division=0
        )
    )

f1_scores = np.asarray(f1_scores)

f1_weights = (
    f1_scores / f1_scores.sum()
    if f1_scores.sum() > 0
    else equal_weights.copy()
)

weights_table = pd.DataFrame({
    "Model": model_names,
    "Equal Weight": equal_weights,
    "F1 Weight": f1_weights,
    "Optimized Log-Loss Weight": optimized_weights
})

print("\nLearned ensemble weights:")
print(weights_table.round(4).to_string(index=False))


# ==========================================
# 6. FIT FINAL PIPELINES
# ==========================================

print("\nTraining final pipelines...")

fitted_models = {}

for name in model_names:
    print("Training:", name)

    pipeline = build_pipeline(name, build_models()[name])
    pipeline.fit(X_dev, y_dev)

    fitted_models[name] = pipeline


# ==========================================
# 7. SAVE MODELS, WEIGHTS AND FEATURES
# ==========================================

output_dir = Path("artifacts")
output_dir.mkdir(parents=True, exist_ok=True)

artifact = {
    "models": fitted_models,
    "model_names": model_names,

    "optimized_weights": dict(
        zip(model_names, optimized_weights.tolist())
    ),

    "f1_weights": dict(
        zip(model_names, f1_weights.tolist())
    ),

    "equal_weights": dict(
        zip(model_names, equal_weights.tolist())
    ),

    "feature_names": X.columns.tolist(),

    "positive_class": 1,
    "labels": {
        0: "Normal",
        1: "Tumour"
    },

    "selected_feature_count": 500,
    "random_state": 42,
    "development_sample_count": len(y_dev),

    "weighting_method": (
        "OOF optimized log-loss weights with "
        "0.05 regularization toward equal weights"
    )
}

model_path = output_dir / "lunginsight_ensemble.joblib"
weights_path = output_dir / "lunginsight_ensemble_weights.csv"

joblib.dump(artifact, model_path)
weights_table.to_csv(weights_path, index=False)

print("\n====================================")
print("MODEL SAVING COMPLETED")
print("====================================")
print("Saved model:", model_path)
print("Saved weights:", weights_path)
print("Saved pipelines:", len(fitted_models))
print("Saved gene features:", len(artifact["feature_names"]))
print("\nReady for the next integration step.")
