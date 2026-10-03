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
