import os

APP_NAME = "BuyWise AI"
APP_TAGLINE = "Research before you buy."
MODEL_NAME = "openai/gpt-oss-120b"
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
TOP_K = 6

def get_groq_api_key():
    key = os.getenv("GROQ_API_KEY")
    if key:
        return key
    try:
        import streamlit as st
        return st.secrets.get("GROQ_API_KEY")
    except Exception:
        return None
