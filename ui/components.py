import streamlit as st

def render_brand(name, tagline):
    st.markdown(
        f'<div class="bw-brand"><span class="bw-name">BuyWise</span>'
        f'<span class="bw-ai">AI</span></div>'
        f'<div class="bw-tagline">{tagline}</div>',
        unsafe_allow_html=True,
    )

def render_research_form():
    query = st.text_area(
        "What are you looking for?",
        placeholder=(
            "Example: I need a phone under PKR 50,000 with good battery "
            "life and camera."
        ),
        height=110,
    )
    c1, c2, c3 = st.columns(3)
    with c1:
        category = st.selectbox(
            "Category",
            ["Auto-detect", "Smartphone", "Laptop", "Electronics", "Appliance", "Fashion", "Other"],
        )
    with c2:
        budget = st.text_input(
            "Budget (optional)", placeholder="e.g. PKR 50,000"
        )
    with c3:
        language = st.selectbox(
            "Answer language", ["English", "Urdu"]
        )
    if category == "Auto-detect":
        category = ""
    return query, category, budget, language

def render_comparison_table(products, category=""):
    if not products:
        return

    rows = []
    for p in products:
        specs = p.get("key_specs", {})
        name = str(p.get("name", "Product"))
        price = str(p.get("price", "Not available"))
        battery = str(specs.get("battery", "Not available"))
        camera = str(specs.get("camera", "Not available"))
        source = str(p.get("source", "Source not available"))
        url = str(p.get("source_url", "")).strip()
        verification = p.get("verification", {}) if isinstance(p.get("verification"), dict) else {}
        status = str(verification.get("status", "insufficient")).lower()
        verification_label = "Verified" if status == "verified" else ("Partially verified" if status == "partial" else "Unverified")
        source_cell = f'<a href="{url}" target="_blank" rel="noopener noreferrer">{source} → Open product</a>' if url else source
        rows.append(f"| {name} | {price} | {battery} | {camera} | {verification_label} | {source_cell} |")

    st.markdown(
        f"| {category or 'Product'} | Price (PKR) | Battery | Camera | Verification | Source / Product Page |\n"
        "|---|---:|---|---:|---|---|\n"
        + "\n".join(rows),
        unsafe_allow_html=True,
    )
def render_product_cards(products):
    if not products:
        st.info("No structured comparison was produced from the available evidence.")
        return

    cols = st.columns(min(3, len(products)))
    labels = {
        "display": "Display",
        "performance": "Performance",
        "battery": "Battery",
        "camera": "Camera",
        "storage_ram": "RAM / Storage",
    }

    for i, p in enumerate(products):
        with cols[i % len(cols)]:
            st.markdown(f"### {p.get('name', 'Product')}")
            st.write(f"**Price:** {p.get('price', 'Not available in evidence')}")

            source = p.get("source", "Source not available")
            source_url = p.get("source_url", "")
            if source_url:
                st.markdown(
                    f'<div class="product-source"><b>Source:</b> '
                    f'<a href="{source_url}" target="_blank" rel="noopener noreferrer">{source}</a></div>',
                    unsafe_allow_html=True,
                )
            else:
                st.caption(f"Source: {source}")

            specs = p.get("key_specs", {})
            for key, label in labels.items():
                st.write(
                    f"**{label}:** "
                    f"{specs.get(key, 'Not available in evidence')}"
                )

            if p.get("strengths"):
                st.write("**Strengths**")
                for x in p["strengths"]:
                    st.write(f"• {x}")

            if p.get("tradeoffs"):
                st.write("**Trade-offs**")
                for x in p["tradeoffs"]:
                    st.write(f"• {x}")

            if p.get("requirement_fit"):
                st.write("**Requirement fit**")
                for x in p["requirement_fit"]:
                    st.write(f"• {x}")

            if p.get("evidence_status"):
                st.caption(f"Evidence: {p['evidence_status']}")

            availability = p.get("availability", [])
            if availability:
                st.write("**Available at**")
                for item in availability:
                    source = item.get("source", "Source")
                    url = item.get("url", "")
                    if url:
                        st.markdown(
                            f'<a href="{url}" target="_blank" '
                            f'rel="noopener noreferrer">{source} → '
                            f'Open product/source</a>',
                            unsafe_allow_html=True,
                        )
            else:
                st.caption("Product link: not available in retrieved evidence.")

def render_sources(sources):
    st.markdown("## Sources")
    seen = set()
    for s in sources:
        key = (s.get("title"), s.get("source"))
        if key in seen:
            continue
        seen.add(key)
        url = s.get("url")
        if url:
            st.markdown(
                f'<div class="source-card"><b>{s["title"]}</b><br>'
                f'{s["source"]} · {s["type"]}<br>'
                f'<a href="{url}" target="_blank">Open source</a></div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<div class="source-card"><b>{s["title"]}</b><br>'
                f'{s["source"]} · {s["type"]}</div>'
            )
