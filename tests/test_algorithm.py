from outfit_recommender.algorithm import (
    UserRequest,
    WardrobeItem,
    WeatherContext,
    recommend_outfits,
    score_item,
)


def test_score_item_prefers_style_and_temperature_match() -> None:
    weather = WeatherContext(temperature_c=18, humidity=60, condition="clear")
    request = UserRequest(occasion="business")
    shirt = WardrobeItem(
        id="shirt",
        name="Business shirt",
        category="tops",
        styles=("business",),
        thickness=3,
        material="cotton",
        in_stock=True,
        days_since_wash=1,
    )
    hoodie = WardrobeItem(
        id="hoodie",
        name="Heavy hoodie",
        category="tops",
        styles=("casual",),
        thickness=5,
        material="fleece",
        in_stock=True,
        days_since_wash=8,
    )

    assert score_item(shirt, weather, request).score > score_item(
        hoodie, weather, request
    ).score


def test_recommend_outfits_filters_not_in_stock_items() -> None:
    items = [
        WardrobeItem("top", "Top", "tops", ("casual",), 2, in_stock=True),
        WardrobeItem("bottom", "Bottom", "bottoms", ("casual",), 2, in_stock=True),
        WardrobeItem("shoe", "Shoe", "shoes", ("casual",), 2, in_stock=True),
        WardrobeItem("lost", "Lost Shoes", "shoes", ("casual",), 2, in_stock=False),
    ]

    recommendations = recommend_outfits(
        items,
        WeatherContext(temperature_c=24),
        UserRequest(occasion="casual"),
    )

    assert recommendations
    recommended_ids = {item.id for item in recommendations[0].items}
    assert "lost" not in recommended_ids


def test_cold_weather_rewards_outerwear() -> None:
    base_items = [
        WardrobeItem("top", "Top", "tops", ("casual",), 4),
        WardrobeItem("bottom", "Bottom", "bottoms", ("casual",), 4),
        WardrobeItem("shoe", "Shoe", "shoes", ("casual",), 3),
    ]
    with_outerwear = [
        *base_items,
        WardrobeItem("coat", "Coat", "outerwear", ("casual",), 5, material="wool"),
    ]

    without = recommend_outfits(
        base_items,
        WeatherContext(temperature_c=3),
        UserRequest(occasion="casual"),
        top_k=1,
    )[0]
    with_coat = recommend_outfits(
        with_outerwear,
        WeatherContext(temperature_c=3),
        UserRequest(occasion="casual"),
        top_k=1,
    )[0]

    assert with_coat.score > without.score
    assert "coat" in {item.id for item in with_coat.items}
