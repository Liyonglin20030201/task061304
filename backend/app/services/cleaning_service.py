import pandas as pd
import numpy as np
from typing import Tuple


def clean_dataframe(df: pd.DataFrame, data_type: str) -> Tuple[pd.DataFrame, int, int]:
    original_count = len(df)
    errors = 0
    duplicates = 0

    df = df.copy()
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    df = df.dropna(how="all")

    dup_count = df.duplicated().sum()
    df = df.drop_duplicates()
    duplicates += dup_count

    if data_type == "sales":
        df, err = _clean_sales(df)
        errors += err
    elif data_type == "inventory":
        df, err = _clean_inventory(df)
        errors += err
    elif data_type == "members":
        df, err = _clean_members(df)
        errors += err
    elif data_type == "traffic":
        df, err = _clean_traffic(df)
        errors += err
    elif data_type == "weather":
        df, err = _clean_weather(df)
        errors += err

    return df, errors, duplicates


def _clean_sales(df: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
    errors = 0
    required = ["store_id", "sale_date", "receipt_no", "item_id", "quantity", "unit_price", "total_amount"]
    for col in required:
        if col not in df.columns:
            return pd.DataFrame(), len(df)

    before = len(df)
    df = df.dropna(subset=required)
    errors += before - len(df)

    df["store_id"] = pd.to_numeric(df["store_id"], errors="coerce")
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
    df["unit_price"] = pd.to_numeric(df["unit_price"], errors="coerce")
    df["total_amount"] = pd.to_numeric(df["total_amount"], errors="coerce")

    invalid = df[["store_id", "quantity", "unit_price", "total_amount"]].isna().any(axis=1)
    errors += invalid.sum()
    df = df[~invalid]

    df = df[df["quantity"] > 0]
    df = df[df["unit_price"] >= 0]
    df = df[df["total_amount"] >= 0]

    df["sale_date"] = pd.to_datetime(df["sale_date"], errors="coerce").dt.date
    df = df.dropna(subset=["sale_date"])

    if "discount_amount" not in df.columns:
        df["discount_amount"] = 0
    df["discount_amount"] = pd.to_numeric(df["discount_amount"], errors="coerce").fillna(0)

    return df, errors


def _clean_inventory(df: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
    errors = 0
    required = ["store_id", "item_id", "quantity", "snapshot_date"]
    for col in required:
        if col not in df.columns:
            return pd.DataFrame(), len(df)

    before = len(df)
    df = df.dropna(subset=required)
    errors += before - len(df)

    df["store_id"] = pd.to_numeric(df["store_id"], errors="coerce")
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
    invalid = df[["store_id", "quantity"]].isna().any(axis=1)
    errors += invalid.sum()
    df = df[~invalid]

    df["snapshot_date"] = pd.to_datetime(df["snapshot_date"], errors="coerce").dt.date
    df = df.dropna(subset=["snapshot_date"])

    if "unit_cost" in df.columns:
        df["unit_cost"] = pd.to_numeric(df["unit_cost"], errors="coerce")
    if "total_value" not in df.columns and "unit_cost" in df.columns:
        df["total_value"] = df["quantity"] * df["unit_cost"]

    return df, errors


def _clean_members(df: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
    errors = 0
    required = ["member_no", "register_date"]
    for col in required:
        if col not in df.columns:
            return pd.DataFrame(), len(df)

    before = len(df)
    df = df.dropna(subset=required)
    errors += before - len(df)

    df["register_date"] = pd.to_datetime(df["register_date"], errors="coerce").dt.date
    df = df.dropna(subset=["register_date"])

    if "phone" in df.columns:
        df["phone"] = df["phone"].astype(str).str.replace(r"[^\d]", "", regex=True)
        df.loc[df["phone"].str.len() != 11, "phone"] = None

    return df, errors


def _clean_traffic(df: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
    errors = 0
    required = ["store_id", "traffic_date", "hour", "enter_count"]
    for col in required:
        if col not in df.columns:
            return pd.DataFrame(), len(df)

    before = len(df)
    df = df.dropna(subset=required)
    errors += before - len(df)

    df["store_id"] = pd.to_numeric(df["store_id"], errors="coerce")
    df["hour"] = pd.to_numeric(df["hour"], errors="coerce")
    df["enter_count"] = pd.to_numeric(df["enter_count"], errors="coerce")

    df = df[(df["hour"] >= 0) & (df["hour"] <= 23)]
    df = df[df["enter_count"] >= 0]

    df["traffic_date"] = pd.to_datetime(df["traffic_date"], errors="coerce").dt.date
    df = df.dropna(subset=["traffic_date"])

    return df, errors


def _clean_weather(df: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
    errors = 0
    required = ["city", "weather_date"]
    for col in required:
        if col not in df.columns:
            return pd.DataFrame(), len(df)

    before = len(df)
    df = df.dropna(subset=required)
    errors += before - len(df)

    df["weather_date"] = pd.to_datetime(df["weather_date"], errors="coerce").dt.date
    df = df.dropna(subset=["weather_date"])

    for col in ["temp_high", "temp_low", "humidity", "wind_speed", "precipitation"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "humidity" in df.columns:
        df.loc[df["humidity"] > 100, "humidity"] = 100
        df.loc[df["humidity"] < 0, "humidity"] = 0

    return df, errors
