# 🛒 BuyWise AI

**Research before you buy.**

Evidence-grounded shopping research assistant using Advanced RAG + Multi-Agent AI.

## Fixed rules
- **BuyWise** = bold, orange, large
- **AI** = small
- Groq model = `openai/gpt-oss-120b`
- GitHub repository
- Streamlit deployment

## Architecture
Query Analyzer → Orchestrator → Advanced RAG → Evidence Agent → Comparison Agent → Response Agent

## Run locally
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Create `.streamlit/secrets.toml`:
```toml
GROQ_API_KEY = "your_key"
```

Run:
```bash
streamlit run app.py
```

The included product records are fictional demonstration data only.
