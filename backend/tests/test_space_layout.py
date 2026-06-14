import pytest
from datetime import date, datetime


# ---------------------------------------------------------------------------
# Helper functions mirroring service-level business logic for space layout
# ---------------------------------------------------------------------------

def calc_revenue_per_sqm(revenue: float, area_sqm: float) -> float:
    """Calculate revenue per square meter with zero-area guard."""
    if area_sqm <= 0:
        return 0.0
    return revenue / area_sqm


def calc_items_per_sqm(item_count: int, area_sqm: float) -> float:
    """Calculate item density per square meter."""
    if area_sqm <= 0:
        return 0.0
    return item_count / area_sqm


def calc_traffic_conversion(transactions: int, traffic: int) -> float:
    """Calculate conversion rate from foot traffic to transactions."""
    if traffic <= 0:
        return 0.0
    return transactions / traffic


def normalize_heatmap(zone_revenues: list[dict]) -> list[dict]:
    """Normalize zone revenues to 0-1 intensity scale based on max value."""
    if not zone_revenues:
        return []
    max_revenue = max(z["revenue"] for z in zone_revenues)
    if max_revenue == 0:
        return [{"zone_id": z["zone_id"], "intensity": 0.0} for z in zone_revenues]
    return [
        {"zone_id": z["zone_id"], "intensity": z["revenue"] / max_revenue}
        for z in zone_revenues
    ]


def generate_recommendations(zones: list[dict]) -> list[dict]:
    """Generate layout recommendations for underperforming zones.

    Each zone dict: {zone_id, revenue_per_sqm, traffic, revenue}
    Rules:
    - If a zone's revenue_per_sqm < 50% of avg, flag as underperforming
    - If a zone has high traffic (>= avg) but revenue < avg, flag as conversion opportunity
    """
    if not zones:
        return []

    avg_revenue_per_sqm = sum(z["revenue_per_sqm"] for z in zones) / len(zones)
    avg_traffic = sum(z["traffic"] for z in zones) / len(zones)
    avg_revenue = sum(z["revenue"] for z in zones) / len(zones)

    recommendations = []
    for z in zones:
        if z["revenue_per_sqm"] < avg_revenue_per_sqm * 0.5:
            recommendations.append({
                "zone_id": z["zone_id"],
                "type": "underperforming",
                "message": f"Zone {z['zone_id']} revenue/sqm is below 50% of average",
            })
        elif z["traffic"] >= avg_traffic and z["revenue"] < avg_revenue:
            recommendations.append({
                "zone_id": z["zone_id"],
                "type": "conversion_opportunity",
                "message": f"Zone {z['zone_id']} has high traffic but low revenue",
            })
    return recommendations


def aggregate_sales_to_zones(
    sales: list[dict], zone_item_mapping: dict[str, list[str]]
) -> dict[str, float]:
    """Aggregate sales revenue to zones based on category-to-zone mapping.

    zone_item_mapping: {zone_id: [category1, category2, ...]}
    sales: [{category, revenue}, ...]
    Returns: {zone_id: total_revenue}
    """
    # Build reverse map: category -> zone_id
    category_to_zone = {}
    for zone_id, categories in zone_item_mapping.items():
        for cat in categories:
            category_to_zone[cat] = zone_id

    result: dict[str, float] = {}
    for sale in sales:
        zone_id = category_to_zone.get(sale["category"])
        if zone_id is not None:
            result[zone_id] = result.get(zone_id, 0.0) + sale["revenue"]
    return result


def compare_stores_by_zone_type(
    stores: list[dict], zone_type: str, descending: bool = True
) -> list[dict]:
    """Compare stores by revenue_per_sqm for a given zone type.

    stores: [{store_id, zones: [{zone_type, revenue_per_sqm}, ...]}]
    Returns sorted list of {store_id, revenue_per_sqm} for matching zone type.
    """
    results = []
    for store in stores:
        for zone in store["zones"]:
            if zone["zone_type"] == zone_type:
                results.append({
                    "store_id": store["store_id"],
                    "revenue_per_sqm": zone["revenue_per_sqm"],
                })
                break
    results.sort(key=lambda x: x["revenue_per_sqm"], reverse=descending)
    return results


# ---------------------------------------------------------------------------
# Test classes
# ---------------------------------------------------------------------------


class TestZoneKPICalculation:
    """Tests for zone-level KPI calculations."""

    def test_revenue_per_sqm_basic(self):
        result = calc_revenue_per_sqm(revenue=50000, area_sqm=100)
        assert result == 500.0

    def test_revenue_per_sqm_zero_area(self):
        result = calc_revenue_per_sqm(revenue=50000, area_sqm=0)
        assert result == 0.0

    def test_items_per_sqm(self):
        result = calc_items_per_sqm(item_count=200, area_sqm=50)
        assert result == 4.0

    def test_traffic_conversion(self):
        result = calc_traffic_conversion(transactions=100, traffic=500)
        assert result == pytest.approx(0.2)

    def test_traffic_conversion_zero_traffic(self):
        result = calc_traffic_conversion(transactions=100, traffic=0)
        assert result == 0.0


class TestHeatmapNormalization:
    """Tests for heatmap intensity normalization."""

    def test_normalize_single_zone(self):
        zones = [{"zone_id": "A", "revenue": 5000}]
        result = normalize_heatmap(zones)
        assert len(result) == 1
        assert result[0]["intensity"] == 1.0

    def test_normalize_multiple_zones(self):
        zones = [
            {"zone_id": "A", "revenue": 10000},
            {"zone_id": "B", "revenue": 5000},
            {"zone_id": "C", "revenue": 2500},
        ]
        result = normalize_heatmap(zones)
        intensities = {r["zone_id"]: r["intensity"] for r in result}
        assert intensities["A"] == pytest.approx(1.0)
        assert intensities["B"] == pytest.approx(0.5)
        assert intensities["C"] == pytest.approx(0.25)

    def test_normalize_all_zero(self):
        zones = [
            {"zone_id": "A", "revenue": 0},
            {"zone_id": "B", "revenue": 0},
        ]
        result = normalize_heatmap(zones)
        for r in result:
            assert r["intensity"] == 0.0


class TestLayoutRecommendations:
    """Tests for layout optimization recommendation engine."""

    def test_underperforming_zone_detected(self):
        zones = [
            {"zone_id": "A", "revenue_per_sqm": 500, "traffic": 300, "revenue": 50000},
            {"zone_id": "B", "revenue_per_sqm": 500, "traffic": 300, "revenue": 50000},
            {"zone_id": "C", "revenue_per_sqm": 100, "traffic": 300, "revenue": 10000},
        ]
        # avg revenue_per_sqm = (500+500+100)/3 = 366.67
        # Zone C at 100 < 366.67 * 0.5 = 183.33 => flagged
        recs = generate_recommendations(zones)
        assert len(recs) >= 1
        flagged_ids = [r["zone_id"] for r in recs]
        assert "C" in flagged_ids
        assert any(r["type"] == "underperforming" for r in recs if r["zone_id"] == "C")

    def test_high_traffic_low_revenue(self):
        zones = [
            {"zone_id": "A", "revenue_per_sqm": 500, "traffic": 200, "revenue": 50000},
            {"zone_id": "B", "revenue_per_sqm": 400, "traffic": 500, "revenue": 1000},
        ]
        # avg traffic = 350, avg revenue = 25500
        # Zone B: traffic 500 >= 350 and revenue 1000 < 25500 => conversion opportunity
        # Zone B revenue_per_sqm 400 vs avg 450 * 0.5 = 225, 400 >= 225 so not underperforming
        recs = generate_recommendations(zones)
        flagged_ids = [r["zone_id"] for r in recs]
        assert "B" in flagged_ids
        b_rec = [r for r in recs if r["zone_id"] == "B"][0]
        assert b_rec["type"] == "conversion_opportunity"

    def test_above_average_no_flag(self):
        zones = [
            {"zone_id": "A", "revenue_per_sqm": 600, "traffic": 400, "revenue": 60000},
            {"zone_id": "B", "revenue_per_sqm": 500, "traffic": 350, "revenue": 50000},
        ]
        # Both above 50% of avg; neither has high-traffic-low-revenue pattern
        recs = generate_recommendations(zones)
        assert len(recs) == 0

    def test_empty_zones(self):
        recs = generate_recommendations([])
        assert recs == []


class TestAggregationLogic:
    """Tests for category-to-zone sales aggregation."""

    def test_category_to_zone_mapping(self):
        zone_item_mapping = {
            "zone_A": ["beverages", "snacks"],
            "zone_B": ["dairy", "frozen"],
        }
        sales = [
            {"category": "beverages", "revenue": 3000},
            {"category": "beverages", "revenue": 2000},
            {"category": "dairy", "revenue": 1500},
        ]
        result = aggregate_sales_to_zones(sales, zone_item_mapping)
        assert result["zone_A"] == pytest.approx(5000.0)
        assert result["zone_B"] == pytest.approx(1500.0)

    def test_unmapped_category_excluded(self):
        zone_item_mapping = {
            "zone_A": ["beverages"],
        }
        sales = [
            {"category": "beverages", "revenue": 1000},
            {"category": "electronics", "revenue": 5000},
        ]
        result = aggregate_sales_to_zones(sales, zone_item_mapping)
        assert "zone_A" in result
        assert result["zone_A"] == pytest.approx(1000.0)
        # electronics has no matching zone, should not appear
        assert len(result) == 1


class TestCrossStoreComparison:
    """Tests for cross-store zone performance comparison."""

    def test_compare_same_zone_types(self):
        stores = [
            {
                "store_id": "S1",
                "zones": [
                    {"zone_type": "shelf", "revenue_per_sqm": 450},
                    {"zone_type": "endcap", "revenue_per_sqm": 800},
                ],
            },
            {
                "store_id": "S2",
                "zones": [
                    {"zone_type": "shelf", "revenue_per_sqm": 600},
                    {"zone_type": "endcap", "revenue_per_sqm": 700},
                ],
            },
        ]
        result = compare_stores_by_zone_type(stores, "shelf")
        assert len(result) == 2
        assert result[0]["store_id"] == "S2"
        assert result[0]["revenue_per_sqm"] == 600
        assert result[1]["store_id"] == "S1"
        assert result[1]["revenue_per_sqm"] == 450

    def test_ranking_order(self):
        stores = [
            {"store_id": "A", "zones": [{"zone_type": "shelf", "revenue_per_sqm": 300}]},
            {"store_id": "B", "zones": [{"zone_type": "shelf", "revenue_per_sqm": 500}]},
            {"store_id": "C", "zones": [{"zone_type": "shelf", "revenue_per_sqm": 400}]},
        ]
        # Descending order
        desc = compare_stores_by_zone_type(stores, "shelf", descending=True)
        assert [r["store_id"] for r in desc] == ["B", "C", "A"]

        # Ascending order
        asc = compare_stores_by_zone_type(stores, "shelf", descending=False)
        assert [r["store_id"] for r in asc] == ["A", "C", "B"]
