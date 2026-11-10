
import joblib
import pandas as pd
from pathlib import Path

artifact_path = Path("artifacts/lunginsight_ensemble.joblib")

# Load the saved model artifact
artifact = joblib.load(artifact_path)

models = artifact["models"]
weights = artifact["optimized_weights"]
features = artifact["feature_names"]

print("Artifact loaded successfully.")
print("Number of models:", len(models))
print("Number of expected genes:", len(features))
print("\nOptimized ensemble weights:")

for name, weight in weights.items():
    print(f"{name}: {weight:.4f}")

# Load a few existing samples to test inference
X = pd.read_csv("dataset/expression_samples.csv", index_col=0)
X_sample = X.loc[:, features].head(5)

# Generate each model's tumour probability
probabilities = []

for name in artifact["model_names"]:
    model = models[name]
    p = model.predict_proba(X_sample)
    positive_index = list(model.classes_).index(1)
    probabilities.append(p[:, positive_index])

# Combine model probabilities using learned weights
probabilities = pd.DataFrame(
    probabilities,
    index=artifact["model_names"],
    columns=X_sample.index
)

weight_series = pd.Series(weights)
ensemble_probabilities = (
    probabilities.T @ weight_series
)

results = pd.DataFrame({
    "Sample_ID": X_sample.index,
    "Tumour_Probability": ensemble_probabilities.values,
    "Predicted_Label": (
        ensemble_probabilities.values >= 0.5
    ).astype(int)
})

results["Prediction"] = results["Predicted_Label"].map({
    0: "Normal",
    1: "Tumour"
})

print("\nTest predictions from saved pipelines:")
print(results.to_string(index=False))
