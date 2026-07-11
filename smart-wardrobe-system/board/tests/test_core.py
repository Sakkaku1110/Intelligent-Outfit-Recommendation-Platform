#!/usr/bin/env python3
import pathlib
import os
import tempfile
import unittest

from app.core import (
    CloudPreprocessor,
    LLMRecommendationClient,
    RecommendationEngine,
    WardrobeDB,
    color_family,
    merge_analysis_into_payload,
    nearest_color_name_from_rgb,
    target_warmth,
)


class WardrobeCoreTest(unittest.TestCase):
    def test_database_and_recommendation_flow(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = WardrobeDB(pathlib.Path(tmp) / "wardrobe.db")
            db.add_clothing(
                {
                    "name": "白色卫衣",
                    "category": "top",
                    "color": "white",
                    "material": "cotton",
                    "season": "spring_autumn,winter",
                    "occasion": "school,casual",
                    "warmth": 3,
                    "favorite_score": 4,
                }
            )
            db.add_clothing(
                {
                    "name": "黑色长裤",
                    "category": "bottom",
                    "color": "black",
                    "material": "cotton",
                    "season": "spring_autumn,winter",
                    "occasion": "school,commute",
                    "warmth": 3,
                    "favorite_score": 4,
                }
            )
            db.add_clothing(
                {
                    "name": "薄外套",
                    "category": "outer",
                    "color": "navy",
                    "material": "polyester",
                    "season": "spring_autumn",
                    "occasion": "school",
                    "warmth": 3,
                    "favorite_score": 3,
                }
            )
            db.add_clothing(
                {
                    "name": "运动鞋",
                    "category": "shoes",
                    "color": "white",
                    "material": "polyester",
                    "season": "spring_autumn,summer_light,winter",
                    "occasion": "school,casual,sport",
                    "warmth": 2,
                    "favorite_score": 4,
                }
            )

            result = RecommendationEngine().recommend(
                db.list_clothes(),
                {"temperature_c": 15.0, "weather_text": "多云", "source": "test"},
                occasion="school",
            )

            self.assertEqual(db.count(), 4)
            self.assertFalse(result["missing_categories"])
            self.assertGreaterEqual(len(result["recommendations"]), 1)
            first = result["recommendations"][0]
            self.assertIn("items", first)
            self.assertIn("reason", first)

    def test_helpers(self):
        self.assertEqual(target_warmth(30), 1)
        self.assertEqual(target_warmth(4), 5)
        self.assertEqual(color_family("白色"), "white")
        self.assertEqual(nearest_color_name_from_rgb((245, 245, 245))[0], "white")

    def test_merge_analysis_into_payload(self):
        analysis = {
            "category": "bottom",
            "color": "黑色",
            "material": "denim",
            "confidence": {"category": 0.5, "color": 0.8, "material": 0.45},
            "reason": ["测试理由"],
        }
        payload = merge_analysis_into_payload({"category": "auto"}, analysis)
        self.assertEqual(payload["category"], "bottom")
        self.assertEqual(payload["color"], "黑色")
        self.assertEqual(payload["material"], "denim")
        self.assertEqual(payload["category_confidence"], 0.5)

    def test_cloud_preprocessor_json_helpers(self):
        processor = CloudPreprocessor(pathlib.Path(tempfile.gettempdir()))
        data = processor._parse_json_object('```json\n{"box_2d":[10,20,800,900],"confidence":0.9}\n```')
        self.assertEqual(data["box_2d"], [10, 20, 800, 900])
        self.assertEqual(processor._normalized_box([10, 20, 800, 900]), [10, 20, 800, 900])
        self.assertEqual(processor._normalized_box([9, 8, 10, 11]), [0, 0, 1000, 1000])

    def test_llm_recommender_disabled_falls_back_to_local_result(self):
        old_enabled = os.environ.pop("SMART_WARDROBE_LLM_ENABLED", None)
        old_url = os.environ.pop("SMART_WARDROBE_LLM_URL", None)
        self.addCleanup(lambda: os.environ.__setitem__("SMART_WARDROBE_LLM_ENABLED", old_enabled) if old_enabled is not None else None)
        self.addCleanup(lambda: os.environ.__setitem__("SMART_WARDROBE_LLM_URL", old_url) if old_url is not None else None)
        local = {
            "weather": {"temperature_c": 22.0},
            "occasion": "school",
            "recommendations": [{"score": 1, "items": [], "reason": []}],
        }
        result = LLMRecommendationClient().recommend([], local["weather"], "school", local)
        self.assertEqual(result["llm"]["status"], "disabled")
        self.assertEqual(result["recommendations"], local["recommendations"])


if __name__ == "__main__":
    unittest.main()
