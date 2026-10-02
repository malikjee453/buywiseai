import re
from pathlib import Path
from core.config import TOP_K

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "knowledge_base"

def _tokens(text):
    return set(re.findall(r"[a-zA-Z0-9]+", text.lower()))

def _load_documents():
    docs = []
    for path in DATA_DIR.glob("*.md"):
        text = path.read_text(encoding="utf-8")
        front, body = {}, text
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) == 3:
                for line in parts[1].splitlines():
                    if ":" in line:
                        k, v = line.split(":", 1)
                        front[k.strip()] = v.strip()
                body = parts[2].strip()
        docs.append({"text": body, "source": front.get("source", path.name),
                     "source_type": front.get("source_type", "knowledge_base"),
                     "metadata": front})
    return docs

def retrieve(query, category="", budget=""):
    q = _tokens(query)
    ranked = []
    for doc in _load_documents():
        score = len(q & _tokens(doc["text"]))
        if category and category.lower() in doc["text"].lower():
            score += 3
        if budget:
            digits = re.sub(r"\D", "", budget)
            if digits and digits in re.sub(r"\D", "", doc["text"]):
                score += 2
        ranked.append((score, doc))
    ranked.sort(key=lambda x: x[0], reverse=True)
    return [doc for score, doc in ranked[:TOP_K] if score > 0] or [d for _, d in ranked[:TOP_K]]
