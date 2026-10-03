from buywise.schemas import ProductQuery

if __name__ == "__main__":
    q = ProductQuery(original_query="iPhone 15 128GB", normalized_query="iPhone 15 128GB")
    print("BuyWiseAI Stage 1 OK")
    print(q.model_dump())
