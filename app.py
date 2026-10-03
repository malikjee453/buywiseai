import streamlit as st

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

# Pakistan is the fixed market for BuyWiseAI.
# The app searches for a maximum of 10 final verified products.
if st.button("🔎 Search products", type="primary"):
    if not query.strip():
        st.error("Enter a product query.")
    else:
        try:
            parsed = ProductQuery(
                original_query=query,
                normalized_query=query,
                country="Pakistan",
                currency="PKR",
            )

            raw_results, listings, errors = run_search(
                parsed.normalized_query,
                parsed.country,
                max_results=10,
            )

            if not listings:
                st.warning(
                    "No priced product results were found. "
                    "Try a more specific product query."
                )
            else:
                rows = [
                    {
                        "Product": item.title,
                        "Price": f"{item.currency} {item.price:,.2f}",
                        "Shopping website": item.source,
                        "Product page": str(item.url),
                    }
                    for item in listings[:10]
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
