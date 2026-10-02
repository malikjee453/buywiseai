from tools.web_search import search_web

def search_products(query, category=None):
    records = search_web(query)
    if category:
        category_text = category.lower()
        filtered = [
            r for r in records
            if category_text in r.get("text", "").lower()
        ]
        if filtered:
            records = filtered
    return records
