
import streamlit as st

st.set_page_config(
    page_title="LungInsight AI",
    page_icon="🧬",
    layout="wide"
)

# ==========================================
# STYLING
# ==========================================

st.markdown("""
<style>
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
    color: white !important;
    border: 2px solid white !important;
    box-shadow: 0 4px 18px rgba(0,0,0,.25) !important;
    font-size: 27px !important;
}

.st-key-chat_panel {
    position: fixed !important;
    right: 24px !important;
    bottom: 96px !important;
    width: 380px !important;
    max-width: calc(100vw - 32px) !important;
    height: min(720px, 82vh) !important;
    overflow-y: auto !important;
    z-index: 9999 !important;
    background: var(--secondary-background-color) !important;
    border: 1px solid #B8D8CF !important;
    border-radius: 18px !important;
    padding: 15px !important;
    box-shadow: 0 8px 30px rgba(0,0,0,.22) !important;
}

.st-key-chat_panel .stButton button {
    border-radius: 10px !important;
    white-space: normal !important;
    text-align: left !important;
    min-height: 42px;
}

.chat-title {
    background: linear-gradient(135deg, #12483E, #16836C);
    color: white;
    padding: 15px;
    border-radius: 13px;
    margin-bottom: 12px;
}

.chat-title h3 {
    color: white;
    margin: 0;
}

.chat-title p {
    color: #E1F4EF;
    font-size: 12px;
    margin: 5px 0 0 0;
}
</style>
""", unsafe_allow_html=True)


# ==========================================
# DASHBOARD PLACEHOLDER
# Keep your real dashboard in your main app.py
# ==========================================

st.title("🧬 LungInsight AI")
st.write("Lung cancer research and explainable AI dashboard.")
st.info("Open the floating chat icon in the bottom-right corner.")


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
