
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from sklearn.model_selection import train_test_split, StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.feature_selection import SelectKBest, f_classif
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.inspection import permutation_importance
from sklearn.metrics import balanced_accuracy_score


# =====================================================
# 1. LOAD AND VERIFY DATA
# =====================================================

print("Loading dataset...", flush=True)

X = pd.read_csv(
    "dataset/expression_samples.csv",
    index_col=0
)

y = pd.read_csv(
    "dataset/sample_labels.csv",
    index_col=0
).squeeze("columns")

# Ensure labels match expression rows.
y = y.loc[X.index].astype(int)

# Reproduce original train/validation/test split.
X_train, X_temp, y_train, y_temp = train_test_split(
    X, y,
    test_size=0.40,
    random_state=42,
    stratify=y
)

X_val, X_test, y_val, y_test = train_test_split(
    X_temp, y_temp,
    test_size=0.50,
    random_state=42,
    stratify=y_temp
)

# Development data only; final test data excluded.
X_dev = pd.concat([X_train, X_val])
y_dev = pd.concat([y_train, y_val])

print("Development samples:", len(X_dev), flush=True)
print("Total genes:", X_dev.shape[1], flush=True)
print("Final test set excluded.", flush=True)


# =====================================================
# 2. DEFINE LOGISTIC REGRESSION PIPELINE
# =====================================================

def build_model():
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("select", SelectKBest(score_func=f_classif, k=500)),
        ("scale", StandardScaler()),
        ("model", LogisticRegression(
            class_weight="balanced",
            max_iter=2000,
            random_state=42
        ))
    ])


# =====================================================
# 3. CROSS-VALIDATION AND SELECTED-GENE IMPORTANCE
# =====================================================

cv = StratifiedKFold(
    n_splits=5,
    shuffle=True,
    random_state=42
)

importance_records = []
fold_scores = []

for fold, (train_idx, val_idx) in enumerate(
    cv.split(X_dev, y_dev), start=1
):
    print(f"\n========== FOLD {fold}/5 ==========", flush=True)

    X_fold_train = X_dev.iloc[train_idx]
    y_fold_train = y_dev.iloc[train_idx]

    X_fold_val = X_dev.iloc[val_idx]
    y_fold_val = y_dev.iloc[val_idx]

    model = build_model()

    print("Training Logistic Regression...", flush=True)
    model.fit(X_fold_train, y_fold_train)

    predictions = model.predict(X_fold_val)

    score = balanced_accuracy_score(
        y_fold_val, predictions
    )

    fold_scores.append({
        "Fold": fold,
        "Balanced_Accuracy": score
    })

    print(
        f"Fold balanced accuracy: {score:.4f}",
        flush=True
    )

    # Get the 500 genes selected using training-fold data only.
    selected_mask = (
        model.named_steps["select"].get_support()
    )

    selected_genes = X_fold_train.columns[selected_mask]

    print(
        f"Calculating importance for {len(selected_genes)} "
        "selected genes...",
        flush=True
    )

    # Permute only selected genes on the validation fold.
    # One repeat and half the samples reduce computation.
    result = permutation_importance(
        model,
        X_fold_val,
        y_fold_val,
        scoring="balanced_accuracy",
        n_repeats=1,
        random_state=100 + fold,
        n_jobs=1,
        max_samples=0.5
    )

    # Map importance scores back to original gene names.
    for gene, mean_imp, std_imp, is_selected in zip(
        X_fold_val.columns,
        result.importances_mean,
        result.importances_std,
        selected_mask
    ):
        if is_selected:
            importance_records.append({
                "Fold": fold,
                "Gene": gene,
                "Importance": mean_imp,
                "Importance_SD": std_imp
            })

    print("Fold completed.", flush=True)


# =====================================================
# 4. AGGREGATE RESULTS ACROSS FOLDS
# =====================================================

print("\nAggregating gene importance...", flush=True)

importance_df = pd.DataFrame(importance_records)

summary = (
    importance_df
    .groupby("Gene")
    .agg(
        Mean_Importance=("Importance", "mean"),
        SD_Importance=("Importance", "std"),
        Folds_Selected=("Fold", "nunique"),
        Folds_Positive=("Importance",
                        lambda x: int((x > 0).sum()))
    )
    .reset_index()
)

summary["Selection_Frequency"] = (
    summary["Folds_Selected"] / 5
)

summary["Positive_Importance_Frequency"] = (
    summary["Folds_Positive"] / 5
)

summary = summary.sort_values(
    ["Mean_Importance", "Selection_Frequency"],
    ascending=False
)

summary.to_csv(
    "biomarker_gene_importance.csv",
    index=False
)

pd.DataFrame(fold_scores).to_csv(
    "biomarker_fold_scores.csv",
    index=False
)


# =====================================================
# 5. SAVE AND DISPLAY TOP 20 GENES
# =====================================================

top20 = summary.head(20).copy()

top20.to_csv(
    "top20_candidate_genes.csv",
    index=False
)

print("\n========== TOP 20 CANDIDATE GENES ==========", flush=True)
print(top20.to_string(index=False))

scores_df = pd.DataFrame(fold_scores)

print(
    "\nMean development CV balanced accuracy:",
    round(scores_df["Balanced_Accuracy"].mean(), 4)
)

print(
    "Standard deviation:",
    round(scores_df["Balanced_Accuracy"].std(), 4)
)


# =====================================================
# 6. PLOT TOP 20 GENES
# =====================================================

plot_data = top20.sort_values("Mean_Importance")

plt.figure(figsize=(10, 8))

plt.barh(
    plot_data["Gene"],
    plot_data["Mean_Importance"],
    xerr=plot_data["SD_Importance"].fillna(0)
)

plt.xlabel("Mean decrease in balanced accuracy")
plt.ylabel("Gene")
plt.title("Top Candidate Genes - Development Cross-Validation")

plt.tight_layout()
plt.savefig(
    "top20_biomarker_importance.png",
    dpi=200
)

plt.close()

print("\nSaved files:", flush=True)
print("- biomarker_gene_importance.csv")
print("- biomarker_fold_scores.csv")
print("- top20_candidate_genes.csv")
print("- top20_biomarker_importance.png")

print(
    "\nNote: permutation importance measures model dependence, "
    "not proof of biological causation or clinical validity."
)
