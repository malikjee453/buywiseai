import streamlit as st

def render_brand(name, tagline):
    st.markdown(f'<div class="bw-brand"><span class="bw-name">BuyWise</span><span class="bw-ai">AI</span></div><div class="bw-tagline">{tagline}</div>', unsafe_allow_html=True)

def render_research_form():
    query = st.text_area("What are you looking for?", placeholder="Example: I need a phone under PKR 50,000 with good battery life and camera.", height=110)
    c1, c2, c3 = st.columns(3)
    with c1: category = st.selectbox("Category", ["Smartphone", "Laptop", "Electronics", "Appliance", "Other"])
    with c2: budget = st.text_input("Budget (optional)", placeholder="e.g. PKR 50,000")
    with c3: language = st.selectbox("Answer language", ["English", "Urdu"])
    return query, category, budget, language

def render_product_cards(products):
    if not products:
        st.info("No structured comparison was produced from the available evidence.")
        return
    cols = st.columns(min(3, len(products)))
    for i, p in enumerate(products):
        with cols[i % len(cols)]:
            st.markdown(f"### {p.get('name','Product')}")
            if p.get("price"): st.write(f"**Price:** {p['price']}")
            if p.get("strengths"):
                st.write("**Strengths**")
                for x in p["strengths"]: st.write(f"• {x}")
            if p.get("tradeoffs"):
                st.write("**Trade-offs**")
                for x in p["tradeoffs"]: st.write(f"• {x}")
            if p.get("evidence_status"): st.caption(f"Evidence: {p['evidence_status']}")

def render_sources(sources):
    st.markdown("## Sources")
    for s in sources:
        st.markdown(f'<div class="source-card"><b>{s["title"]}</b><br>{s["source"]} · {s["type"]}</div>', unsafe_allow_html=True)
