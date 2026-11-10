
import warnings
import numpy as np
import pandas as pd

from sklearn.model_selection import train_test_split, StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.feature_selection import SelectKBest, f_classif
from sklearn.preprocessing import StandardScaler

from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier, AdaBoostClassifier
from sklearn.naive_bayes import GaussianNB
from sklearn.linear_model import LogisticRegression
from xgboost import XGBClassifier

from sklearn.metrics import accuracy_score

warnings.filterwarnings("ignore")

# 1. Load the dataset
DATA_DIR = "dataset"

X = pd.read_csv(
    f"{DATA_DIR}/expression_samples.csv", index_col=0
)
y = pd.read_csv(
    f"{DATA_DIR}/sample_labels.csv", index_col=0
).squeeze("columns")

y = y.loc[X.index].astype(int)

# Reproduce the original split and preserve the final test set
X_train, X_temp, y_train, y_temp = train_test_split(
    X, y, test_size=0.40, random_state=42, stratify=y
)

X_val, X_test, y_val, y_test = train_test_split(
    X_temp, y_temp, test_size=0.50,
    random_state=42, stratify=y_temp
)

# Development data only
X_dev = pd.concat([X_train, X_val])
y_dev = pd.concat([y_train, y_val])

models = {
    "Decision Tree": (
        DecisionTreeClassifier(
            max_depth=5, class_weight="balanced",
            random_state=42
        ), False
    ),
    "Random Forest": (
        RandomForestClassifier(
            n_estimators=200, class_weight="balanced",
            random_state=42, n_jobs=-1
        ), False
    ),
    "XGBoost": (
        XGBClassifier(
            n_estimators=100, max_depth=3,
            learning_rate=0.05, eval_metric="logloss",
            random_state=42, n_jobs=-1
        ), False
    ),
    "AdaBoost": (
        AdaBoostClassifier(
            n_estimators=100, random_state=42
        ), False
    ),
    "Gaussian NB": (GaussianNB(), False),
    "Logistic Regression": (
        LogisticRegression(
            class_weight="balanced",
            max_iter=2000, random_state=42
        ), True
    ),
}

def build_pipeline(model, scale):
    steps = [
        ("imputer", SimpleImputer(strategy="median")),
        ("select", SelectKBest(score_func=f_classif, k=500)),
    ]

    if scale:
        steps.append(("scaler", StandardScaler()))

    steps.append(("model", model))
    return Pipeline(steps)

# 2. Obtain out-of-fold predictions on development data
cv = StratifiedKFold(
    n_splits=5, shuffle=True, random_state=42
)

oof_predictions = pd.DataFrame(
    index=X_dev.index, columns=list(models), dtype=float
)

for fold, (train_idx, val_idx) in enumerate(
    cv.split(X_dev, y_dev), start=1
):
    print(f"\nFold {fold}/5")

    X_fold_train = X_dev.iloc[train_idx]
    y_fold_train = y_dev.iloc[train_idx]
    X_fold_val = X_dev.iloc[val_idx]

    for name, (model, scale) in models.items():
        pipeline = build_pipeline(model, scale)
        pipeline.fit(X_fold_train, y_fold_train)

        oof_predictions.loc[X_fold_val.index, name] = (
            pipeline.predict(X_fold_val)
        )

# Convert to integer class predictions
oof_predictions = oof_predictions.astype(int)

# 3. Calculate each model's out-of-fold accuracy
print("\nINDIVIDUAL MODEL ACCURACY")

for name in models:
    accuracy = accuracy_score(
        y_dev, oof_predictions[name]
    )
    print(f"{name}: {accuracy:.4f}")

# 4. Compare prediction disagreement between models
# Higher disagreement means models predict different labels
disagreement = pd.DataFrame(
    index=list(models), columns=list(models), dtype=float
)

for model_a in models:
    for model_b in models:
        disagreement.loc[model_a, model_b] = np.mean(
            oof_predictions[model_a].values
            != oof_predictions[model_b].values
        )

print("\nPAIRWISE PREDICTION DISAGREEMENT")
print(disagreement.round(4).to_string())

# 5. Compare five-model and six-model majority voting
five_names = list(models)[:5]
six_names = list(models)

five_vote = (
    oof_predictions[five_names].mean(axis=1) >= 0.5
).astype(int)

six_vote = (
    oof_predictions[six_names].mean(axis=1) >= 0.5
).astype(int)

print("\nMAJORITY-VOTE ACCURACY")
print(
    "Five models:",
    round(accuracy_score(y_dev, five_vote), 4)
)
print(
    "Six models:",
    round(accuracy_score(y_dev, six_vote), 4)
)

# 6. Does Logistic Regression fix mistakes made by the
# original five models' majority vote?
original_wrong = five_vote.values != y_dev.values
logistic_correct = (
    oof_predictions["Logistic Regression"].values
    == y_dev.values
)

print("\nLOGISTIC REGRESSION COMPLEMENTARITY")
print(
    "Samples where five-model vote is wrong:",
    int(original_wrong.sum())
)
print(
    "Of those, Logistic Regression predicts correctly:",
    int((original_wrong & logistic_correct).sum())
)

# Save the analysis
oof_predictions.to_csv(
    "model_diversity_oof_predictions.csv"
)
disagreement.to_csv(
    "model_diversity_disagreement.csv"
)

print("\nSaved:")
print("- model_diversity_oof_predictions.csv")
print("- model_diversity_disagreement.csv")
print("\nThe final test set was not evaluated.")
