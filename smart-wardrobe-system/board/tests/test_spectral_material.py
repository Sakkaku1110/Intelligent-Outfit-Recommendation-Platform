#!/usr/bin/env python3
import json
import pathlib
import tempfile
import unittest

from app.core import save_ws63_payload
from app.spectral_material import classify_json_lines, classify_material


LOW_LIGHT_SAMPLE = {
    "device": "WS63",
    "sensor": "GY-AS7341",
    "f1": 2,
    "f2": 1,
    "f3": 2,
    "f4": 2,
    "f5": 2,
    "f6": 5,
    "f7": 16,
    "f8": 21,
    "clear": 31,
    "nir": 6,
}


class SpectralMaterialTest(unittest.TestCase):
    def test_real_low_light_sample_is_not_overclaimed(self):
        result = classify_material(LOW_LIGHT_SAMPLE)

        self.assertEqual(result["quality"], "low_light")
        self.assertEqual(result["material"], "unknown_low_light")
        self.assertLess(result["confidence"], 0.2)

    def test_denim_like_reading(self):
        result = classify_material(
            {
                "f1": 90,
                "f2": 110,
                "f3": 120,
                "f4": 95,
                "f5": 70,
                "f6": 52,
                "f7": 35,
                "f8": 28,
                "clear": 670,
                "nir": 135,
            }
        )

        self.assertEqual(result["quality"], "ok")
        self.assertEqual(result["material"], "denim")

    def test_leather_like_reading(self):
        result = classify_material(
            {
                "f1": 45,
                "f2": 48,
                "f3": 54,
                "f4": 70,
                "f5": 98,
                "f6": 132,
                "f7": 170,
                "f8": 186,
                "clear": 750,
                "nir": 320,
            }
        )

        self.assertEqual(result["quality"], "ok")
        self.assertEqual(result["material"], "leather")

    def test_json_lines_skips_non_sensor_logs(self):
        lines = [
            "APP|[SYS INFO] mem: used:91340, free:272488",
            json.dumps(LOW_LIGHT_SAMPLE),
        ]

        results = classify_json_lines(lines)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["material"], "unknown_low_light")

    def test_save_ws63_payload_adds_material_prediction(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "ws63_latest.json"
            saved = save_ws63_payload(path, LOW_LIGHT_SAMPLE)
            disk = json.loads(path.read_text(encoding="utf-8"))

        self.assertIn("received_at", saved)
        self.assertEqual(saved["material_prediction"]["material"], "unknown_low_light")
        self.assertEqual(disk["material_prediction"]["sensor"], "GY-AS7341")


if __name__ == "__main__":
    unittest.main()
