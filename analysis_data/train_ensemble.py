
import warnings
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from sklearn.feature_selection import SelectKBest, f_classif
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.ensemble import RandomForestClassifier, AdaBoostClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.naive_bayes import GaussianNB
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    confusion_matrix,
    classification_report,
)
from xgboost import XGBClassifier

warnings.filterwarnings("ignore")

# --------------------------------------------------
# 1. Load data
# --------------------------------------------------
DATA_DIR = "dataset"

X = pd.read_csv(
    f"{DATA_DIR}/expression_samples.csv", index_col=0
)
y = pd.read_csv(
    f"{DATA_DIR}/sample_labels.csv", index_col=0
).squeeze("columns")

y = y.loc[X.index].astype(int)

# Reproduce the same stratified split as prepare_data.py
from sklearn.model_selection import train_test_split

X_train, X_temp, y_train, y_temp = train_test_split(
    X, y, test_size=0.40, random_state=42, stratify=y
)
X_val, X_test, y_val, y_test = train_test_split(
    X_temp, y_temp, test_size=0.50, random_state=42, stratify=y_temp
)

print("Train:", X_train.shape)
print("Validation:", X_val.shape)
print("Test:", X_test.shape)

# --------------------------------------------------
# 2. Define five classifiers
# Feature selection is fitted ONLY on training data.
# --------------------------------------------------
models = {
    "Decision Tree": DecisionTreeClassifier(
        max_depth=5, class_weight="balanced", random_state=42
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
        n_estimators=100, random_state=42
    ),
    "Gaussian NB": GaussianNB(),
}

def build_pipeline(model):
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("select", SelectKBest(score_func=f_classif, k=500)),
        ("model", model),
    ])

fitted_models = {}
val_probs = {}
test_probs = {}
val_f1 = {}

# --------------------------------------------------
# 3. Train and collect validation/test probabilities
# --------------------------------------------------
for name, classifier in models.items():
    print(f"\nTraining {name}...")

    pipeline = build_pipeline(classifier)
    pipeline.fit(X_train, y_train)

    fitted_models[name] = pipeline
    val_probs[name] = pipeline.predict_proba(X_val)[:, 1]
    test_probs[name] = pipeline.predict_proba(X_test)[:, 1]

    val_pred = (val_probs[name] >= 0.5).astype(int)
    val_f1[name] = f1_score(
        y_val, val_pred, zero_division=0
    )

    print(f"Validation F1: {val_f1[name]:.4f}")

# --------------------------------------------------
# 4. Calculate adaptive weights from validation F1
# --------------------------------------------------
scores = np.array(list(val_f1.values()), dtype=float)

if scores.sum() == 0:
    weights = np.ones(len(scores)) / len(scores)
else:
    weights = scores / scores.sum()

print("\nAdaptive weights:")
for name, weight in zip(models.keys(), weights):
    print(f"{name}: {weight:.4f}")

# --------------------------------------------------
# 5. Compare equal-weight voting and adaptive ensemble
# --------------------------------------------------
equal_probs = np.mean(
    np.column_stack(list(test_probs.values())), axis=1
)

adaptive_probs = np.zeros(len(y_test))
for weight, name in zip(weights, models.keys()):
    adaptive_probs += weight * test_probs[name]

# --------------------------------------------------
# 6. Evaluation on untouched test set
# --------------------------------------------------
def evaluate(name, probabilities):
    predictions = (probabilities >= 0.5).astype(int)

    print("\n" + "=" * 55)
    print(name)
    print("=" * 55)
    print(f"Accuracy:          {accuracy_score(y_test, predictions):.4f}")
    print(f"Balanced accuracy: {balanced_accuracy_score(y_test, predictions):.4f}")
    print(f"Precision:         {precision_score(y_test, predictions, zero_division=0):.4f}")
    print(f"Recall:            {recall_score(y_test, predictions, zero_division=0):.4f}")
    print(f"F1-score:          {f1_score(y_test, predictions, zero_division=0):.4f}")
    print(f"ROC-AUC:           {roc_auc_score(y_test, probabilities):.4f}")

    print("\nClassification report:")
    print(classification_report(
        y_test,
        predictions,
        target_names=["Normal", "Tumour"],
        zero_division=0,
    ))

    return predictions

equal_pred = evaluate("Equal-weight Soft Voting", equal_probs)
adaptive_pred = evaluate("Adaptive Weighted Ensemble", adaptive_probs)

# --------------------------------------------------
# 7. Confusion matrix for adaptive ensemble
# --------------------------------------------------
cm = confusion_matrix(y_test, adaptive_pred, labels=[0, 1])

plt.figure(figsize=(6, 5))
plt.imshow(cm)
plt.title("Adaptive Ensemble - Confusion Matrix")
plt.xlabel("Predicted class")
plt.ylabel("Actual class")
plt.xticks([0, 1], ["Normal", "Tumour"])
plt.yticks([0, 1], ["Normal", "Tumour"])

for (i, j), value in np.ndenumerate(cm):
    plt.text(j, i, str(value), ha="center", va="center")

plt.tight_layout()
plt.savefig("adaptive_confusion_matrix.png", dpi=150)
plt.show()

# --------------------------------------------------
# 8. Save comparison and model weights
# --------------------------------------------------
results = pd.DataFrame({
    "Sample_ID": X_test.index,
    "Actual_Label": y_test.values,
    "Equal_Voting_Probability": equal_probs,
    "Adaptive_Probability": adaptive_probs,
})

results.to_csv("ensemble_test_predictions.csv", index=False)

pd.DataFrame({
    "Model": list(models.keys()),
    "Validation_F1": list(val_f1.values()),
    "Adaptive_Weight": weights,
}).to_csv("adaptive_model_weights.csv", index=False)

print("\nSaved:")
print("- adaptive_confusion_matrix.png")
print("- ensemble_test_predictions.csv")
print("- adaptive_model_weights.csv")
