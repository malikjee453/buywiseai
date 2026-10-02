from tools.web_search import search_web

def search_prices(query, currency="PKR"):
    records = search_web(query)
    return [
        r for r in records
        if r.get("price") and r.get("metadata", {}).get("currency") == currency
    ]
