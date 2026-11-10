
import streamlit as st
import pandas as pd
import numpy as np
import joblib
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from io import BytesIO
from pathlib import Path

st.set_page_config(
    page_title="LungInsight AI",
    page_icon="🫁",
    layout="wide"
)


def build_pdf_report(title, results_df, probability_columns, label_column, disclaimer):
    """Create a compact PDF summary using matplotlib (already used by this app)."""
    buffer = BytesIO()
    with PdfPages(buffer) as pdf:
        fig = plt.figure(figsize=(11.7, 8.3))
        fig.patch.set_facecolor("#0B1220")
        fig.text(0.07, 0.91, title, fontsize=22, color="#67E8F9", weight="bold")
        fig.text(0.07, 0.86, "LungInsight AI | Research sample analysis", fontsize=11, color="#E2E8F0")
        fig.text(0.07, 0.80, f"Samples analysed: {len(results_df)}", fontsize=13, color="#FFFFFF")
        counts = results_df[label_column].astype(str).value_counts().to_dict() if label_column in results_df else {}
        y = 0.75
        for label, count in counts.items():
            fig.text(0.09, y, f"• {label}: {count}", fontsize=11, color="#CBD5E1")
            y -= 0.035
        fig.text(0.07, max(0.45, y - 0.015), "Preview of results", fontsize=13, color="#67E8F9", weight="bold")
        preview = results_df.head(12).copy()
        for col in probability_columns:
            if col in preview:
                preview[col] = (pd.to_numeric(preview[col], errors="coerce") * 100).round(2).map(lambda x: f"{x:.2f}%" if pd.notna(x) else "")
        ax = fig.add_axes([0.06, 0.20, 0.88, 0.30])
        ax.axis("off")
        table = ax.table(cellText=preview.astype(str).values, colLabels=preview.columns.tolist(), loc="center", cellLoc="left")
        table.auto_set_font_size(False)
        table.set_fontsize(7)
        table.scale(1, 1.45)
        for (r, c), cell in table.get_celld().items():
            cell.set_edgecolor("#334155")
            cell.set_facecolor("#172033" if r else "#164E63")
            cell.get_text().set_color("#F8FAFC")
        fig.text(0.07, 0.10, disclaimer, fontsize=8.5, color="#CBD5E1", wrap=True)
        fig.text(0.07, 0.055, "This report summarizes model outputs for research use only; it is not a medical diagnosis.", fontsize=8, color="#94A3B8")
        pdf.savefig(fig, facecolor=fig.get_facecolor(), bbox_inches="tight")
        plt.close(fig)
    buffer.seek(0)
    return buffer.getvalue()

MODEL_PATH = Path("artifacts/lunginsight_ensemble.joblib")

st.markdown("""
<style>
:root { color-scheme: dark; }
.stApp { background: radial-gradient(ellipse at 12% 0%, #123047 0%, #0B1220 38%, #070B14 100%); color: #E5EDF7; }
[data-testid="stHeader"] { background: rgba(7, 11, 20, 0.75); }
[data-testid="stSidebar"] { background: linear-gradient(180deg, #0D1728 0%, #080E19 100%); border-right: 1px solid #1E3449; }
.block-container { padding-top: 1.8rem; padding-bottom: 5rem; max-width: 1500px; }
h1, h2, h3 { color: #E6F7FF !important; letter-spacing: -0.02em; }
[data-testid="stMetric"] { background: linear-gradient(135deg, rgba(18, 39, 58, .95), rgba(12, 24, 40, .95)); border: 1px solid #25445B; padding: 16px 18px; border-radius: 15px; }
[data-testid="stMetricLabel"] { color: #9BB6C9 !important; }
[data-testid="stMetricValue"] { color: #67E8F9 !important; }
[data-testid="stFileUploader"] section { background: rgba(14, 29, 46, .72); border: 1px dashed #2E7187; border-radius: 14px; }
[data-testid="stDataFrame"] { border: 1px solid #20394E; border-radius: 12px; overflow: hidden; }
.stButton > button, .stDownloadButton > button { background: linear-gradient(90deg, #0E7490, #0F766E); color: white; border: 1px solid #2DD4BF; border-radius: 10px; font-weight: 600; }
.stButton > button:hover, .stDownloadButton > button:hover { border-color: #A5F3FC; color: white; }
[data-testid="stExpander"] { background: rgba(13, 27, 43, .76); border: 1px solid #20394E; border-radius: 12px; }
hr { border-color: #1D3447; }
.lung-hero { padding: 1.5rem 1.7rem; border: 1px solid #24516A; border-radius: 20px; background: linear-gradient(115deg, rgba(15, 50, 72, .92), rgba(11, 21, 37, .92)); margin-bottom: 1.2rem; }
.lung-kicker { color: #67E8F9; text-transform: uppercase; letter-spacing: .16em; font-size: .75rem; font-weight: 700; }
.lung-subtitle { color: #B6C9D8; font-size: 1rem; margin-top: .5rem; }
.lung-pill { display: inline-block; padding: .32rem .65rem; border: 1px solid #286078; border-radius: 99px; color: #A5F3FC; font-size: .78rem; margin: .8rem .35rem 0 0; }
</style>
<div class="lung-hero">
  <div class="lung-kicker">Research workspace · RNA-seq</div>
  <h1 style="margin:.35rem 0 0 0; color:#F0FAFF;">🫁 LungInsight AI</h1>
  <div class="lung-subtitle">Gene-expression classification with adaptive ensembles and sample-level explainability.</div>
  <span class="lung-pill">LUAD vs Normal</span><span class="lung-pill">LUAD vs LUSC</span><span class="lung-pill">SHAP + LIME</span>
</div>
""", unsafe_allow_html=True)

st.info("Start by uploading a compatible RNA-seq expression CSV. Use one row per sample and gene names as columns. This research prototype does not diagnose people or estimate personal clinical risk.")
with st.sidebar:
    st.markdown("### 🫁 LungInsight AI")
    st.caption("RNA-seq research workspace")
    st.markdown("---")
    st.markdown("**Workflow**")
    st.markdown("1. Upload expression data")
    st.markdown("2. Review feature compatibility")
    st.markdown("3. Run either classifier")
    st.markdown("4. Explore SHAP / LIME")
    st.markdown("5. Export CSV or PDF")
    st.markdown("---")
    st.caption("Research prototype · Not for clinical diagnosis")



# ---------------------------------------------------------
# 1. Load the saved model
# ---------------------------------------------------------

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

expected_features = list(artifact["feature_names"])
model_names = artifact["model_names"]
models = artifact["models"]
weights = artifact["optimized_weights"]

st.success("Saved ensemble loaded successfully.")

# ---------------------------------------------------------
# 2. Upload data
# ---------------------------------------------------------

st.header("1. Upload gene-expression data")

uploaded_file = st.file_uploader(
    "Choose a CSV file",
    type=["csv"],
    help=(
        "Use one row per sample and one column per gene. "
        "All gene features required by the trained model must be present."
    )
)

if uploaded_file is not None:

    # Invalidate old results if the uploaded file changes.
    upload_signature = (uploaded_file.name, uploaded_file.size)

    if st.session_state.get("upload_signature") != upload_signature:
        st.session_state.pop("lunginsight_results", None)
        st.session_state["upload_signature"] = upload_signature

    try:
        uploaded_df = pd.read_csv(uploaded_file)
    except Exception as exc:
        st.error(f"Could not read the CSV file: {exc}")
        st.stop()

    if uploaded_df.empty:
        st.error("The uploaded CSV is empty.")
        st.stop()

    st.subheader("Data preview")
    st.dataframe(uploaded_df.head(10), use_container_width=True)

    st.write(
        f"Rows: **{uploaded_df.shape[0]}** | "
        f"Columns: **{uploaded_df.shape[1]}**"
    )

    # -----------------------------------------------------
    # 3. Validate input
    # -----------------------------------------------------

    st.header("2. Validate uploaded data")

    id_candidates = {
        "sample_id", "sampleid", "sample", "id",
        "sample_name", "patient_id"
    }

    id_column = next(
        (
            col for col in uploaded_df.columns
            if str(col).strip().lower() in id_candidates
        ),
        None
    )

    if id_column is not None:
        sample_ids = uploaded_df[id_column].astype(str).reset_index(drop=True)
        feature_df = uploaded_df.drop(columns=[id_column]).copy()
    else:
        sample_ids = pd.Series(
            [f"Sample_{i + 1}" for i in range(len(uploaded_df))]
        )
        feature_df = uploaded_df.copy()

    if not feature_df.columns.is_unique:
        st.error(
            "Duplicate column names were found. Make every gene "
            "column name unique."
        )
        st.stop()

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
            "Use a dataset with the same gene identifiers as the "
            "model's training data."
        )
        st.stop()

    # Reorder features to match training order.
    X_new = feature_df.loc[:, expected_features].copy()

    original_values = X_new.copy()

    for col in X_new.columns:
        X_new[col] = pd.to_numeric(X_new[col], errors="coerce")

    # Reject strings that cannot be converted to numeric values.
    invalid_mask = (
        X_new.isna()
        & original_values.notna()
        & original_values.astype(str).apply(
            lambda col: col.str.strip().ne("")
        )
    )

    if invalid_mask.any().any():
        st.error(
            "Non-numeric gene values were found. Correct these "
            "values before uploading."
        )
        st.stop()

    if np.isinf(X_new.to_numpy(dtype=float)).any():
        st.error("Infinite values were found. Correct the CSV.")
        st.stop()

    if X_new.isna().all(axis=1).any():
        st.error(
            "At least one sample has no usable gene values. "
            "Remove or correct that sample."
        )
        st.stop()

    st.success(
        f"Validation passed: all {len(expected_features)} required "
        "gene features are present."
    )

    if X_new.isna().any().any():
        st.info(
            "Missing values were found. The saved pipelines' "
            "imputers will handle them."
        )

    # -----------------------------------------------------
    # 4. Generate predictions
    # -----------------------------------------------------

    st.header("3. Generate predictions")

    if st.button("Predict samples", type="primary"):
        try:
            with st.spinner("Generating ensemble predictions..."):

                model_probabilities = {}

                for name in model_names:
                    model = models[name]
                    probabilities = model.predict_proba(X_new)

                    positive_index = list(model.classes_).index(1)
                    model_probabilities[name] = probabilities[
                        :, positive_index
                    ]

                probability_matrix = np.column_stack([
                    model_probabilities[name]
                    for name in model_names
                ])

                weight_vector = np.array(
                    [weights[name] for name in model_names],
                    dtype=float
                )

                if (
                    not np.isfinite(weight_vector).all()
                    or not np.isclose(weight_vector.sum(), 1.0)
                    or (weight_vector < 0).any()
                ):
                    st.error("Saved ensemble weights are invalid.")
                    st.stop()

                ensemble_probabilities = (
                    probability_matrix @ weight_vector
                )

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

    # Load results only after X_new and the uploaded file exist.
    results = st.session_state.get("lunginsight_results")

    # -----------------------------------------------------
    # 5. Display results
    # -----------------------------------------------------

    if results is not None:

        st.header("4. Prediction results")

        tumour_count = int(
            (results["Predicted_Label"] == 1).sum()
        )
        normal_count = int(
            (results["Predicted_Label"] == 0).sum()
        )

        col1, col2, col3 = st.columns(3)
        col1.metric("Samples analysed", len(results))
        col2.metric("Predicted tumour", tumour_count)
        col3.metric("Predicted normal", normal_count)

        display_results = results.copy()
        display_results["Tumour_Probability"] = (
            display_results["Tumour_Probability"] * 100
        ).round(2)

        st.dataframe(display_results, use_container_width=True)

        st.download_button(
            "Download predictions as CSV",
            data=results.to_csv(index=False).encode("utf-8"),
            file_name="lunginsight_predictions.csv",
            mime="text/csv"
        )
        st.download_button(
            "Download summary as PDF",
            data=build_pdf_report(
                "LUAD vs Normal — Prediction Summary",
                results,
                ["Tumour_Probability"],
                "Prediction",
                "Predictions are research outputs from the saved ensemble. Validate externally before drawing scientific conclusions."
            ),
            file_name="lunginsight_luad_vs_normal_report.pdf",
            mime="application/pdf",
            key="download_normal_pdf"
        )

        st.caption(
            "Tumour probability is the ensemble's output, not a "
            "calibrated clinical risk estimate."
        )

        # -------------------------------------------------
        # 6. SHAP and LIME explanations
        # -------------------------------------------------

        st.header("5. Explain an individual prediction")

        st.write(
            "Select a sample to explore approximate local explanations "
            "of the saved weighted ensemble."
        )

        sample_options = [
            f"{i}: {sample_ids.iloc[i]}"
            for i in range(len(X_new))
        ]

        selected_option = st.selectbox(
            "Select a sample",
            sample_options,
            key="explain_sample"
        )

        selected_index = int(selected_option.split(":")[0])

        selected_sample = X_new.iloc[[selected_index]]
        selected_prediction = results.iloc[selected_index]

        st.write(
            f"**Prediction:** {selected_prediction['Prediction']}"
        )
        st.write(
            "**Ensemble tumour probability:** "
            f"{selected_prediction['Tumour_Probability']:.2%}"
        )

        st.warning(
            "These explanations use a limited set of candidate genes "
            "and hold other genes fixed. They are approximate model "
            "explanations, not evidence of biological causation."
        )

        # Rank genes by weighted frequency of selection.
        gene_scores = {}

        for name in model_names:
            model_weight = float(weights[name])

            if model_weight <= 0:
                continue

            selector = models[name].named_steps["select"]
            selected_indices = selector.get_support(indices=True)

            for idx in selected_indices:
                gene = expected_features[idx]
                gene_scores[gene] = (
                    gene_scores.get(gene, 0.0) + model_weight
                )

        candidate_genes = [
            gene
            for gene, _ in sorted(
                gene_scores.items(),
                key=lambda item: item[1],
                reverse=True
            )[:12]
        ]

        if len(candidate_genes) < 2:
            st.warning(
                "There are not enough candidate genes for explanations."
            )
        else:
            candidate_indices = [
                expected_features.index(gene)
                for gene in candidate_genes
            ]

            # Candidate matrix used for local explanations.
            candidate_data = X_new.iloc[
                :, candidate_indices
            ].to_numpy(dtype=float)

            # Fill missing values for explainer sampling.
            # Model predictions still use each saved pipeline's imputer.
            medians = np.nanmedian(candidate_data, axis=0)
            medians = np.where(np.isfinite(medians), medians, 0.0)

            candidate_data_filled = np.where(
                np.isfinite(candidate_data),
                candidate_data,
                medians
            )

            selected_candidates = candidate_data_filled[
                selected_index
            ]

            base_values = selected_sample.to_numpy(dtype=float)[0]

            st.caption(
                "Candidate genes are selected using their weighted "
                "frequency across nonzero-weight model pipelines."
            )

            st.write("Candidate genes:", ", ".join(candidate_genes))

            def ensemble_probability_for_candidates(candidate_matrix):
                candidate_matrix = np.asarray(
                    candidate_matrix, dtype=float
                )

                if candidate_matrix.ndim == 1:
                    candidate_matrix = candidate_matrix.reshape(1, -1)

                # Keep all non-candidate genes at the selected sample's
                # values; vary only the candidate genes.
                full_matrix = np.tile(
                    base_values, (candidate_matrix.shape[0], 1)
                )

                full_matrix[:, candidate_indices] = candidate_matrix

                full_df = pd.DataFrame(
                    full_matrix,
                    columns=expected_features
                )

                all_probabilities = []

                for name in model_names:
                    model = models[name]
                    p = model.predict_proba(full_df)
                    positive_index = list(model.classes_).index(1)
                    all_probabilities.append(p[:, positive_index])

                probability_matrix = np.column_stack(all_probabilities)

                current_weights = np.array(
                    [weights[name] for name in model_names],
                    dtype=float
                )

                return probability_matrix @ current_weights

            if st.button(
                "Generate SHAP and LIME explanations",
                key="generate_explanations"
            ):
                try:
                    import shap
                    from lime.lime_tabular import LimeTabularExplainer

                    with st.spinner(
                        "Calculating explanations. This may take a while..."
                    ):
                        # Use a small deterministic background set.
                        rng = np.random.default_rng(42)
                        background_count = min(
                            10, len(candidate_data_filled)
                        )

                        background_indices = rng.choice(
                            len(candidate_data_filled),
                            size=background_count,
                            replace=False
                        )

                        background = candidate_data_filled[
                            background_indices
                        ]

                        # SHAP KernelExplainer explains the weighted
                        # ensemble's probability output.
                        shap_explainer = shap.KernelExplainer(
                            ensemble_probability_for_candidates,
                            background
                        )

                        shap_values = shap_explainer.shap_values(
                            selected_candidates.reshape(1, -1),
                            nsamples=100
                        )

                        shap_array = np.asarray(shap_values)
                        shap_array = np.squeeze(shap_array)

                        if shap_array.ndim > 1:
                            shap_array = shap_array[-1]

                        if shap_array.size != len(candidate_genes):
                            raise ValueError(
                                "Unexpected SHAP output shape: "
                                f"{shap_array.shape}"
                            )

                        shap_df = pd.DataFrame({
                            "Gene": candidate_genes,
                            "SHAP contribution": shap_array.astype(float)
                        })

                        shap_df["Absolute contribution"] = (
                            shap_df["SHAP contribution"].abs()
                        )

                        shap_df = shap_df.sort_values(
                            "Absolute contribution",
                            ascending=False
                        )

                        st.subheader("SHAP: local contributions")

                        st.write(
                            "Positive values push the model score upward; "
                            "negative values push it downward relative to "
                            "the explainer's background."
                        )

                        shap_plot_df = shap_df.sort_values(
                            "SHAP contribution"
                        ).set_index("Gene")

                        fig, ax = plt.subplots(figsize=(9, 5))
                        shap_plot_df["SHAP contribution"].plot.barh(
                            ax=ax
                        )
                        ax.set_xlabel(
                            "Contribution to ensemble tumour probability"
                        )
                        ax.set_ylabel("Candidate gene")
                        ax.set_title("SHAP local explanation")
                        fig.tight_layout()
                        st.pyplot(fig)
                        plt.close(fig)

                        st.dataframe(
                            shap_df,
                            use_container_width=True
                        )

                        # LIME approximates the same ensemble score.
                        lime_explainer = LimeTabularExplainer(
                            training_data=candidate_data_filled,
                            feature_names=candidate_genes,
                            mode="regression",
                            discretize_continuous=False,
                            random_state=42
                        )

                        lime_explanation = lime_explainer.explain_instance(
                            data_row=selected_candidates,
                            predict_fn=ensemble_probability_for_candidates,
                            num_features=len(candidate_genes),
                            num_samples=1000
                        )

                        lime_df = pd.DataFrame(
                            lime_explanation.as_list(),
                            columns=[
                                "Gene feature",
                                "LIME contribution"
                            ]
                        )

                        st.subheader("LIME: local approximation")

                        lime_plot_df = lime_df.set_index("Gene feature")

                        fig, ax = plt.subplots(figsize=(9, 5))
                        lime_plot_df.sort_values(
                            "LIME contribution"
                        )["LIME contribution"].plot.barh(ax=ax)
                        ax.set_xlabel(
                            "Contribution in local surrogate model"
                        )
                        ax.set_ylabel("Gene feature")
                        ax.set_title("LIME local explanation")
                        fig.tight_layout()
                        st.pyplot(fig)
                        plt.close(fig)

                        st.dataframe(
                            lime_df,
                            use_container_width=True
                        )

                except Exception as exc:
                    st.error(
                        "Explanation generation failed. "
                        f"Error details: {exc}"
                    )

# ---------------------------------------------------------
# LUAD vs LUSC subtype classifier (separate from LUAD vs Normal)
# ---------------------------------------------------------

SUBTYPE_MODEL_PATH = Path("artifacts/luad_lusc_ensemble.joblib")

with st.expander("🧬 Open LUAD vs LUSC Subtype Classifier", expanded=False):
    st.subheader("LUAD vs LUSC — Adaptive Weighted Ensemble")
    st.write(
        "Classifies compatible tumour gene-expression samples as LUAD or LUSC. "
        "This research workflow is separate from the LUAD-vs-Normal classifier above."
    )

    if not SUBTYPE_MODEL_PATH.exists():
        st.error(f"Subtype model artifact not found: {SUBTYPE_MODEL_PATH}")
    else:
        @st.cache_resource(show_spinner=False)
        def load_subtype_artifact(path_string):
            return joblib.load(path_string)

        try:
            subtype_artifact = load_subtype_artifact(str(SUBTYPE_MODEL_PATH))
            subtype_features = list(subtype_artifact["feature_names"])
            subtype_model_names = list(subtype_artifact["model_names"])
            subtype_models = subtype_artifact["models"]
            subtype_weights = subtype_artifact["optimized_weights"]
            subtype_threshold = float(subtype_artifact.get("decision_threshold", 0.5))
        except Exception as exc:
            st.error(f"Could not load the subtype model artifact: {exc}")
            subtype_artifact = None

        if subtype_artifact is not None:
            subtype_file = st.file_uploader(
                "Upload LUAD/LUSC gene-expression CSV",
                type=["csv"],
                key="luad_lusc_upload",
                help="One row per sample, one column per gene, and optionally a sample_id column."
            )

            if subtype_file is not None:
                try:
                    subtype_input = pd.read_csv(subtype_file)
                except Exception as exc:
                    st.error(f"Could not read subtype CSV: {exc}")
                    subtype_input = None

                if subtype_input is not None:
                    if subtype_input.empty:
                        st.error("The uploaded subtype CSV is empty.")
                    else:
                        subtype_id_candidates = {
                            "sample_id", "sampleid", "sample", "id",
                            "sample_name", "patient_id"
                        }
                        subtype_id_col = next(
                            (c for c in subtype_input.columns
                             if str(c).strip().lower() in subtype_id_candidates),
                            None
                        )
                        if subtype_id_col is not None:
                            subtype_sample_ids = subtype_input[subtype_id_col].astype(str).reset_index(drop=True)
                            subtype_features_df = subtype_input.drop(columns=[subtype_id_col]).copy()
                        else:
                            subtype_sample_ids = pd.Series(
                                [f"Sample_{i + 1}" for i in range(len(subtype_input))]
                            )
                            subtype_features_df = subtype_input.copy()

                        if not subtype_features_df.columns.is_unique:
                            st.error("Duplicate column names were found. Ensure every gene column is unique.")
                        else:
                            subtype_missing = [g for g in subtype_features if g not in subtype_features_df.columns]
                            if subtype_missing:
                                st.error(
                                    f"Missing {len(subtype_missing)} required genes. "
                                    "This model requires the gene identifiers used during training."
                                )
                                st.caption("Examples: " + ", ".join(map(str, subtype_missing[:15])))
                            else:
                                subtype_X = subtype_features_df.loc[:, subtype_features].copy()
                                subtype_original = subtype_X.copy()
                                for col in subtype_X.columns:
                                    subtype_X[col] = pd.to_numeric(subtype_X[col], errors="coerce")

                                subtype_invalid = (
                                    subtype_X.isna() & subtype_original.notna()
                                    & subtype_original.astype(str).apply(lambda col: col.str.strip().ne(""))
                                )
                                if subtype_invalid.any().any():
                                    st.error("Non-numeric gene-expression values were found. Correct them before prediction.")
                                elif np.isinf(subtype_X.to_numpy(dtype=float)).any():
                                    st.error("Infinite values were found in the subtype CSV.")
                                elif subtype_X.isna().all(axis=1).any():
                                    st.error("At least one sample has no usable gene-expression values.")
                                else:
                                    st.success(
                                        f"Validated {len(subtype_X)} samples and all {len(subtype_features)} required genes."
                                    )
                                    st.dataframe(subtype_input.head(5), use_container_width=True)

                                    if st.button("Predict LUAD vs LUSC", type="primary", key="predict_luad_lusc"):
                                        try:
                                            with st.spinner("Running the adaptive weighted ensemble..."):
                                                p_by_model = {}
                                                for model_name in subtype_model_names:
                                                    fitted_model = subtype_models[model_name]
                                                    proba = fitted_model.predict_proba(subtype_X)
                                                    pos_idx = list(fitted_model.classes_).index(1)
                                                    p_by_model[model_name] = proba[:, pos_idx]

                                                weight_vector = np.array(
                                                    [float(subtype_weights[name]) for name in subtype_model_names],
                                                    dtype=float
                                                )
                                                if (
                                                    not np.isfinite(weight_vector).all()
                                                    or (weight_vector < 0).any()
                                                    or not np.isclose(weight_vector.sum(), 1.0)
                                                ):
                                                    raise ValueError("Saved subtype ensemble weights are invalid.")

                                                probability_matrix = np.column_stack(
                                                    [p_by_model[name] for name in subtype_model_names]
                                                )
                                                p_lusc = probability_matrix @ weight_vector
                                                pred = (p_lusc >= subtype_threshold).astype(int)
                                                subtype_results = pd.DataFrame({
                                                    "Sample_ID": subtype_sample_ids.to_numpy(),
                                                    "LUAD_Probability": 1.0 - p_lusc,
                                                    "LUSC_Probability": p_lusc,
                                                    "Predicted_Label": pred,
                                                    "Predicted_Subtype": ["LUSC" if v == 1 else "LUAD" for v in pred]
                                                })
                                                st.session_state["luad_lusc_results"] = subtype_results
                                                st.session_state["luad_lusc_input_signature"] = (
                                                    subtype_file.name, subtype_file.size
                                                )
                                        except Exception as exc:
                                            st.error(f"Subtype prediction failed: {exc}")

                                    subtype_results = st.session_state.get("luad_lusc_results")
                                    current_signature = (subtype_file.name, subtype_file.size)
                                    if (
                                        subtype_results is not None
                                        and st.session_state.get("luad_lusc_input_signature") == current_signature
                                    ):
                                        st.markdown("#### Subtype prediction results")
                                        subtype_col1, subtype_col2, subtype_col3 = st.columns(3)
                                        subtype_col1.metric("Samples analysed", len(subtype_results))
                                        subtype_col2.metric("Predicted LUAD", int((subtype_results["Predicted_Label"] == 0).sum()))
                                        subtype_col3.metric("Predicted LUSC", int((subtype_results["Predicted_Label"] == 1).sum()))
                                        subtype_display = subtype_results.copy()
                                        for probability_col in ["LUAD_Probability", "LUSC_Probability"]:
                                            subtype_display[probability_col] = (subtype_display[probability_col] * 100).round(2)
                                        st.dataframe(subtype_display, use_container_width=True)
                                        st.download_button(
                                            "Download LUAD-vs-LUSC report (CSV)",
                                            data=subtype_results.to_csv(index=False).encode("utf-8"),
                                            file_name="lunginsight_luad_lusc_predictions.csv",
                                            mime="text/csv",
                                            key="download_luad_lusc_results"
                                        )
                                        st.download_button(
                                            "Download LUAD-vs-LUSC summary (PDF)",
                                            data=build_pdf_report(
                                                "LUAD vs LUSC — Prediction Summary",
                                                subtype_results,
                                                ["LUAD_Probability", "LUSC_Probability"],
                                                "Predicted_Subtype",
                                                "Predictions are research outputs from the saved adaptive ensemble. This workflow is intended for compatible tumour RNA-seq samples, not clinical diagnosis."
                                            ),
                                            file_name="lunginsight_luad_lusc_report.pdf",
                                            mime="application/pdf",
                                            key="download_subtype_pdf"
                                        )
                                        st.caption(
                                            "Probabilities are model outputs, not calibrated clinical risk estimates. "
                                            "This research prototype is not a diagnostic tool."
                                        )

                                        st.markdown("#### Explain one subtype prediction (SHAP + LIME)")
                                        st.caption(
                                            "Explanations vary a limited set of candidate genes while holding other genes fixed; "
                                            "they explain model behaviour, not biological causation."
                                        )
                                        sample_labels = [
                                            f"{i}: {subtype_sample_ids.iloc[i]} — {subtype_results.iloc[i]['Predicted_Subtype']}"
                                            for i in range(len(subtype_results))
                                        ]
                                        selected_subtype_option = st.selectbox(
                                            "Choose a sample to explain",
                                            sample_labels,
                                            key="luad_lusc_explain_sample"
                                        )
                                        selected_subtype_idx = int(selected_subtype_option.split(":")[0])

                                        if st.button("Generate subtype SHAP and LIME", key="generate_luad_lusc_explanations"):
                                            try:
                                                import shap
                                                from lime.lime_tabular import LimeTabularExplainer

                                                # Candidate genes: weighted frequency of selection across fitted pipelines.
                                                subtype_gene_scores = {}
                                                for model_name in subtype_model_names:
                                                    w = float(subtype_weights[model_name])
                                                    if w <= 0:
                                                        continue
                                                    selector = subtype_models[model_name].named_steps.get("feature_selection")
                                                    if selector is None:
                                                        continue
                                                    for feature_idx in selector.get_support(indices=True):
                                                        gene = subtype_features[feature_idx]
                                                        subtype_gene_scores[gene] = subtype_gene_scores.get(gene, 0.0) + w
                                                candidate_subtype_genes = [
                                                    gene for gene, _ in sorted(
                                                        subtype_gene_scores.items(), key=lambda item: item[1], reverse=True
                                                    )[:10]
                                                ]
                                                if len(candidate_subtype_genes) < 2:
                                                    raise ValueError("Not enough candidate genes are available for explanations.")
                                                candidate_subtype_indices = [subtype_features.index(g) for g in candidate_subtype_genes]
                                                all_candidate_values = subtype_X.iloc[:, candidate_subtype_indices].to_numpy(dtype=float)
                                                medians = np.nanmedian(all_candidate_values, axis=0)
                                                medians = np.where(np.isfinite(medians), medians, 0.0)
                                                candidate_filled = np.where(np.isfinite(all_candidate_values), all_candidate_values, medians)
                                                selected_candidate_values = candidate_filled[selected_subtype_idx]
                                                base_subtype_values = subtype_X.iloc[selected_subtype_idx].to_numpy(dtype=float)
                                                base_subtype_values = np.where(np.isfinite(base_subtype_values), base_subtype_values, np.nan_to_num(base_subtype_values, nan=0.0))

                                                weight_vector = np.array(
                                                    [float(subtype_weights[name]) for name in subtype_model_names],
                                                    dtype=float
                                                )

                                                def subtype_ensemble_for_candidates(candidate_matrix):
                                                    candidate_matrix = np.asarray(candidate_matrix, dtype=float)
                                                    if candidate_matrix.ndim == 1:
                                                        candidate_matrix = candidate_matrix.reshape(1, -1)
                                                    full_matrix = np.tile(base_subtype_values, (candidate_matrix.shape[0], 1))
                                                    full_matrix[:, candidate_subtype_indices] = candidate_matrix
                                                    full_frame = pd.DataFrame(full_matrix, columns=subtype_features)
                                                    model_ps = []
                                                    for model_name in subtype_model_names:
                                                        fitted = subtype_models[model_name]
                                                        probas = fitted.predict_proba(full_frame)
                                                        model_ps.append(probas[:, list(fitted.classes_).index(1)])
                                                    return np.column_stack(model_ps) @ weight_vector

                                                rng = np.random.default_rng(42)
                                                bg_n = min(10, len(candidate_filled))
                                                bg_idx = rng.choice(len(candidate_filled), size=bg_n, replace=False)
                                                with st.spinner("Calculating approximate subtype explanations..."):
                                                    shap_explainer = shap.KernelExplainer(
                                                        subtype_ensemble_for_candidates, candidate_filled[bg_idx]
                                                    )
                                                    shap_values = shap_explainer.shap_values(
                                                        selected_candidate_values.reshape(1, -1), nsamples=100
                                                    )
                                                    shap_array = np.squeeze(np.asarray(shap_values))
                                                    if shap_array.ndim > 1:
                                                        shap_array = shap_array[-1]
                                                    if shap_array.size != len(candidate_subtype_genes):
                                                        raise ValueError(f"Unexpected SHAP output shape: {shap_array.shape}")
                                                    shap_df = pd.DataFrame({
                                                        "Gene": candidate_subtype_genes,
                                                        "SHAP contribution to LUSC probability": shap_array.astype(float)
                                                    })
                                                    shap_df["Absolute contribution"] = shap_df.iloc[:, 1].abs()
                                                    shap_df = shap_df.sort_values("Absolute contribution", ascending=False)
                                                    st.write("**SHAP local contributions** (positive values increase the LUSC probability relative to the background).")
                                                    st.dataframe(shap_df, use_container_width=True)
                                                    fig, ax = plt.subplots(figsize=(9, 4.5))
                                                    shap_df.sort_values(shap_df.columns[1]).set_index("Gene")[shap_df.columns[1]].plot.barh(ax=ax)
                                                    ax.set_xlabel("Contribution to LUSC probability")
                                                    fig.tight_layout()
                                                    st.pyplot(fig)
                                                    plt.close(fig)

                                                    lime_explainer = LimeTabularExplainer(
                                                        training_data=candidate_filled,
                                                        feature_names=candidate_subtype_genes,
                                                        mode="regression",
                                                        discretize_continuous=False,
                                                        random_state=42
                                                    )
                                                    lime_exp = lime_explainer.explain_instance(
                                                        data_row=selected_candidate_values,
                                                        predict_fn=subtype_ensemble_for_candidates,
                                                        num_features=len(candidate_subtype_genes),
                                                        num_samples=1000
                                                    )
                                                    lime_df = pd.DataFrame(
                                                        lime_exp.as_list(), columns=["Gene feature", "LIME contribution"]
                                                    )
                                                    st.write("**LIME local approximation**")
                                                    st.dataframe(lime_df, use_container_width=True)
                                                    fig, ax = plt.subplots(figsize=(9, 4.5))
                                                    lime_df.set_index("Gene feature").sort_values("LIME contribution")["LIME contribution"].plot.barh(ax=ax)
                                                    ax.set_xlabel("Contribution in local surrogate model")
                                                    fig.tight_layout()
                                                    st.pyplot(fig)
                                                    plt.close(fig)
                                            except Exception as exc:
                                                st.error(f"Subtype explanation generation failed: {exc}")


st.caption(
    "LungInsight AI is a research prototype. Results require "
    "independent validation and must not be used as a clinical diagnosis."
)




# ==========================================
# CHATBOT STYLING — SOLID, OPAQUE PANEL
# ==========================================

st.markdown("""
<style>

/* Floating chatbot button */
.st-key-chat_launcher {
    position: fixed !important;
    bottom: 22px !important;
    right: 24px !important;
    z-index: 10000 !important;
}

.st-key-chat_launcher button {
    width: 62px !important;
    height: 62px !important;
    border-radius: 50% !important;
    background: #147D68 !important;
    color: #FFFFFF !important;
    border: 2px solid #FFFFFF !important;
    box-shadow: 0 4px 18px rgba(0, 0, 0, 0.25) !important;
    font-size: 27px !important;
}

/* Main chatbot panel: completely opaque */
/* Chat panel: keep the full panel inside the viewport */
.st-key-chat_panel {
    position: fixed !important;
    right: 24px !important;
    bottom: 88px !important;
    top: auto !important;

    width: 380px !important;
    max-width: calc(100vw - 32px) !important;
    height: min(680px, calc(100vh - 120px)) !important;
    max-height: calc(100vh - 120px) !important;

    overflow-y: auto !important;
    overflow-x: hidden !important;
    z-index: 9999 !important;

    background: #FFFFFF !important;
    opacity: 1 !important;
    color: #20252B !important;

    border: 1px solid #D5E2DE !important;
    border-radius: 18px !important;
    padding: 15px !important;
    box-shadow: 0 8px 30px rgba(0, 0, 0, 0.22) !important;
    box-sizing: border-box !important;
    isolation: isolate !important;
}

/* Green header: fully visible and compact */
.chat-title {
    background: linear-gradient(135deg, #12483E, #16836C) !important;
    color: #FFFFFF !important;
    padding: 14px 16px !important;
    border-radius: 13px !important;
    margin-bottom: 12px !important;
    width: 100% !important;
    box-sizing: border-box !important;
    overflow-wrap: anywhere !important;
}

.chat-title h3 {
    color: #FFFFFF !important;
    margin: 0 !important;
    font-size: 21px !important;
    line-height: 1.3 !important;
}

.chat-title p {
    color: #E1F4EF !important;
    font-size: 12px !important;
    line-height: 1.4 !important;
    margin: 6px 0 0 0 !important;
}

/* Mobile screens */
@media (max-width: 480px) {
    .st-key-chat_panel {
        right: 8px !important;
        bottom: 82px !important;
        width: calc(100vw - 16px) !important;
        max-width: calc(100vw - 16px) !important;
        height: calc(100vh - 110px) !important;
        max-height: calc(100vh - 110px) !important;
    }
}
/* Keep nested Streamlit containers from showing the dashboard through */
.st-key-chat_panel [data-testid="stVerticalBlock"],
.st-key-chat_panel [data-testid="stVerticalBlockBorderWrapper"],
.st-key-chat_panel [data-testid="stForm"] {
    background-color: #FFFFFF !important;
    opacity: 1 !important;
}

/* Chat conversation area */
.st-key-chat_panel [data-testid="stChatMessage"] {
    background-color: #F2F6F5 !important;
    color: #20252B !important;
    border: 1px solid #E1E9E6 !important;
    border-radius: 12px !important;
    padding: 10px 12px !important;
    margin-bottom: 8px !important;
}

/* Message text */
.st-key-chat_panel [data-testid="stChatMessage"] p,
.st-key-chat_panel [data-testid="stMarkdownContainer"] p,
.st-key-chat_panel label {
    color: #20252B !important;
}

/* Input field */
.st-key-chat_panel [data-testid="stTextInput"] input {
    background-color: #F1F3F6 !important;
    color: #20252B !important;
    border: 1px solid #D4D9DF !important;
    border-radius: 10px !important;
    opacity: 1 !important;
}

/* Input placeholder */
.st-key-chat_panel [data-testid="stTextInput"] input::placeholder {
    color: #737B85 !important;
    opacity: 1 !important;
}

/* Chatbot buttons */
.st-key-chat_panel .stButton button,
.st-key-chat_panel [data-testid="stFormSubmitButton"] button {
    background-color: #FFFFFF !important;
    color: #25312E !important;
    border: 1px solid #D5DEDA !important;
    border-radius: 10px !important;
    white-space: normal !important;
    text-align: left !important;
    min-height: 42px !important;
}

/* Hover effect */
.st-key-chat_panel .stButton button:hover,
.st-key-chat_panel [data-testid="stFormSubmitButton"] button:hover {
    background-color: #E8F5F0 !important;
    border-color: #147D68 !important;
    color: #12483E !important;
}

/* Chat header */
.chat-title {
    background: linear-gradient(135deg, #12483E, #16836C) !important;
    color: #FFFFFF !important;
    padding: 15px !important;
    border-radius: 13px !important;
    margin-bottom: 12px !important;
}

.chat-title h3 {
    color: #FFFFFF !important;
    margin: 0 !important;
}

.chat-title p {
    color: #E1F4EF !important;
    font-size: 12px !important;
    margin: 5px 0 0 0 !important;
}

/* Clear conversation button */
.st-key-chat_panel [data-testid="stButton"] button {
    transition: background-color 0.15s ease-in-out !important;
}

/* Smaller screens */
@media (max-width: 480px) {
    .st-key-chat_panel {
        right: 8px !important;
        bottom: 84px !important;
        width: calc(100vw - 16px) !important;
        max-width: calc(100vw - 16px) !important;
        height: 78vh !important;
    }

    .st-key-chat_launcher {
        right: 16px !important;
        bottom: 16px !important;
    }
}

</style>
""", unsafe_allow_html=True)


# ==========================================
# DASHBOARD PLACEHOLDER
# Keep your real dashboard in your main app.py
# ==========================================




# ==========================================
# KNOWLEDGE BASE
# ==========================================

gene_answers = {
    "What is EGFR?":
        "EGFR encodes a cell-surface receptor involved in cell growth "
        "and signalling. Certain EGFR alterations are important in "
        "lung cancer research.",

    "What is TP53?":
        "TP53 encodes the p53 tumour-suppressor protein, which helps "
        "regulate DNA damage responses, cell-cycle control and cell death.",

    "What is KRAS?":
        "KRAS encodes a protein involved in cell-growth signalling. "
        "Certain KRAS mutations are relevant to lung cancer biology.",

    "What is ALK?":
        "ALK encodes a receptor tyrosine kinase. Certain ALK gene "
        "rearrangements can drive a subset of lung cancers.",

    "What is ROS1?":
        "ROS1 encodes a receptor tyrosine kinase. ROS1 gene fusions "
        "are found in a subset of lung cancers.",

    "What is BRAF?":
        "BRAF encodes a protein in a cell-signalling pathway. Some "
        "BRAF mutations are studied in lung adenocarcinoma.",

    "What is MET?":
        "MET encodes a receptor involved in cell growth and survival. "
        "Some MET alterations are relevant to lung cancer.",

    "What is ERBB2 (HER2)?":
        "ERBB2, also called HER2, encodes a receptor tyrosine kinase "
        "involved in cell signalling.",

    "What is STK11?":
        "STK11 encodes a tumour-suppressor protein involved in "
        "cellular energy regulation and growth control.",

    "What is KEAP1?":
        "KEAP1 helps regulate the NRF2 pathway, which is involved "
        "in cellular responses to oxidative stress."
}

quick_answers = {
    "How does LungInsight AI work?":
        "LungInsight AI analyzes gene-expression data using machine "
        "learning to classify samples. It is a research prototype.",

    "What does model accuracy mean?":
        "Accuracy measures the fraction of predictions that are correct. "
        "Because our dataset is imbalanced, also examine balanced "
        "accuracy, macro F1, and recall for each class.",

    "What is LUAD vs LUSC?":
        "LUAD means lung adenocarcinoma, while LUSC means lung "
        "squamous cell carcinoma. Our current dataset focuses on LUAD.",

    "How does our ensemble work?":
        "An ensemble combines predictions from multiple models. "
        "Our project evaluates Decision Tree, Random Forest, XGBoost, "
        "AdaBoost, Gaussian Naive Bayes and Logistic Regression.",

    "What are SHAP and LIME?":
        "SHAP and LIME help explain which features influenced a model "
        "prediction. They describe model behaviour, not biological causation.",

    "Which genes influenced my prediction?":
        "This requires the actual explanation output for a selected sample. "
        "This demo is not connected to your trained model, so it cannot "
        "reliably identify those genes yet."
}


def get_answer(question):
    # Exact answers from the knowledge base
    if question in gene_answers:
        return gene_answers[question]

    if question in quick_answers:
        return quick_answers[question]

    q = question.lower().strip()

    # Medical safety
    if any(word in q for word in [
        "diagnosis", "diagnose", "treatment", "cure", "symptom"
    ]):
        return (
            "I can explain general research concepts, but I cannot "
            "diagnose cancer or recommend treatment. A model prediction "
            "is not a medical diagnosis. Please consult a qualified "
            "healthcare professional for personal medical concerns."
        )

    # General gene questions
    if any(word in q for word in [
        "gene", "biomarker", "egfr", "tp53", "kras", "alk",
        "ros1", "braf", "met", "stk11", "keap1", "her2", "erbb2"
    ]):
        return (
            "I can explain general gene biology. Try asking about "
            "EGFR, TP53, KRAS, ALK, ROS1, BRAF, MET, ERBB2, STK11 "
            "or KEAP1. I cannot identify your model's top genes without "
            "its actual feature-selection or explanation results."
        )

    # Model questions
    if any(word in q for word in [
        "accuracy", "performance", "f1", "auc", "model", "ensemble"
    ]):
        return (
            "I can explain the models and evaluation metrics. For actual "
            "performance values, please consult the measured results "
            "in the dashboard. This chatbot does not load your results files."
        )

    # General fallback
    return (
        "Thanks for your question! 😊 I'm currently a guided LungInsight "
        "assistant and may not know every open-ended question.\n\n"
        "**You can ask me about:**\n"
        "- LungInsight AI and its workflow\n"
        "- Lung cancer genes and biomarkers\n"
        "- LUAD vs LUSC\n"
        "- Ensemble models and performance metrics\n"
        "- SHAP and LIME\n\n"
        "Try rephrasing your question or select one of the options above. "
        "Later, we can connect a local language model for more flexible answers."
    )


# ==========================================
# SESSION STATE
# ==========================================

if "chat_open" not in st.session_state:
    st.session_state.chat_open = False

if "messages" not in st.session_state:
    st.session_state.messages = [{
        "role": "assistant",
        "content": (
            "Hi! 👋 Welcome to LungInsight AI.\n\n"
            "Choose a suggested question below or type your own question."
        )
    }]


# ==========================================
# FLOATING CHAT ICON
# ==========================================

if st.button(
    "💬",
    key="chat_launcher",
    help="Open LungInsight Assistant"
):
    st.session_state.chat_open = not st.session_state.chat_open


# ==========================================
# CHAT WINDOW
# ORDER: HEADER → QUESTIONS → CONVERSATION → INPUT
# ==========================================

if st.session_state.chat_open:

    with st.container(key="chat_panel"):

        # Header
        header_col, close_col = st.columns([5, 1])

        with header_col:
            st.markdown("""
            <div class="chat-title">
                <h3>🧬 LungInsight Assistant</h3>
                <p>Research guide · Here to help you explore</p>
            </div>
            """, unsafe_allow_html=True)

        with close_col:
            if st.button("✕", key="chat_close", help="Close assistant"):
                st.session_state.chat_open = False
                st.rerun()

        # ----------------------------------
        # 1. SUGGESTED QUESTIONS FIRST
        # ----------------------------------

        st.markdown("**✨ Quick questions**")

        general_questions = list(quick_answers.keys())

        for i in range(0, len(general_questions), 2):
            cols = st.columns(2)

            for j, col in enumerate(cols):
                idx = i + j

                if idx < len(general_questions):
                    question = general_questions[idx]

                    if col.button(
                        question,
                        key=f"general_{idx}",
                        use_container_width=True
                    ):
                        st.session_state.messages.extend([
                            {"role": "user", "content": question},
                            {
                                "role": "assistant",
                                "content": get_answer(question)
                            }
                        ])
                        st.rerun()

        # ----------------------------------
        # 2. GENE EXPLORER
        # ----------------------------------

        with st.expander("🧬 Explore gene questions"):
            for i, question in enumerate(gene_answers.keys()):
                if st.button(
                    question,
                    key=f"gene_{i}",
                    use_container_width=True
                ):
                    st.session_state.messages.extend([
                        {"role": "user", "content": question},
                        {
                            "role": "assistant",
                            "content": get_answer(question)
                        }
                    ])
                    st.rerun()

        st.divider()

        # ----------------------------------
        # 3. CONVERSATION BELOW QUESTIONS
        # ----------------------------------

        st.markdown("**💭 Conversation**")

        with st.container(height=210):
            for message in st.session_state.messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

        # ----------------------------------
        # 4. CUSTOM QUESTION INPUT
        # ----------------------------------

        with st.form("chat_question_form", clear_on_submit=True):
            custom_question = st.text_input(
                "Ask your own question",
                placeholder="e.g. What is the role of EGFR?"
            )

            send = st.form_submit_button(
                "Send ➤",
                use_container_width=True
            )

            if send and custom_question.strip():
                question = custom_question.strip()

                st.session_state.messages.extend([
                    {"role": "user", "content": question},
                    {
                        "role": "assistant",
                        "content": get_answer(question)
                    }
                ])
                st.rerun()

        # ----------------------------------
        # 5. CLEAR CHAT
        # ----------------------------------

        if st.button("Clear conversation", key="chat_clear"):
            st.session_state.messages = [{
                "role": "assistant",
                "content": (
                    "Hi! 👋 Welcome to LungInsight AI. "
                    "Choose a suggested question or type your own."
                )
            }]
            st.rerun()
