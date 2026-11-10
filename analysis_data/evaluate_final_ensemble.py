
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
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    log_loss,
    confusion_matrix,
    classification_report,
)

from xgboost import XGBClassifier


# =====================================================
# 1. LOAD DATA AND REPRODUCE THE ORIGINAL SPLIT
# =====================================================

X = pd.read_csv(
    "dataset/expression_samples.csv", index_col=0
)
y = pd.read_csv(
    "dataset/sample_labels.csv", index_col=0
).squeeze("columns")

# Ensure labels align with expression samples.
y = y.loc[X.index].astype(int)

X_train, X_temp, y_train, y_temp = train_test_split(
    X, y, test_size=0.40, random_state=42, stratify=y
)

X_val, X_test, y_val, y_test = train_test_split(
    X_temp, y_temp, test_size=0.50,
    random_state=42, stratify=y_temp
)

# Combine training and validation for model development.
X_dev = pd.concat([X_train, X_val])
y_dev = pd.concat([y_train, y_val])

print("Development samples:", len(y_dev))
print("Final comparison samples:", len(y_test))
print("Test class counts:")
print(y_test.value_counts().sort_index())


# =====================================================
# 2. DEFINE SIX MODELS
# =====================================================

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


def build_pipeline(name, model):
    steps = [
        ("imputer", SimpleImputer(strategy="median")),
        ("select", SelectKBest(score_func=f_classif, k=500))
    ]

    if name == "Logistic Regression":
        steps.append(("scale", StandardScaler()))

    steps.append(("model", model))
    return Pipeline(steps)


def get_positive_probability(model, X_part):
    probabilities = model.predict_proba(X_part)
    class_index = list(model.classes_).index(1)
    return probabilities[:, class_index]


# =====================================================
# 3. GENERATE DEVELOPMENT OUT-OF-FOLD PROBABILITIES
# =====================================================

model_names = list(build_models().keys())

oof_probs = np.zeros((len(y_dev), len(model_names)))

cv = StratifiedKFold(
    n_splits=5, shuffle=True, random_state=42
)

print("\nGenerating development OOF predictions...")

for fold, (train_idx, holdout_idx) in enumerate(
    cv.split(X_dev, y_dev), start=1
):
    print(f"Development fold {fold}/5")

    X_fold_train = X_dev.iloc[train_idx]
    y_fold_train = y_dev.iloc[train_idx]
    X_fold_holdout = X_dev.iloc[holdout_idx]

    for j, name in enumerate(model_names):
        model = build_pipeline(name, build_models()[name])

        model.fit(X_fold_train, y_fold_train)

        oof_probs[holdout_idx, j] = get_positive_probability(
            model, X_fold_holdout
        )


# =====================================================
# 4. LEARN ENSEMBLE WEIGHTS USING DEVELOPMENT DATA ONLY
# =====================================================

equal_weights = np.ones(len(model_names)) / len(model_names)

f1_scores = []

for j in range(len(model_names)):
    predictions = (oof_probs[:, j] >= 0.5).astype(int)
    f1_scores.append(
        f1_score(y_dev, predictions, pos_label=1, zero_division=0)
    )

f1_scores = np.asarray(f1_scores)
f1_weights = (
    f1_scores / f1_scores.sum()
    if f1_scores.sum() > 0 else equal_weights.copy()
)


def optimize_logloss_weights(probabilities, labels, regularization=0.05):
    n_models = probabilities.shape[1]
    initial_weights = np.ones(n_models) / n_models
    epsilon = 1e-7

    def objective(weights):
        combined = np.clip(
            probabilities @ weights, epsilon, 1 - epsilon
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
        print("Weight optimization failed; using equal weights.")
        return initial_weights

    weights = np.maximum(result.x, 0)
    return weights / weights.sum()


optimized_weights = optimize_logloss_weights(oof_probs, y_dev)

print("\nLearned weights:")
weight_table = pd.DataFrame({
    "Model": model_names,
    "Equal Weight": equal_weights,
    "F1 Weight": f1_weights,
    "Optimized Log-Loss Weight": optimized_weights
})
print(weight_table.round(4).to_string(index=False))


# =====================================================
# 5. FIT SIX MODELS ON ALL DEVELOPMENT SAMPLES
# =====================================================

print("\nFitting final comparison models on development data...")

fitted_models = {}
test_probs = np.zeros((len(y_test), len(model_names)))

for j, name in enumerate(model_names):
    print("Training:", name)

    model = build_pipeline(name, build_models()[name])
    model.fit(X_dev, y_dev)

    fitted_models[name] = model
    test_probs[:, j] = get_positive_probability(model, X_test)


# =====================================================
# 6. COMPARE METHODS ON THE TEST SET
# =====================================================

methods = {
    "AdaBoost": test_probs[:, model_names.index("AdaBoost")],
    "Logistic Regression": test_probs[
        :, model_names.index("Logistic Regression")
    ],
    "Six-Model Equal Ensemble": test_probs @ equal_weights,
    "Six-Model F1-Weighted Ensemble": test_probs @ f1_weights,
    "Six-Model Optimized Log-Loss Ensemble":
        test_probs @ optimized_weights
}


def evaluate(name, probabilities):
    probabilities = np.clip(probabilities, 1e-7, 1 - 1e-7)
    predictions = (probabilities >= 0.5).astype(int)

    cm = confusion_matrix(y_test, predictions, labels=[0, 1])

    tn, fp, fn, tp = cm.ravel()

    specificity = tn / (tn + fp) if (tn + fp) else 0.0

    metrics = {
        "Method": name,
        "Accuracy": accuracy_score(y_test, predictions),
        "Balanced Accuracy": balanced_accuracy_score(
            y_test, predictions
        ),
        "Macro F1": f1_score(
            y_test, predictions, average="macro", zero_division=0
        ),
        "Normal Recall": recall_score(
            y_test, predictions, pos_label=0, zero_division=0
        ),
        "Tumour Recall": recall_score(
            y_test, predictions, pos_label=1, zero_division=0
        ),
        "Normal Specificity": specificity,
        "ROC AUC": roc_auc_score(y_test, probabilities),
        "Log Loss": log_loss(y_test, probabilities, labels=[0, 1])
    }

    print("\n" + "=" * 55)
    print(name)
    print("=" * 55)
    print("Confusion matrix (rows=actual, columns=predicted):")
    print(pd.DataFrame(
        cm,
        index=["Actual Normal", "Actual Tumour"],
        columns=["Predicted Normal", "Predicted Tumour"]
    ).to_string())

    print("\nClassification report:")
    print(classification_report(
        y_test,
        predictions,
        labels=[0, 1],
        target_names=["Normal", "Tumour"],
        zero_division=0
    ))

    return metrics, predictions


all_metrics = []
all_predictions = {}

for name, probabilities in methods.items():
    metrics, predictions = evaluate(name, probabilities)
    all_metrics.append(metrics)
    all_predictions[name] = predictions


# =====================================================
# 7. SAVE RESULTS
# =====================================================

results_df = pd.DataFrame(all_metrics)
results_df.to_csv("final_ensemble_comparison.csv", index=False)

weight_table.to_csv("final_ensemble_weights.csv", index=False)

prediction_table = pd.DataFrame({
    "Sample_ID": X_test.index,
    "Actual_Label": y_test.values
})

for name, probabilities in methods.items():
    prediction_table[name + "_Probability"] = probabilities
    prediction_table[name + "_Prediction"] = all_predictions[name]

prediction_table.to_csv(
    "final_ensemble_test_predictions.csv", index=False
)

print("\n\n========== FINAL COMPARISON SUMMARY ==========")
print(
    results_df.sort_values(
        "Balanced Accuracy", ascending=False
    ).round(4).to_string(index=False)
)

print("\nSaved files:")
print("- final_ensemble_comparison.csv")
print("- final_ensemble_weights.csv")
print("- final_ensemble_test_predictions.csv")

print(
    "\nInterpretation note: this test set was inspected in earlier "
    "experiments. Report these results as a final comparative "
    "evaluation on a previously inspected test set, not as a "
    "completely untouched external validation."
)
