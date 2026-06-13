import pytest
import pandas as pd
import numpy as np
from app.services.cleaning_service import clean_dataframe


class TestSalesCleaning:
    def test_valid_sales_data(self):
        df = pd.DataFrame({
            "store_id": [1, 1, 2],
            "sale_date": ["2024-01-01", "2024-01-02", "2024-01-01"],
            "receipt_no": ["R001", "R002", "R003"],
            "item_id": ["A001", "A002", "A001"],
            "quantity": [2, 1, 3],
            "unit_price": [10.0, 20.0, 15.0],
            "total_amount": [20.0, 20.0, 45.0],
        })
        cleaned, errors, dupes = clean_dataframe(df, "sales")
        assert len(cleaned) == 3
        assert errors == 0
        assert dupes == 0

    def test_removes_duplicates(self):
        df = pd.DataFrame({
            "store_id": [1, 1],
            "sale_date": ["2024-01-01", "2024-01-01"],
            "receipt_no": ["R001", "R001"],
            "item_id": ["A001", "A001"],
            "quantity": [2, 2],
            "unit_price": [10.0, 10.0],
            "total_amount": [20.0, 20.0],
        })
        cleaned, errors, dupes = clean_dataframe(df, "sales")
        assert len(cleaned) == 1
        assert dupes == 1

    def test_handles_dirty_data(self):
        df = pd.DataFrame({
            "store_id": [1, "invalid", 2],
            "sale_date": ["2024-01-01", "not-a-date", "2024-01-03"],
            "receipt_no": ["R001", "R002", "R003"],
            "item_id": ["A001", "A002", "A003"],
            "quantity": [2, -1, 3],
            "unit_price": [10.0, 20.0, 15.0],
            "total_amount": [20.0, 20.0, 45.0],
        })
        cleaned, errors, dupes = clean_dataframe(df, "sales")
        assert len(cleaned) <= 2

    def test_missing_required_columns(self):
        df = pd.DataFrame({"store_id": [1], "sale_date": ["2024-01-01"]})
        cleaned, errors, dupes = clean_dataframe(df, "sales")
        assert len(cleaned) == 0

    def test_negative_quantity_filtered(self):
        df = pd.DataFrame({
            "store_id": [1],
            "sale_date": ["2024-01-01"],
            "receipt_no": ["R001"],
            "item_id": ["A001"],
            "quantity": [-5],
            "unit_price": [10.0],
            "total_amount": [50.0],
        })
        cleaned, errors, dupes = clean_dataframe(df, "sales")
        assert len(cleaned) == 0


class TestTrafficCleaning:
    def test_valid_traffic(self):
        df = pd.DataFrame({
            "store_id": [1, 1],
            "traffic_date": ["2024-01-01", "2024-01-01"],
            "hour": [9, 10],
            "enter_count": [50, 80],
        })
        cleaned, errors, dupes = clean_dataframe(df, "traffic")
        assert len(cleaned) == 2

    def test_invalid_hour_filtered(self):
        df = pd.DataFrame({
            "store_id": [1, 1],
            "traffic_date": ["2024-01-01", "2024-01-01"],
            "hour": [25, 10],
            "enter_count": [50, 80],
        })
        cleaned, errors, dupes = clean_dataframe(df, "traffic")
        assert len(cleaned) == 1


class TestWeatherCleaning:
    def test_humidity_clamped(self):
        df = pd.DataFrame({
            "city": ["上海"],
            "weather_date": ["2024-01-01"],
            "humidity": [150.0],
        })
        cleaned, errors, dupes = clean_dataframe(df, "weather")
        assert cleaned.iloc[0]["humidity"] == 100


class TestInterpolation:
    def test_missing_quantity_interpolated(self):
        df = pd.DataFrame({
            "store_id": [1, 1, 1],
            "sale_date": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "receipt_no": ["R001", "R002", "R003"],
            "item_id": ["A001", "A002", "A003"],
            "quantity": [2, None, 4],
            "unit_price": [10.0, 20.0, 15.0],
            "total_amount": [20.0, None, 60.0],
        })
        cleaned, errors, dupes = clean_dataframe(df, "sales")
        # Row with missing quantity should be interpolated (2+4)/2=3, not dropped
        assert len(cleaned) == 3
        assert cleaned.iloc[1]["quantity"] == 3.0

    def test_missing_weather_interpolated(self):
        df = pd.DataFrame({
            "city": ["上海", "上海", "上海"],
            "weather_date": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "temp_high": [10.0, None, 14.0],
            "humidity": [60.0, None, 80.0],
        })
        cleaned, errors, dupes = clean_dataframe(df, "weather")
        assert len(cleaned) == 3
        assert cleaned.iloc[1]["temp_high"] == 12.0
        assert cleaned.iloc[1]["humidity"] == 70.0

    def test_missing_traffic_interpolated(self):
        df = pd.DataFrame({
            "store_id": [1, 1, 1],
            "traffic_date": ["2024-01-01", "2024-01-01", "2024-01-01"],
            "hour": [9, 10, 11],
            "enter_count": [50, None, 70],
        })
        cleaned, errors, dupes = clean_dataframe(df, "traffic")
        assert len(cleaned) == 3
        assert cleaned.iloc[1]["enter_count"] == 60.0
