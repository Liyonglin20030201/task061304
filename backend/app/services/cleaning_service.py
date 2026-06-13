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


def _interpolate_numeric(df: pd.DataFrame, columns: list, group_col: str = None) -> pd.DataFrame:
    """Fill missing numeric values using linear interpolation instead of dropping rows."""
    for col in columns:
        if col not in df.columns:
            continue
        if group_col and group_col in df.columns:
            df[col] = df.groupby(group_col)[col].transform(
                lambda s: s.interpolate(method="linear", limit_direction="both")
            )
        else:
            df[col] = df[col].interpolate(method="linear", limit_direction="both")
        # fallback: fill any remaining NaN with column median
        if df[col].isna().any():
            median_val = df[col].median()
            df[col] = df[col].fillna(median_val if pd.notna(median_val) else 0)
    return df


def _clean_sales(df: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
    errors = 0
    required = ["store_id", "sale_date", "receipt_no", "item_id", "quantity", "unit_price", "total_amount"]
    for col in required:
        if col not in df.columns:
            return pd.DataFrame(), len(df)

    # Only drop rows missing truly required business keys (non-interpolatable)
    key_cols = ["store_id", "sale_date", "receipt_no", "item_id"]
    before = len(df)
    df = df.dropna(subset=key_cols)
    errors += before - len(df)

    df["store_id"] = pd.to_numeric(df["store_id"], errors="coerce")
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
    df["unit_price"] = pd.to_numeric(df["unit_price"], errors="coerce")
    df["total_amount"] = pd.to_numeric(df["total_amount"], errors="coerce")

    # Interpolate missing numeric values instead of dropping
    df = _interpolate_numeric(df, ["quantity", "unit_price", "total_amount"], group_col="store_id")

    # Only drop rows where store_id is invalid (can't interpolate IDs)
    invalid_store = df["store_id"].isna()
    errors += invalid_store.sum()
    df = df[~invalid_store]

    # Filter obviously invalid data (negative qty/price)
    df = df[df["quantity"] > 0]
    df = df[df["unit_price"] >= 0]
    df = df[df["total_amount"] >= 0]

    df["sale_date"] = pd.to_datetime(df["sale_date"], errors="coerce").dt.date
    df = df.dropna(subset=["sale_date"])

    if "discount_amount" not in df.columns:
        df["discount_amount"] = 0
    df["discount_amount"] = pd.to_numeric(df["discount_amount"], errors="coerce").fillna(0)

    # Recalculate total_amount if it was interpolated and we have qty+price
    mask = (df["total_amount"] == 0) & (df["quantity"] > 0) & (df["unit_price"] > 0)
    df.loc[mask, "total_amount"] = df.loc[mask, "quantity"] * df.loc[mask, "unit_price"]

    return df, errors


def _clean_inventory(df: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
    errors = 0
    required = ["store_id", "item_id", "quantity", "snapshot_date"]
    for col in required:
        if col not in df.columns:
            return pd.DataFrame(), len(df)

    # Drop only rows missing business keys
    key_cols = ["store_id", "item_id", "snapshot_date"]
    before = len(df)
    df = df.dropna(subset=key_cols)
    errors += before - len(df)

    df["store_id"] = pd.to_numeric(df["store_id"], errors="coerce")
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")

    # Interpolate missing quantity values
    df = _interpolate_numeric(df, ["quantity"], group_col="item_id")

    invalid_store = df["store_id"].isna()
    errors += invalid_store.sum()
    df = df[~invalid_store]

    df["snapshot_date"] = pd.to_datetime(df["snapshot_date"], errors="coerce").dt.date
    df = df.dropna(subset=["snapshot_date"])

    if "unit_cost" in df.columns:
        df["unit_cost"] = pd.to_numeric(df["unit_cost"], errors="coerce")
        df = _interpolate_numeric(df, ["unit_cost"], group_col="item_id")
    if "total_value" not in df.columns and "unit_cost" in df.columns:
        df["total_value"] = df["quantity"] * df["unit_cost"]
    elif "total_value" in df.columns:
        df["total_value"] = pd.to_numeric(df["total_value"], errors="coerce")
        df = _interpolate_numeric(df, ["total_value"], group_col="item_id")

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

    # Drop only rows missing time-dimension keys
    key_cols = ["store_id", "traffic_date", "hour"]
    before = len(df)
    df = df.dropna(subset=key_cols)
    errors += before - len(df)

    df["store_id"] = pd.to_numeric(df["store_id"], errors="coerce")
    df["hour"] = pd.to_numeric(df["hour"], errors="coerce")
    df["enter_count"] = pd.to_numeric(df["enter_count"], errors="coerce")

    # Interpolate missing enter_count
    df = _interpolate_numeric(df, ["enter_count", "exit_count", "pass_by_count"], group_col="store_id")

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

    numeric_cols = ["temp_high", "temp_low", "humidity", "wind_speed", "precipitation"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Interpolate missing weather metrics instead of leaving them as NaN
    existing_numeric = [c for c in numeric_cols if c in df.columns]
    df = _interpolate_numeric(df, existing_numeric, group_col="city")

    if "humidity" in df.columns:
        df.loc[df["humidity"] > 100, "humidity"] = 100
        df.loc[df["humidity"] < 0, "humidity"] = 0

    return df, errors
