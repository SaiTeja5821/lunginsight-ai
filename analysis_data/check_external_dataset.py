
import pandas as pd
import joblib

path = "external_dataset/GSE40419_LC-87_RPKM_expression.txt.gz"
model_path = "artifacts/lunginsight_ensemble.joblib"

df = pd.read_csv(path, sep="\t", compression="gzip", low_memory=False)
artifact = joblib.load(model_path)

# Six metadata columns precede the sample expression columns
sample_cols = df.columns[6:].tolist()


tumour_cols = [
    col for col in sample_cols
    if (col.startswith("LC_C") or col.startswith("LC_S"))
    and not col.endswith("_nor")
]

normal_cols = [
    col for col in sample_cols
    if col.endswith("_nor")
]

other_cols = [
    col for col in sample_cols
    if col not in tumour_cols and col not in normal_cols
]

print("Total samples:", len(sample_cols))
print("Tumour samples:", len(tumour_cols))
print("Normal samples:", len(normal_cols))
print("Other samples:", len(other_cols))

print("\nAll unclassified sample columns:")
print(other_cols)

print("\nSample-name prefixes:")
print(pd.Series(sample_cols).str.extract(r"^([^0-9_]+)")[0].value_counts())

print("\nFirst 30 sample names:")
print(sample_cols[:30])

model_genes = set(artifact["feature_names"])
external_genes = set(df["gene"].dropna().astype(str))

print("Total samples:", len(sample_cols))
print("Tumour samples:", len(tumour_cols))
print("Normal samples:", len(normal_cols))
print("Other sample columns:", len(sample_cols) - len(tumour_cols) - len(normal_cols))

print("\nUnique external gene symbols:", len(external_genes))
print("Unique model gene symbols:", len(model_genes))
print("Overlapping gene symbols:", len(external_genes & model_genes))
print("Model genes missing externally:", len(model_genes - external_genes))

print("\nExample tumour samples:", tumour_cols[:5])
print("Example normal samples:", normal_cols[:5])

# Inspect repeated gene symbols and whether their measurements differ
duplicate_rows = df[df["gene"].duplicated(keep=False)]
print("\nRows with duplicated gene symbols:", len(duplicate_rows))
print("Example duplicate symbols:")
print(
    duplicate_rows["gene"]
    .value_counts()
    .head(10)
    .to_string()
)
