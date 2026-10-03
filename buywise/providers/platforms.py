from __future__ import annotations

# Broad Pakistan shopping coverage. This is a configurable catalog, not a claim
# that it represents every store in Pakistan. New stores can be added here.
PLATFORMS = {
    "general_marketplaces": {
        "Daraz": "daraz.pk",
        "AliExpress": "aliexpress.com",
        "Goto": "goto.com.pk",
        "iShopping": "ishopping.pk",
        "PeshMart": "peshawarmart.pk",
    },
    "electronics_and_tech": {
        "PriceOye": "priceoye.pk",
        "Telemart": "telex.pk",
        "Shophive": "shophive.com",
        "Mega.pk": "mega.pk",
        "HomeShopping": "homeshopping.pk",
        "Symbios": "symbios.pk",
        "BuyTechThings": "buytechthings.com",
        "Al-Fatah Electronics": "alfatah.com.pk",
        "Japan Electronics": "japanelectronics.com.pk",
    },
    "grocery_home_everyday": {
        "Naheed": "naheed.pk",
        "Chase Value": "chasevalue.pk",
    },
    "fashion_beauty": {
        "Sapphire": "sapphireonline.pk",
        "Limelight": "limelight.pk",
        "Gul Ahmed": "gulahmedshop.com",
        "Maria B": "mariab.pk",
        "Nishat Linen": "nishatlinen.com",
        "Alkaram Studio": "alkaramstudio.com",
        "Ethnic": "ethnic.pk",
        "Bonanza Satrangi": "bonanzasatrangi.com",
        "Khaadi": "khaadi.com",
        "Junaid Jamshed": "junaidjamshed.com",
        "Outfitters": "outfitters.com.pk",
        "Bagallery": "bagallery.com",
    },
    "international": {
        "Amazon": "amazon.com",
        "eBay": "ebay.com",
    },
}


def all_platforms() -> dict[str, str]:
    return {
        name: domain
        for category in PLATFORMS.values()
        for name, domain in category.items()
    }


def platform_count() -> int:
    return len(all_platforms())


# Fast category routing: only the most relevant stores are searched first.
PLATFORM_GROUPS = {
    "fashion": ["Daraz", "Sapphire", "Limelight", "Gul Ahmed", "Maria B", "Nishat Linen", "Alkaram Studio", "Ethnic", "Khaadi", "Junaid Jamshed", "Outfitters", "Bonanza Satrangi"],
    "electronics": ["Daraz", "PriceOye", "Telemart", "Shophive", "Mega.pk", "HomeShopping", "Symbios", "BuyTechThings", "AliExpress", "Amazon"],
    "groceries": ["Daraz", "Naheed", "Chase Value", "Goto", "AliExpress"],
    "beauty": ["Daraz", "Bagallery", "Sapphire", "Limelight", "Gul Ahmed", "Khaadi", "AliExpress"],
    "home": ["Daraz", "Goto", "iShopping", "Chase Value", "Naheed", "Mega.pk", "AliExpress", "Amazon"],
    "sports": ["Daraz", "Goto", "iShopping", "AliExpress", "Amazon", "eBay"],
    "baby": ["Daraz", "Goto", "iShopping", "AliExpress", "Amazon", "eBay"],
    "automotive": ["Daraz", "Goto", "iShopping", "AliExpress", "Amazon", "eBay"],
    "general": ["Daraz", "AliExpress", "Goto", "iShopping", "PeshMart", "Amazon", "eBay"],
}


def relevant_platforms(query: str, max_platforms: int = 10) -> dict[str, str]:
    """Return a small, relevant platform set to keep search latency bounded."""
    text = query.lower()
    if any(k in text for k in ("shalwar", "kameez", "kurta", "dress", "shirt", "jeans", "shoe", "shoes", "sneaker", "jacket", "clothing", "fashion", "suit")):
        group = "fashion"
    elif any(k in text for k in ("laptop", "phone", "iphone", "mobile", "computer", "tablet", "monitor", "tv", "camera", "headphone", "earbuds", "console", "ps5", "xbox")):
        group = "electronics"
    elif any(k in text for k in ("grocery", "milk", "snack", "coffee", "tea", "rice", "flour", "food", "beverage")):
        group = "groceries"
    elif any(k in text for k in ("perfume", "makeup", "cosmetic", "skincare", "skin care", "shampoo", "conditioner", "beauty")):
        group = "beauty"
    elif any(k in text for k in ("sofa", "furniture", "air fryer", "blender", "kitchen", "mattress", "pillow", "curtain", "rug", "home decor")):
        group = "home"
    elif any(k in text for k in ("football", "soccer", "basketball", "treadmill", "dumbbell", "gym", "camping", "tent", "bicycle", "bike")):
        group = "sports"
    elif any(k in text for k in ("baby", "stroller", "diaper", "toy", "lego", "doll")):
        group = "baby"
    elif any(k in text for k in ("car", "tyre", "tire", "wiper", "engine oil", "brake", "automotive")):
        group = "automotive"
    else:
        group = "general"

    catalog = all_platforms()
    names = PLATFORM_GROUPS[group][:max_platforms]
    return {name: catalog[name] for name in names if name in catalog}
