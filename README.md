# BuyWiseAI

Multi-agent, RAG-powered product search and price comparison platform.

## Stage 1
Foundation: Pydantic schemas, Groq wrapper for openai/gpt-oss-120b, YAML configuration, logging, Streamlit health check, and tests.

## Run locally
python -m venv .venv
pip install -r requirements.txt
# create .env and set GROQ_API_KEY
pytest -q
streamlit run app.py

## Architecture
```mermaid
flowchart LR
 UI[Streamlit] --> Q[Query Understanding]
 Q --> S[Parallel Search]
 S --> E[Extraction]
 E --> N[Normalize + Dedup]
 N --> R[RAG + Rerank]
 R --> V[Verification]
 V --> C[Coverage Controller]
 C --> A[Recommendation]
 A --> UI
```
