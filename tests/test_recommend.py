"""실행: python3 -m unittest discover tests"""
import unittest

from closet import data, llm, weather
from closet.recommend import (CORE_SLOTS, Context, Outfit, candidates, mood_relation,
                              recommend, score_color, score_fit, score_formality,
                              target_warmth)


class RecommendTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.closet = data.load()
        cls.by_id = {it["id"]: it for it in cls.closet.items}

    def core(self, *ids):
        return [self.by_id[i] for i in ids]

    def test_sample_data_is_valid(self):
        self.assertEqual(data.validate(), [])

    def test_moods_inherit_from_brand_unless_overridden(self):
        self.assertEqual(self.by_id["top-002"]["moods"], ["minimal"])            # 유니클로
        self.assertEqual(self.by_id["top-016"]["moods"], ["classic", "minimal"])  # 덮어쓰기
        self.assertEqual(self.by_id["acc-001"]["moods"], ["minimal"])            # 브랜드 없음

    def test_target_warmth(self):
        for temp, want in [(30, 1), (25, 1), (20, 2), (12, 3), (5, 4), (-3, 5)]:
            self.assertEqual(target_warmth(self.closet, temp), want, temp)

    def test_tpo_filter_excludes_sweats_everywhere(self):
        for tpo in self.closet.tpo:
            for temp in (0, 12, 28):
                ids = {it["id"] for items in candidates(self.closet, Context(tpo, temp)).values()
                       for it in items}
                self.assertNotIn("bottom-006", ids)   # 스웨트팬츠 (격식 1)
                self.assertNotIn("top-009", ids)      # 후디 (격식 1)

    def test_rain_excludes_suede(self):
        dry = candidates(self.closet, Context("commute", 12))["shoes"]
        wet = candidates(self.closet, Context("commute", 12, rain=True))["shoes"]
        self.assertTrue(any(it["material"] == "suede" for it in dry))
        self.assertFalse(any(it["material"] == "suede" for it in wet))

    def test_outer_follows_temperature(self):
        for o in recommend(self.closet, Context("commute", 0), n=5):
            self.assertIn("outer", o.items)
        for o in recommend(self.closet, Context("commute", 30), n=5):
            self.assertNotIn("outer", o.items)

    def test_every_tpo_and_season_gets_outfits(self):
        for tpo, spec in self.closet.tpo.items():
            lo, hi = spec["formality"]
            for temp in (-5, 5, 14, 21, 30):
                outfits = recommend(self.closet, Context(tpo, temp), n=3)
                self.assertEqual(len(outfits), 3, (tpo, temp))
                self.assertEqual(outfits, sorted(outfits, key=lambda o: -o.total))
                for o in outfits:
                    self.assertTrue(0 <= o.total <= 1)
                    for it in o.items.values():
                        self.assertTrue(lo <= it["formality"] <= hi, (tpo, temp, it["id"]))

    def test_results_differ_by_at_least_two_items(self):
        outfits = recommend(self.closet, Context("commute", 8), n=3)
        for i, a in enumerate(outfits):
            for b in outfits[i + 1:]:
                shared = {it["id"] for it in a.core} & {it["id"] for it in b.core}
                self.assertLess(len(shared), max(len(a.core), len(b.core)) - 1)

    def test_color_prefers_one_accent_over_many(self):
        calm, _ = score_color(self.closet, self.core("top-003", "bottom-001", "shoes-002"))
        busy, _ = score_color(self.closet, self.core("top-013", "bottom-007", "shoes-002", "outer-003"))
        self.assertGreater(calm, busy)   # 블루 하나 vs 버건디+카키+스카이블루

    def test_pattern_clash_lowers_color(self):
        solid, _ = score_color(self.closet, self.core("top-016", "bottom-002", "shoes-002"))
        clash, _ = score_color(self.closet, self.core("top-003", "bottom-002", "shoes-002")
                               + [dict(self.by_id["outer-005"], pattern="check")])
        self.assertGreater(solid, clash)

    def test_formality_prefers_consistent_levels(self):
        even, _ = score_formality(self.closet, self.core("top-001", "bottom-001", "shoes-001"), "commute")
        mixed, _ = score_formality(self.closet, self.core("top-001", "bottom-004", "shoes-008"), "commute")
        self.assertGreater(even, mixed)

    def test_fit_prefers_balance(self):
        balanced, _ = score_fit(self.core("top-003", "bottom-001"))   # relaxed + regular
        all_slim, _ = score_fit([self.by_id["top-007"], self.by_id["bottom-009"]])
        self.assertGreater(balanced, all_slim)
        tight_outer, _ = score_fit(self.core("top-004", "bottom-002", "outer-005"))  # 오버 맨투맨 + 블레이저
        no_outer, _ = score_fit(self.core("top-004", "bottom-002"))
        self.assertGreater(no_outer, tight_outer)

    def test_mood_relation(self):
        c = self.closet
        self.assertEqual(mood_relation(c, ["minimal"], ["minimal", "classic"]), 1.0)
        self.assertEqual(mood_relation(c, ["workwear"], ["amekaji"]), 0.75)
        self.assertEqual(mood_relation(c, ["workwear"], ["minimal"]), 0.5)
        self.assertEqual(mood_relation(c, ["techwear"], ["classic"]), 0.0)

    def test_weather_parse(self):
        payload = {"daily": {"apparent_temperature_max": [12.0], "apparent_temperature_min": [4.0],
                             "precipitation_probability_max": [70]}}
        self.assertEqual(weather.parse(payload), (8.0, True))
        payload["daily"]["precipitation_probability_max"] = [None]
        self.assertEqual(weather.parse(payload), (8.0, False))

    def test_llm_prompt_lists_every_candidate(self):
        ctx = Context("date", 8)
        outfits = recommend(self.closet, ctx, n=2)
        prompt = llm.build_prompt(self.closet, ctx, outfits)
        for o in outfits:
            for slot in CORE_SLOTS:
                self.assertIn(o.items[slot]["name"], prompt)


if __name__ == "__main__":
    unittest.main()
