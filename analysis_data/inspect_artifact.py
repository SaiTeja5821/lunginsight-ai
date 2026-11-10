import joblib
from pathlib import Path

path = Path("artifacts/lunginsight_ensemble.joblib")
artifact = joblib.load(path)

print("Artifact keys:", list(artifact.keys()))
print("Number of features:", len(artifact["feature_names"]))

for name, model in artifact["models"].items():
    print(f"\nModel: {name}")
    print("Type:", type(model).__name__)

    if hasattr(model, "named_steps"):
        print("Pipeline steps:", list(model.named_steps.keys()))
    elif hasattr(model, "steps"):
        print("Pipeline steps:", [step[0] for step in model.steps])
    else:
        print("No pipeline steps exposed.")

print("\nSaved weights:", artifact["optimized_weights"])