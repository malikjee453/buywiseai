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

    web_evidence = search_web(search_text)
    product_evidence = search_products(
        search_text,
        structured.get("category", "")
    )
    price_evidence = search_prices(search_text, "PKR")

    retrieved = (
        local_evidence
        + web_evidence
        + product_evidence
        + price_evidence
    )

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
                "title": e.get("metadata", {}).get(
                    "title", e.get("source", "Source")
                ),
                "source": e.get("source", "Unknown"),
                "type": e.get("source_type", "unknown"),
            }
            for e in retrieved
        ],
    }
