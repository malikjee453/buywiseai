from agents.query_analyzer import analyze_query
from agents.evidence_agent import verify_evidence
from agents.comparison_agent import build_comparison
from agents.response_agent import generate_response
from rag.retriever import retrieve
from tools.web_search import search_web


def _safe_text(value):
    if value is None:
        return ""
    return str(value).strip()


def _safe_requirements(value):
    if not isinstance(value, list):
        return []
    return [
        str(item).strip()
        for item in value
        if item is not None and str(item).strip()
    ]


def run_buywise(query, category="", budget="", language="English"):
    structured = analyze_query(query, category, budget, language)

    if not isinstance(structured, dict):
        structured = {}

    structured["category"] = _safe_text(structured.get("category")) or _safe_text(category)
    structured["budget"] = _safe_text(structured.get("budget")) or _safe_text(budget)
    structured["use_case"] = _safe_text(structured.get("use_case"))
    structured["requirements"] = _safe_requirements(
        structured.get("requirements")
    )

    search_parts = [
        _safe_text(query),
        structured["category"],
        structured["use_case"],
        " ".join(structured["requirements"]),
    ]
    search_text = " ".join(part for part in search_parts if part)

    local_evidence = retrieve(
        search_text,
        structured["category"],
        structured["budget"],
    )

    web_evidence = search_web(
        search_text,
        structured["category"] or category,
    )

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
