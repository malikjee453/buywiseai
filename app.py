import streamlit as st
from buywise.llm import LLMConfigurationError, get_llm
from buywise.schemas import ProductQuery

st.set_page_config(page_title="BuyWiseAI", page_icon="🛒", layout="wide")
st.title("🛒 BuyWiseAI")
st.caption("Multi-agent product search and price comparison — Stage 1")
st.markdown("### Foundation check\nStage 1 contains the validated schemas, Groq wrapper, configuration, logging, and tests. Search providers and LangGraph workflow come next.")
query = st.text_input("Test product query", "iPhone 15 128GB")
country = st.selectbox("Country", ["Pakistan", "United States", "United Kingdom"])
currency = st.selectbox("Display currency", ["PKR", "USD", "GBP"])
if st.button("Validate query"):
    try:
        parsed = ProductQuery(original_query=query, normalized_query=query, country=country, currency=currency)
        st.success("Schema validation passed.")
        st.json(parsed.model_dump())
    except Exception as exc:
        st.error(f"Validation failed: {exc}")
try:
    get_llm()
    st.success("Groq configuration detected. The LLM wrapper is ready.")
except LLMConfigurationError as exc:
    st.warning(str(exc))
