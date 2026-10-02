import streamlit as st

def inject_styles():
    st.markdown('''
    <style>
    .block-container { max-width:1180px; padding-top:2rem; }
    .bw-brand { display:flex; align-items:baseline; gap:7px; margin-bottom:.15rem; }
    .bw-name { font-family:Trebuchet MS,Segoe UI,Arial,sans-serif; font-size:3.35rem;
               line-height:1; font-weight:900; color:#E47C22; letter-spacing:-2px; }
    .bw-ai { font-family:Segoe UI,Arial,sans-serif; font-size:1rem; font-weight:700;
             color:#555; letter-spacing:1px; position:relative; top:-.85rem; }
    .bw-tagline { color:#5d6a64; font-size:1.02rem; margin-bottom:1.5rem; }
    .hero-copy { font-size:1.65rem; font-weight:700; color:#173B2D; margin:.7rem 0 1.2rem; }
    .source-card { padding:.8rem 1rem; border:1px solid #dce5df; border-radius:12px;
                   margin-bottom:.5rem; background:#fbfdfc; }
    </style>
    ''', unsafe_allow_html=True)
