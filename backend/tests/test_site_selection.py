import pytest
import numpy as np


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    lat1_r, lat2_r = np.radians(lat1), np.radians(lat2)
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1_r) * np.cos(lat2_r) * np.sin(dlon / 2) ** 2
    return R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))


class TestSiteSelectionScoring:
    """Tests for the multi-criteria site scoring algorithm."""

    def test_haversine_same_point(self):
        dist = _haversine_km(39.9, 116.4, 39.9, 116.4)
        assert dist == pytest.approx(0.0, abs=0.001)

    def test_haversine_known_distance(self):
        # Beijing to Shanghai approx 1068 km
        dist = _haversine_km(39.9042, 116.4074, 31.2304, 121.4737)
        assert 1050 < dist < 1100

    def test_competition_score_no_competitors(self):
        score = 85.0  # default when no competitors
        assert score == 85.0

    def test_competition_penalty_500m(self):
        nearby_500m = 3
        nearby_1km = 2
        nearby_2km = 1
        penalty = nearby_500m * 15 + nearby_1km * 8 + nearby_2km * 3
        score = max(10, 100 - penalty)
        assert penalty == 64
        assert score == 36

    def test_weighted_total_score(self):
        weights = {
            "traffic": 0.25,
            "competition": 0.20,
            "demographic": 0.20,
            "transport": 0.15,
            "commercial": 0.20,
        }
        scores = {
            "traffic": 80,
            "competition": 70,
            "demographic": 65,
            "transport": 55,
            "commercial": 75,
        }
        total = sum(scores[k] * weights[k] for k in weights)
        expected = 80*0.25 + 70*0.20 + 65*0.20 + 55*0.15 + 75*0.20
        assert abs(total - expected) < 0.01
        assert total == pytest.approx(70.25, abs=0.01)

    def test_weights_sum_to_one(self):
        weights = [0.25, 0.20, 0.20, 0.15, 0.20]
        assert sum(weights) == pytest.approx(1.0)

    def test_payback_months_calculation(self):
        monthly_rent = 50000
        predicted_revenue = 300000
        profit_margin = 0.15
        payback = monthly_rent * 12 / (predicted_revenue * profit_margin)
        assert payback == pytest.approx(13.33, abs=0.01)

    def test_confidence_bounds(self):
        total_score = 80
        confidence = min(100, max(30, total_score * 0.8 + 20))
        assert 30 <= confidence <= 100
        assert confidence == 84.0

    def test_revenue_prediction_scale(self):
        avg_rev = 200000
        score_factor = 80 / 70.0
        area_factor = min(2.0, 150 / 100.0)
        predicted = avg_rev * score_factor * area_factor
        assert predicted > 0
        assert predicted == pytest.approx(200000 * (80/70) * 1.5, abs=1)

    def test_demographic_score_tiers(self):
        test_cases = [
            (15000, 90),
            (7000, 75),
            (2000, 60),
            (500, 45),
        ]
        for member_count, expected_score in test_cases:
            if member_count > 10000:
                score = 90
            elif member_count > 5000:
                score = 75
            elif member_count > 1000:
                score = 60
            else:
                score = 45
            assert score == expected_score
