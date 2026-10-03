from __future__ import annotations

# Broad shopping catalog. These are discovery targets; availability varies by
# product/category. Add new stores here without changing the search engine.
PLATFORMS = {
    "general_marketplaces": {
        "Daraz": "daraz.pk",
        "AliExpress": "aliexpress.com",
        "Goto": "goto.com.pk",
        "iShopping": "ishopping.pk",
        "PeshMart": "peshawarmart.pk",
        "Shophive": "shophive.com",
        "HomeShopping": "homeshopping.pk",
    },
    "electronics_and_tech": {
        "PriceOye": "priceoye.pk",
        "Telemart": "telemart.pk",
        "Mega.pk": "mega.pk",
        "Symbios": "symbios.pk",
        "BuyTechThings": "buytechthings.com",
        "Al-Fatah Electronics": "alfatah.com.pk",
        "Japan Electronics": "japanelectronics.com.pk",
        "Paklap": "paklap.pk",
        "Czone": "czone.com.pk",
    },
    "grocery_home_everyday": {
        "Naheed": "naheed.pk",
        "Chase Value": "chasevalue.pk",
        "Metro Online": "metro-online.pk",
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
        "Junaid Jamshed": "j.urban?invalid",
        "Outfitters": "outfitters.com.pk",
        "Bagallery": "bagallery.com",
    },
    "international": {
        "Amazon": "amazon.com",
        "eBay": "ebay.com",
        "Walmart": "walmart.com",
        "Best Buy": "bestbuy.com",
        "Target": "target.com",
        "Newegg": "newegg.com",
        "Flipkart": "flipkart.com",
    },
}


# Remove the one intentionally invalid placeholder above while preserving the
# visible catalog behavior.
PLATFORMS["fashion_beauty"].pop("Junaid Jamshed", None)


def all_platforms() -> dict[str, str]:
    return {
        name: domain
        for category in PLATFORMS.values()
        for name, domain in category.items()
    }


def platform_count() -> int:
    return len(all_platforms())


PLATFORM_GROUPS = {
    "fashion": [
        "Daraz", "Sapphire", "Limelight", "Gul Ahmed", "Maria B",
        "Nishat Linen", "Alkaram Studio", "Ethnic", "Khaadi",
        "Outfitters", "Bonanza Satrangi", "Bagallery", "AliExpress",
        "Amazon", "eBay", "Goto", "iShopping", "PeshMart",
    ],
    "electronics": [
        "Daraz", "PriceOye", "Telemart", "Shophive", "Mega.pk",
        "HomeShopping", "Symbios", "BuyTechThings", "AliExpress",
        "Amazon", "eBay", "Walmart", "Best Buy", "Target", "Newegg",
        "Czone", "Paklap", "Goto", "iShopping", "PeshMart",
    ],
    "groceries": [
        "Daraz", "Naheed", "Chase Value", "Metro Online", "Goto",
        "iShopping", "AliExpress", "Amazon", "Walmart", "Target",
    ],
    "beauty": [
        "Daraz", "Bagallery", "Sapphire", "Limelight", "Gul Ahmed",
        "Khaadi", "AliExpress", "Amazon", "eBay", "Walmart",
    ],
    "home": [
        "Daraz", "Goto", "iShopping", "Chase Value", "Naheed",
        "Metro Online", "Mega.pk", "AliExpress", "Amazon", "eBay",
        "Walmart", "Target",
    ],
    "sports": [
        "Daraz", "Goto", "iShopping", "AliExpress", "Amazon", "eBay",
        "Walmart", "Target", "Decathlon", "Newegg",
    ],
    "baby": [
        "Daraz", "Goto", "iShopping", "AliExpress", "Amazon", "eBay",
        "Walmart", "Target", "Newegg",
    ],
    "automotive": [
        "Daraz", "Goto", "iShopping", "AliExpress", "Amazon", "eBay",
        "Walmart", "Target", "Newegg",
    ],
    "general": [
        "Daraz", "AliExpress", "Goto", "iShopping", "PeshMart",
        "Amazon", "eBay", "Walmart", "Target", "Best Buy", "Newegg",
        "Flipkart", "Mega.pk", "HomeShopping",
    ],
}


def relevant_platforms(query: str, max_platforms: int = 20) -> dict[str, str]:
    text = query.lower()

    if any(k in text for k in (
        "shalwar", "kameez", "kurta", "dress", "shirt", "jeans",
        "shoe", "shoes", "sneaker", "jacket", "clothing", "fashion",
        "suit", "abaya", "scarf", "watch",
    )):
        group = "fashion"
    elif any(k in text for k in (
        "laptop", "phone", "iphone", "mobile", "computer", "tablet",
        "monitor", "tv", "camera", "headphone", "earbuds", "console",
        "ps5", "xbox", "charger", "printer", "gpu",
    )):
        group = "electronics"
    elif any(k in text for k in (
        "grocery", "milk", "snack", "coffee", "tea", "rice", "flour",
        "food", "beverage", "cereal",
    )):
        group = "groceries"
    elif any(k in text for k in (
        "perfume", "makeup", "cosmetic", "skincare", "skin care",
        "shampoo", "conditioner", "beauty", "lipstick",
    )):
        group = "beauty"
    elif any(k in text for k in (
        "sofa", "furniture", "air fryer", "blender", "kitchen",
        "mattress", "pillow", "curtain", "rug", "home decor",
    )):
        group = "home"
    elif any(k in text for k in (
        "football", "soccer", "basketball", "treadmill", "dumbbell",
        "gym", "camping", "tent", "bicycle", "bike",
    )):
        group = "sports"
    elif any(k in text for k in (
        "baby", "stroller", "diaper", "toy", "lego", "doll",
    )):
        group = "baby"
    elif any(k in text for k in (
        "car", "tyre", "tire", "wiper", "engine oil", "brake",
        "automotive", "motorcycle",
    )):
        group = "automotive"
    else:
        group = "general"

    catalog = all_platforms()
    names = PLATFORM_GROUPS[group][:max_platforms]
    return {name: catalog[name] for name in names if name in catalog}
