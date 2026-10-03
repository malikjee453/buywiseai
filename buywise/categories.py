from __future__ import annotations

"""BuyWiseAI's category taxonomy for general-purpose shopping queries."""

SHOPPING_CATEGORIES: dict[str, dict[str, list[str]]] = {
    "Electronics & Technology": {
        "Cell Phones & Accessories": ["smartphone", "phone", "iphone", "android", "charger", "case", "screen protector", "smartwatch"],
        "Computers & Tablets": ["laptop", "desktop", "computer", "tablet", "ipad", "monitor", "printer", "gpu", "cpu", "ram", "ssd"],
        "TV, Audio & Home Theater": ["tv", "television", "soundbar", "headphones", "earbuds", "speaker", "home theater", "streaming device"],
        "Cameras & Photography": ["camera", "dslr", "mirrorless", "lens", "drone", "action camera", "tripod"],
        "Video Games & Consoles": ["playstation", "ps5", "xbox", "nintendo", "switch", "gaming console", "video game", "controller"],
    },
    "Fashion & Apparel": {
        "Women's Clothing": ["women", "women's", "girl", "girls", "dress", "top", "jeans", "activewear", "swimwear", "outerwear", "shalwar", "kameez", "kurta", "shalwar kameez"],
        "Men's Clothing": ["men", "men's", "shirt", "pants", "suit", "jacket", "underwear"],
        "Kids & Baby Apparel": ["kids", "children", "baby clothes", "newborn", "toddler", "teen clothing", "girls clothing", "boys clothing"],
        "Shoes": ["shoes", "sneakers", "boots", "heels", "sandals", "athletic footwear"],
        "Jewelry & Watches": ["jewelry", "ring", "necklace", "earrings", "watch", "smart band"],
        "Accessories": ["handbag", "wallet", "belt", "hat", "sunglasses", "scarf"],
    },
    "Home, Garden & Furniture": {
        "Furniture": ["sofa", "bed", "bedroom", "desk", "dining table", "mattress", "chair", "furniture"],
        "Kitchen & Dining": ["cookware", "bakeware", "blender", "air fryer", "dinnerware", "utensils", "kitchen"],
        "Bedding & Bath": ["bedsheet", "sheet", "comforter", "pillow", "towel", "bath mat"],
        "Home Decor": ["rug", "curtain", "lighting", "wall art", "candle", "mirror", "decor"],
        "Garden & Outdoor": ["patio", "grill", "lawnmower", "plant", "gardening", "garden"],
        "Home Improvement": ["tools", "smart home", "fixture", "paint", "building material", "hardware"],
    },
    "Beauty & Personal Care": {
        "Makeup & Cosmetics": ["makeup", "foundation", "lipstick", "eyeshadow", "makeup brush", "cosmetics"],
        "Skin Care": ["skincare", "cleanser", "moisturizer", "serum", "sunscreen", "face mask"],
        "Hair Care": ["shampoo", "conditioner", "hair dye", "hair dryer", "hair styling"],
        "Fragrances": ["perfume", "cologne", "fragrance", "body spray"],
        "Personal Care": ["toothpaste", "oral care", "deodorant", "shaving", "feminine hygiene"],
    },
    "Health & Wellness": {
        "Vitamins & Supplements": ["vitamin", "supplement", "multivitamin", "protein powder", "herbal supplement", "gummies"],
        "Medical Supplies": ["first aid", "thermometer", "mask", "mobility aid", "medical supplies"],
        "Fitness & Nutrition": ["weight management", "hydration", "healthy snacks", "nutrition"],
    },
    "Sports & Outdoors": {
        "Exercise & Fitness": ["treadmill", "dumbbell", "yoga mat", "resistance band", "gym", "fitness"],
        "Outdoor Recreation": ["camping", "tent", "hiking", "fishing", "bike", "bicycle", "outdoor"],
        "Team Sports": ["football", "soccer", "basketball", "baseball", "sports gear"],
    },
    "Toys, Hobbies & Baby": {
        "Toys & Games": ["toy", "doll", "board game", "puzzle", "lego", "building blocks", "action figure"],
        "Baby Essentials": ["stroller", "car seat", "diaper", "wipes", "baby monitor", "feeding"],
        "Arts & Crafts": ["sewing", "yarn", "painting supplies", "scrapbooking", "craft"],
    },
    "Automotive & Industrial": {
        "Car Parts & Accessories": ["tire", "tyre", "engine oil", "oil filter", "wiper", "car mat", "car cleaning"],
        "Tools & Equipment": ["diagnostic tool", "car jack", "wrench", "garage storage", "workshop"],
    },
    "Groceries & Pets": {
        "Pantry Staples": ["snacks", "beverage", "canned food", "breakfast", "coffee", "tea", "grocery"],
        "Pet Supplies": ["dog food", "cat food", "pet food", "pet bed", "pet toy", "aquarium", "pet supplies"],
    },
}


def all_categories() -> list[str]:
    return [
        subcategory
        for department in SHOPPING_CATEGORIES.values()
        for subcategory in department
    ]


def detect_categories(query: str, limit: int = 3) -> list[str]:
    text = query.lower()
    matches: list[tuple[int, str]] = []

    for department, subcategories in SHOPPING_CATEGORIES.items():
        for subcategory, keywords in subcategories.items():
            score = sum(1 for keyword in keywords if keyword in text)
            if score:
                matches.append((score, subcategory))

    matches.sort(key=lambda item: (-item[0], item[1]))
    return [name for _, name in matches[:limit]]
