# transform_filter.py
import os
from typing import Tuple
from config_context import CONFIG
from time_utils import datetime_to_epoch
from logging_utils import cleanup_old_files
import numpy as np
import pandas as pd

def _build_item_url(row: pd.Series) -> str:
    sub_layer = row.get("sub_layer_id", 0)

    if row["portal"] == "ArcGIS Online":
        return f"https://x.arcgis.com/home/item.html?id={row['item_id']}&sublayer={sub_layer}"

    return f"https://maps.x.com/portal/home/item.html?id={row['item_id']}&sublayer={sub_layer}"


def _print_delta_stats(df: pd.DataFrame, config) -> None:
    if not getattr(config, "delta_features", False) or "delta_features" not in df.columns:
        return

    deltas = df["delta_features"]
    total_delta = int(deltas.sum())
    increased = int((deltas > 0).sum())
    decreased = int((deltas < 0).sum())
    unchanged = int((deltas == 0).sum())

    print(
        f"   📈 Delta Summary: Total={total_delta:+d}, "
        f"Increased={increased}, Decreased={decreased}, Unchanged={unchanged}"
    )




def transform_dataframe(df: pd.DataFrame, config) -> pd.DataFrame:
    print(f"📊 Transforming {len(df)} records...")

    date_columns = ["item_created", "item_updated", "data_updated", "schema_updated"]

    for col in date_columns:
        if col in df.columns:
            # Convert to datetime safely
            dt = pd.to_datetime(df[col], errors="coerce", utc=True)

            # Convert to epoch ms (int64) but keep nulls as None
            epoch_ms = (dt.view("int64") // 1_000_000).astype("float64")
            epoch_ms = epoch_ms.where(dt.notna(), np.nan)

            # IMPORTANT: SQL Server / ArcGIS hates NaN -> convert NaN to None
            df[col] = epoch_ms.replace([np.nan, np.inf, -np.inf], None)

    # report_month string
    if "report_month" in df.columns:
        df["report_month"] = pd.to_datetime(df["report_month"], errors="coerce").dt.strftime("%Y-%m")

    # item_url if present
    if getattr(config, "item_url", False):
        df["item_url"] = df.apply(_build_item_url, axis=1)

    # ✅ FINAL SAFETY: replace any remaining NaN anywhere in df
    df = df.replace([np.nan, np.inf, -np.inf], None)

    print(f"✅ Transformation complete\n")
    return df





def filter_unchanged_layers(
    df: pd.DataFrame,
    prev_snapshot: pd.DataFrame,
    run_context
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    ONLY net feature change mode (ignore dates):
      - Upload if delta_features != 0
      - Upload if layer is NEW (not found in previous snapshot)
      - Skip if delta_features == 0 AND layer existed before
    Returns: (df_to_upload, skipped_layers)
    """
    if prev_snapshot.empty:
        # First run: treat everything as new -> upload all
        return df, pd.DataFrame()

    print("🔍 Filtering layers using ONLY net feature change (delta_features) ...")

    compare_cols = ["portal", "item_id", "sub_layer_id"]

    # --- Normalize keys ---
    df["portal"] = df["portal"].astype(str).str.strip()
    prev_snapshot["portal"] = prev_snapshot["portal"].astype(str).str.strip()

    df["item_id"] = df["item_id"].astype(str).str.strip()
    prev_snapshot["item_id"] = prev_snapshot["item_id"].astype(str).str.strip()

    # sub_layer_id normalize to int then str (prevents NULL vs 0 mismatch)
    df["sub_layer_id"] = pd.to_numeric(df.get("sub_layer_id", 0), errors="coerce").fillna(0).astype(int)
    prev_snapshot["sub_layer_id"] = pd.to_numeric(prev_snapshot.get("sub_layer_id", 0), errors="coerce").fillna(0).astype(int)

    # --- Mark whether layer existed before ---
    prev_keys = prev_snapshot[compare_cols].drop_duplicates().copy()
    prev_keys["has_prev"] = 1

    df_merged = df.merge(prev_keys, how="left", on=compare_cols)
    df_merged["has_prev"] = df_merged["has_prev"].fillna(0).astype(int)

    # --- delta_features required ---
    if "delta_features" not in df_merged.columns:
        print("❌ delta_features column not found in current df. Cannot do net-change filtering.")
        print("   Add 'delta_features' field to audit table and ensure collector populates it.")
        return df, pd.DataFrame()

    df_merged["delta_features"] = pd.to_numeric(
        df_merged["delta_features"], errors="coerce"
    ).fillna(0).astype(int)

    # --- Skip rule: existed before AND delta == 0 ---
    unchanged_mask = (df_merged["has_prev"] == 1) & (df_merged["delta_features"] == 0)

    skipped_layers = df_merged[unchanged_mask].copy()
    df_to_upload = df_merged[~unchanged_mask].copy()

    # Remove helper col
    df_to_upload.drop(columns=["has_prev"], inplace=True, errors="ignore")
    skipped_layers.drop(columns=["has_prev"], inplace=True, errors="ignore")

    print(f"✅ {len(skipped_layers)} unchanged (delta=0) layers skipped from upload")
    print(f"📌 {len(df_to_upload)} layers will be uploaded (net change or new)\n")

    return df_to_upload, skipped_layers



def export_skipped_layers(skipped_layers: pd.DataFrame, run_context) -> None:
    if skipped_layers.empty:
        print("ℹ️ No unchanged layers to export.\n")
        return

    export_dir = os.path.join(os.getcwd(), "audit_exports_unchanged_data")
    os.makedirs(export_dir, exist_ok=True)

    try:
        cleanup_old_files(
            export_dir,
            days_to_keep=CONFIG.EXPORT_RETENTION_DAYS,
            extensions=(".csv",),
        )
    except Exception as e:
        print(f"⚠️ Failed to clean old exports: {e}")

    for col in skipped_layers.select_dtypes(include=["datetimetz"]).columns:
        skipped_layers[col] = skipped_layers[col].dt.tz_localize(None)

    csv_name = f"skipped_layers_{run_context.local_now.strftime('%Y%m%d_%H%M%S')}.csv"
    csv_path = os.path.join(export_dir, csv_name)

    skipped_layers.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"📂 Skipped layers exported → {csv_path}\n")
