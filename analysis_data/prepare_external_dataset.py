
import pandas as pd
import joblib
from pathlib import Path

external_path = Path(
    "external_dataset/GSE40419_LC-87_RPKM_expression.txt.gz"
)
model_path = Path("artifacts/lunginsight_ensemble.joblib")

df = pd.read_csv(
    external_path,
    sep="\t",
    compression="gzip",
    low_memory=False
)

artifact = joblib.load(model_path)

# Identify sample columns and their labels
sample_cols = df.columns[6:].tolist()

tumour_cols = [
    c for c in sample_cols
    if (c.startswith("LC_C") or c.startswith("LC_S"))
    and not c.endswith("_nor")
]
normal_cols = [c for c in sample_cols if c.endswith("_nor")]

print("Tumour samples:", len(tumour_cols))
print("Normal samples:", len(normal_cols))

# Keep gene symbols and expression values only
expression = df[["gene"] + sample_cols].copy()
expression["gene"] = expression["gene"].astype(str).str.strip()

# Convert expression measurements to numeric values
expression[sample_cols] = expression[sample_cols].apply(
    pd.to_numeric, errors="coerce"
)

# Report invalid measurements before proceeding
print(
    "Missing expression measurements:",
    int(expression[sample_cols].isna().sum().sum())
)

# Consolidate duplicate symbols using the mean RPKM value
gene_expression = expression.groupby("gene")[sample_cols].mean()

artifact_genes = list(artifact["feature_names"])
overlap = set(gene_expression.index) & set(artifact_genes)

print("Unique external genes:", len(gene_expression))
print("Model genes:", len(artifact_genes))
print("Overlapping genes:", len(overlap))
print("Missing model genes:", len(set(artifact_genes) - overlap))

# Save the consolidated matrix for inspection, not prediction yet
gene_expression.to_csv(
    "external_dataset/GSE40419_gene_expression_by_symbol.csv"
)

print("\nSaved consolidated gene-expression matrix.")
print("No model predictions have been run.")
