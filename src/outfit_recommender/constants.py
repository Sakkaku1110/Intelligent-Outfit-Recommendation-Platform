SEMANTIC_CATEGORIES = (
    "unknown",
    "tops",
    "bottoms",
    "all-body",
    "outerwear",
    "shoes",
    "bags",
    "accessories",
    "jewellery",
    "sunglasses",
    "hats",
    "scarves",
)

CATEGORY_TO_INDEX = {
    category: index for index, category in enumerate(SEMANTIC_CATEGORIES)
}

