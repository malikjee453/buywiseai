from agents.query_analyzer import analyze_query
from agents.evidence_agent import verify_evidence
from agents.comparison_agent import build_comparison
from agents.response_agent import generate_response
from rag.retriever import retrieve

def run_buywise(query, category="", budget="", language="English"):
    structured = analyze_query(query, category, budget, language)
    search_text = " ".join([
        query, structured.get("category", ""), structured.get("use_case", ""),
        " ".join(structured.get("requirements", []))
    ])
    retrieved = retrieve(search_text, structured.get("category", ""), structured.get("budget", ""))
    evidence = verify_evidence(query, structured, retrieved)
    comparison = build_comparison(query, structured, evidence)
    summary = generate_response(query, structured, evidence, comparison, language)
    return {
        "summary": summary,
        "comparison": comparison,
        "evidence_notes": evidence.get("notes", []) + evidence.get("conflicts", []),
        "sources": [{"title": e["metadata"].get("title", e["source"]),
                     "source": e["source"], "type": e["source_type"]} for e in retrieved]
    }
