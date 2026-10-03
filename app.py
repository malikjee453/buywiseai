import streamlit as st
from urllib.parse import urlsplit

from buywise.llm import LLMConfigurationError, get_llm
from buywise.providers import run_search
from buywise.schemas import ProductQuery


st.set_page_config(page_title="BuyWiseAI", page_icon="🛒", layout="wide")

st.title("🛒 BuyWiseAI")
st.caption("Find the best products and prices across Pakistan shopping websites.")

st.markdown(
    """
    ### What are you looking for?
    Search for any product — electronics, fashion, home, beauty, sports,
    groceries, baby products, automotive, tools, and more.
    """
)

query = st.text_input(
    "Product query",
    "iPhone 15 128GB",
    label_visibility="collapsed",
)

currency = st.selectbox(
    "Display currency",
    ["PKR", "USD", "GBP"],
)

max_results = st.slider(
    "Maximum results",
    5,
    10,
    10,
)

if st.button("🔎 Search products", type="primary"):
    if not query.strip():
        st.error("Enter a product query.")
    else:
        try:
            parsed = ProductQuery(
                original_query=query,
                normalized_query=query,
                country="Pakistan",
                currency=currency,
            )

            with st.status(
                "Searching shopping websites...",
                expanded=False,
            ) as status:
                raw_results, listings, errors = run_search(
                    parsed.normalized_query,
                    parsed.country,
                    max_results=max_results,
                )
                status.update(
                    label=f"Search complete — {len(listings)} priced results",
                    state="complete",
                )

            if not listings:
                st.warning(
                    "No priced product results were found. "
                    "Try a more specific product query."
                )
            else:
                distinct_sources = len({
                    urlsplit(str(item.url)).netloc.lower().removeprefix("www.")
                    for item in listings
                })

                st.success(
                    f"Found {len(listings)} verified priced results from "
                    f"{distinct_sources} different shopping websites."
                )

                if len(listings) < 10 or distinct_sources < 8:
                    st.info(
                        "Coverage is below the target of 10 products from "
                        "8+ different shopping websites. BuyWiseAI will "
                        "never duplicate a store or invent a price."
                    )
                else:
                    st.success(
                        "Coverage target reached: 10 products from 8+ "
                        "different shopping websites."
                    )

                rows = [
                    {
                        "Product": item.title,
                        "Price": f"{item.currency} {item.price:,.2f}",
                        "Shopping website": item.source,
                        "Product page": str(item.url),
                    }
                    for item in listings
                ]

                st.dataframe(
                    rows,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Product page": st.column_config.LinkColumn(
                            "Product page"
                        ),
                    },
                )

        except Exception as exc:
            st.error(f"Search failed: {type(exc).__name__}: {exc}")

# Keep Groq initialization available for the next AI recommendation stage,
# but do not expose configuration/status details in the public interface.
try:
    get_llm()
except LLMConfigurationError:
    pass
