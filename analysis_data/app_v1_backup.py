
import streamlit as st
import pandas as pd
import numpy as np
import joblib
from pathlib import Path

st.set_page_config(
    page_title="LungInsight AI",
    page_icon="🫁",
    layout="wide"
)

MODEL_PATH = Path("artifacts/lunginsight_ensemble.joblib")

st.title("🫁 LungInsight AI")
st.subheader("Gene Expression Analysis & Research Support")
st.write(
    "Upload a gene-expression CSV to generate research predictions "
    "using the saved ensemble model."
)

st.warning(
    "Research prototype only. Predictions are not medical diagnoses "
    "and have not been validated for arbitrary external datasets."
)

# Load the saved model artifact
@st.cache_resource
def load_artifact():
    return joblib.load(MODEL_PATH)

if not MODEL_PATH.exists():
    st.error(f"Model artifact not found: {MODEL_PATH}")
    st.stop()

try:
    artifact = load_artifact()
except Exception as exc:
    st.error(f"Could not load the saved model: {exc}")
    st.stop()

expected_features = artifact["feature_names"]
model_names = artifact["model_names"]
models = artifact["models"]
weights = artifact["optimized_weights"]

st.success("Saved ensemble loaded successfully.")

st.header("1. Upload gene-expression data")

uploaded_file = st.file_uploader(
    "Choose a CSV file",
    type=["csv"],
    help=(
        "Use one row per sample and one column per gene. "
        "The file must contain the gene features used by the trained model."
    )
)

if uploaded_file is not None:
    try:
        uploaded_df = pd.read_csv(uploaded_file)
    except Exception as exc:
        st.error(f"Could not read the CSV file: {exc}")
        st.stop()

    if uploaded_df.empty:
        st.error("The uploaded CSV is empty.")
        st.stop()

    st.write("### Data preview")
    st.dataframe(uploaded_df.head(10), use_container_width=True)

    st.write(
        f"Rows: **{uploaded_df.shape[0]}** | "
        f"Columns: **{uploaded_df.shape[1]}**"
    )

    st.header("2. Validate the uploaded data")

    # Sample identifiers are not model features.
    id_candidates = [
        "sample_id", "sampleid", "sample", "id",
        "sample_name", "patient_id"
    ]

    id_column = next(
        (
            col for col in uploaded_df.columns
            if str(col).strip().lower() in id_candidates
        ),
        None
    )

    if id_column is not None:
        sample_ids = uploaded_df[id_column].astype(str)
        feature_df = uploaded_df.drop(columns=[id_column]).copy()
    else:
        sample_ids = pd.Series(
            [f"Sample_{i + 1}" for i in range(len(uploaded_df))]
        )
        feature_df = uploaded_df.copy()

    # Check for duplicate column names.
    if not feature_df.columns.is_unique:
        st.error(
            "Duplicate column names were found. Please make every "
            "gene column name unique."
        )
        st.stop()

    # Ensure all required genes are present.
    missing_features = [
        gene for gene in expected_features
        if gene not in feature_df.columns
    ]

    if missing_features:
        st.error(
            f"Missing {len(missing_features)} required gene features. "
            "The model cannot safely predict with this file."
        )
        st.write("Examples of missing gene names:")
        st.code(", ".join(map(str, missing_features[:20])))
        st.info(
            "Download or prepare a dataset using the same gene identifiers "
            "as the model's training data."
        )
        st.stop()

    # Use exactly the expected feature names and order.
    X_new = feature_df.loc[:, expected_features].copy()

    # Convert gene values to numeric; reject non-numeric entries.
    for col in X_new.columns:
        X_new[col] = pd.to_numeric(X_new[col], errors="coerce")

    # Reject values that became missing because they were non-numeric.
    original_values = feature_df.loc[:, expected_features]
    invalid_mask = (
        X_new.isna()
        & original_values.notna()
        & original_values.astype(str).apply(
            lambda col: col.str.strip().ne("")
        )
    )

    if invalid_mask.any().any():
        st.error(
            "Some gene values are non-numeric. Correct these values "
            "before uploading the file."
        )
        st.stop()

    # Infinite values are not valid expression measurements.
    if np.isinf(X_new.to_numpy(dtype=float)).any():
        st.error("Infinite values were found. Please correct the CSV.")
        st.stop()

    if X_new.isna().all(axis=1).any():
        st.error(
            "At least one sample has no usable gene values. "
            "Remove or correct that sample."
        )
        st.stop()

    st.success(
        f"Validation passed: all {len(expected_features)} required genes "
        "are present and ordered correctly."
    )

    if X_new.isna().any().any():
        st.info(
            "Some values are missing. The trained pipeline's median "
            "imputer will handle missing values."
        )

    st.header("3. Generate predictions")

    if st.button("Predict samples", type="primary"):
        with st.spinner("Generating ensemble predictions..."):
            try:
                # Calculate tumour probabilities from all saved pipelines.
                model_probabilities = {}

                for name in model_names:
                    model = models[name]
                    p = model.predict_proba(X_new)
                    positive_index = list(model.classes_).index(1)
                    model_probabilities[name] = p[:, positive_index]

                probability_matrix = np.column_stack(
                    [model_probabilities[name] for name in model_names]
                )

                weight_vector = np.array(
                    [weights[name] for name in model_names],
                    dtype=float
                )

                if not np.isclose(weight_vector.sum(), 1.0):
                    st.error("Saved ensemble weights are invalid.")
                    st.stop()

                ensemble_probabilities = probability_matrix @ weight_vector
                predicted_labels = (
                    ensemble_probabilities >= 0.5
                ).astype(int)

                results = pd.DataFrame({
                    "Sample_ID": sample_ids.to_numpy(),
                    "Tumour_Probability": ensemble_probabilities,
                    "Predicted_Label": predicted_labels,
                    "Prediction": [
                        "Tumour" if label == 1 else "Normal"
                        for label in predicted_labels
                    ]
                })

                st.session_state["lunginsight_results"] = results

            except Exception as exc:
                st.error(f"Prediction failed: {exc}")
                st.stop()

    results = st.session_state.get("lunginsight_results")

    if results is not None:
        st.header("4. Prediction results")

        tumour_count = int((results["Predicted_Label"] == 1).sum())
        normal_count = int((results["Predicted_Label"] == 0).sum())

        col1, col2, col3 = st.columns(3)
        col1.metric("Samples analysed", len(results))
        col2.metric("Predicted tumour", tumour_count)
        col3.metric("Predicted normal", normal_count)

        display_results = results.copy()
        display_results["Tumour_Probability"] = (
            display_results["Tumour_Probability"] * 100
        ).round(2)

        st.dataframe(display_results, use_container_width=True)

        csv_bytes = results.to_csv(index=False).encode("utf-8")

        st.download_button(
            "Download predictions as CSV",
            data=csv_bytes,
            file_name="lunginsight_predictions.csv",
            mime="text/csv"
        )

        st.caption(
            "Tumour probability is the ensemble model's output, not a "
            "calibrated clinical risk estimate. Predictions do not "
            "establish diagnosis or model accuracy on this dataset."
        )
