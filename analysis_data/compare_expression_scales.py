
import pandas as pd
import numpy as np
import joblib

tcga_path = "dataset/expression_samples.csv"
external_path = (
    "external_dataset/GSE40419_gene_expression_by_symbol.csv"
)
model_path = "artifacts/lunginsight_ensemble.joblib"

# Load training and external expression data
tcga = pd.read_csv(tcga_path, index_col=0)
external = pd.read_csv(external_path, index_col=0)
artifact = joblib.load(model_path)

genes = list(artifact["feature_names"])

# Match the model's gene list where available
tcga_genes = [g for g in genes if g in tcga.columns]
external_genes = [g for g in genes if g in external.index]

print("TCGA shape:", tcga.shape)
print("External shape (genes x samples):", external.shape)
print("Model genes found in TCGA:", len(tcga_genes))
print("Model genes found externally:", len(external_genes))

def summarize(name, values):
    values = np.asarray(values, dtype=float).ravel()
    values = values[np.isfinite(values)]

    print(f"\n{name}")
    print("Count:", len(values))
    print("Min:", round(float(np.min(values)), 4))
    print("25%:", round(float(np.percentile(values, 25)), 4))
    print("Median:", round(float(np.median(values)), 4))
    print("75%:", round(float(np.percentile(values, 75)), 4))
    print("95%:", round(float(np.percentile(values, 95)), 4))
    print("Max:", round(float(np.max(values)), 4))
    print("Zero fraction:", round(float(np.mean(values == 0)), 4))

summarize(
    "TCGA matched gene values",
    tcga[tcga_genes].to_numpy()
)

summarize(
    "External matched gene values",
    external.loc[external_genes].to_numpy()
)

print("\nPreprocessing steps in each saved model:")
for name, pipeline in zip(
    artifact["model_names"], artifact["models"]
):
    print(f"\n{name}")
    print(pipeline)

print("\nDiagnostic complete. No predictions were run.")
