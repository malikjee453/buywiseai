import streamlit as st

from buywise.llm import LLMConfigurationError, get_llm
from buywise.providers import run_search
from buywise.schemas import ProductQuery

st.set_page_config(page_title="BuyWiseAI", page_icon="🛒", layout="wide")

st.title("🛒 BuyWiseAI")
st.caption("Multi-agent product search and price comparison — Stage 2")

st.markdown(
    """
    ### Real product search
    BuyWiseAI now fans your query out to multiple search providers in parallel,
    extracts only results with a parseable currency price and URL, then removes
    duplicate destination URLs.
    """
)

query = st.text_input("Product query", "iPhone 15 128GB")
country = st.selectbox("Country", ["Pakistan", "United States", "United Kingdom"])
currency = st.selectbox("Display currency", ["PKR", "USD", "GBP"])
max_results = st.slider("Results per provider", 5, 20, 10)

with st.expander("Search provider status"):
    st.write("Serper.dev, SerpAPI, Tavily, Brave Search, and DuckDuckGo")
    st.caption(
        "Paid providers are used only when their API key is configured. "
        "DuckDuckGo does not require a key."
    )

if st.button("🔎 Search products", type="primary"):
    if not query.strip():
        st.error("Enter a product query.")
    else:
        try:
            parsed = ProductQuery(
                original_query=query,
                normalized_query=query,
                country=country,
                currency=currency,
            )

            with st.status("Searching multiple providers...", expanded=True) as status:
                raw_results, listings, errors = run_search(
                    parsed.normalized_query,
                    parsed.country,
                    max_results=max_results,
                )
                status.update(
                    label=f"Search complete — {len(listings)} priced results",
                    state="complete",
                )

            if errors:
                with st.expander(f"Provider issues ({len(errors)})"):
                    for error in errors:
                        st.warning(error)

            if not listings:
                st.warning(
                    "No priced product results were found. Add one or more provider "
                    "API keys in Streamlit Secrets, or try a more specific product query."
                )
            else:
                st.success(
                    f"Found {len(listings)} results with a verified URL + parseable price."
                )

                rows = [
                    {
                        "Product": item.title,
                        "Price": f"{item.currency} {item.price:,.2f}",
                        "Source": item.source,
                        "URL": str(item.url),
                    }
                    for item in listings
                ]
                st.dataframe(
                    rows,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "URL": st.column_config.LinkColumn("Product page"),
                    },
                )

                with st.expander("Raw provider results"):
                    st.write(f"Raw results received: {len(raw_results)}")
                    st.json([item.model_dump() for item in raw_results[:100]])

excepted = False

try:
    get_llm()
    st.success("Groq configuration detected. The LLM wrapper is ready.")
except LLMConfigurationError as exc:
    st.info(f"LLM note: {exc}")
