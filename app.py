import streamlit as st
from core.config import APP_NAME, APP_TAGLINE
from core.llm import llm_available
from ui.styles import inject_styles
from ui.components import render_brand, render_research_form, render_comparison_table

st.set_page_config(page_title="BuyWise AI", page_icon="🛒", layout="wide")
inject_styles()

if "result" not in st.session_state:
    st.session_state.result = None

render_brand(APP_NAME, APP_TAGLINE)
st.markdown(
    '<div class="hero-copy">Research products with evidence before you buy.</div>',
    unsafe_allow_html=True,
)

if not llm_available():
    st.info("Add GROQ_API_KEY to Streamlit Secrets before using AI research.")

query, category, budget, language = render_research_form()

if st.button("🔎 Research", type="primary"):
    if not query.strip():
        st.warning("Please enter what you want to research.")
    elif not llm_available():
        st.error("GROQ_API_KEY is not configured.")
    else:
        with st.spinner("BuyWise AI is researching and verifying evidence..."):
            try:
                from agents.orchestrator import run_buywise
                st.session_state.result = run_buywise(
                    query, category, budget, language
                )
            except Exception as exc:
                st.session_state.result = None
                st.error(f"Research failed: {exc}")

result = st.session_state.result
if result:
    st.divider()
    st.markdown("## Research Result")
    comparison = result.get("comparison", [])
    if comparison:
        render_comparison_table(comparison, category=result.get("category", category))
    else:
        st.info("No matching products were found in the available evidence.")

with st.expander("How BuyWise AI works"):
    st.markdown(
        "**Query Analyzer → Orchestrator → Advanced RAG → Evidence Agent "
        "→ Comparison Agent → Response Agent**"
    )
