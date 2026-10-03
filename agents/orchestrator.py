from agents.query_analyzer import analyze_query
from agents.evidence_agent import verify_evidence
from agents.comparison_agent import build_comparison
from agents.response_agent import generate_response
from rag.retriever import retrieve
from tools.web_search import search_web
from tools.product_search import search_products
from tools.price_search import search_prices

def run_buywise(query, category="", budget="", language="English"):
    structured = analyze_query(query, category, budget, language)

    search_text = " ".join([
        query,
        structured.get("category", ""),
        structured.get("use_case", ""),
        " ".join(structured.get("requirements", []))
    ])

    local_evidence = retrieve(
        search_text,
        structured.get("category", ""),
        structured.get("budget", "")
    )

    web_evidence = search_web(search_text, structured.get("category", category))

    # Reuse the same live records instead of fetching the shopping site
    # three separate times for web, product, and price evidence.
    product_evidence = web_evidence
    price_evidence = [
        item for item in web_evidence
        if item.get("price")
        and item.get("metadata", {}).get("currency") == "PKR"
    ]

    # Keep useful local RAG guidance, but never expose fictional demo records
    # as evidence for real shopping research.
    safe_local = [
        item for item in local_evidence
        if "demo" not in str(item.get("source", "")).lower()
        and "demonstration" not in str(item.get("text", "")).lower()
    ]
    retrieved = safe_local + web_evidence

    evidence = verify_evidence(query, structured, retrieved)
    comparison = build_comparison(query, structured, evidence)
    summary = generate_response(
        query, structured, evidence, comparison, language
    )

    return {
        "summary": summary,
        "comparison": comparison,
        "evidence_notes": (
            evidence.get("notes", [])
            + evidence.get("conflicts", [])
            + evidence.get("gaps", [])
        ),
        "sources": [
            {
                "title": p.get("name", "Product"),
                "source": item.get("source", "Unknown"),
                "type": "live_web",
                "url": item.get("url", ""),
            }
            for p in comparison
            for item in p.get("availability", [])
            if item.get("url")
        ],
    }
