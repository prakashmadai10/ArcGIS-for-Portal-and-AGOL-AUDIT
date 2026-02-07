# audit_table_io.py
from dataclasses import dataclass
from typing import Tuple, Dict, List

import pandas as pd
from arcgis.features import FeatureLayer

from config_context import CONFIG
from logging_utils import cleanup_old_files


@dataclass
class AuditTableConfig:
    """Configuration for audit table optional fields."""
    sub_layer_name: bool = False
    sub_layer_id: bool = False
    owner: bool = False
    item_url: bool = False
    delta_features: bool = False

    def __str__(self) -> str:
        return ", ".join(f'{k}={v}' for k, v in self.__dict__.items())


def validate_audit_table(audit_table_url: str, gis_obj) -> Tuple[FeatureLayer, AuditTableConfig]:
    """Validate audit table and detect available optional fields."""
    try:
        audit_table = FeatureLayer(audit_table_url, gis=gis_obj)
        capabilities = getattr(audit_table.properties, "capabilities", "") or ""

        print(f"🧩 Connected: {audit_table.url}")

        if "Create" not in capabilities:
            print("❌ Editing not enabled for this table.")
            raise SystemExit(1)

        print("✅ Editing enabled.")

        field_names = {f["name"].lower() for f in audit_table.properties.fields}
        config = AuditTableConfig(
            sub_layer_name="sub_layer_name" in field_names,
            sub_layer_id="sub_layer_id" in field_names,
            owner="owner" in field_names,
            item_url="item_url" in field_names,
            delta_features="delta_features" in field_names,
                    )

        print(f"📋 Optional fields: {config}\n")
        return audit_table, config

    except Exception as e:
        print(f"❌ Unable to access hosted table: {e}")
        raise SystemExit(1)


def get_previous_counts(audit_table: FeatureLayer, run_timestamp: int) -> Dict:
    """
    Fetch previous run's feature counts for delta calculation.
    Returns dict: (portal, item_id, sub_layer_id) -> total_features
    """
    print("📥 Fetching previous feature counts for delta calculation...")

    try:
        result = audit_table.query(
            where="1=1",
            out_fields="portal,item_id,sub_layer_id,total_features,run_timestamp",
            return_geometry=False,
        )

        if not result.features:
            print("   ℹ️ No previous data found - this appears to be first run\n")
            return {}

        df = pd.DataFrame([f.attributes for f in result.features])
        df = df[df["run_timestamp"] < run_timestamp]

        if df.empty:
            print("   ℹ️ No previous data found - this appears to be first run\n")
            return {}

        df = df.sort_values("run_timestamp", ascending=False)
        df_latest = df.drop_duplicates(
            subset=["portal", "item_id", "sub_layer_id"], keep="first"
        )

        df_latest["sub_layer_id"] = df_latest["sub_layer_id"].fillna(0).astype(int)
        prev_counts = {
            (str(row["portal"]), str(row["item_id"]), int(row["sub_layer_id"])): int(row["total_features"])
            for _, row in df_latest.iterrows()
        }

        print(f"   ✅ Found previous counts for {len(prev_counts)} layers\n")
        return prev_counts

    except Exception as e:
        print(f"   ⚠️ Error fetching previous counts: {e}")
        print("   ℹ️ Treating as first run\n")
        return {}


def get_last_run_snapshot(audit_table: FeatureLayer) -> pd.DataFrame:
    """
    Fetch the latest known record per layer (portal, item_id, sub_layer_id).
    """
    print("📥 Fetching latest record snapshot for comparison...")

    out_fields = [
        "portal",
        "item_id",
        "sub_layer_id",
        "item_created",
        "item_updated",
        "data_updated",
        "schema_updated",
        "run_timestamp",
    ]
    out_fields_str = ",".join(out_fields)

    try:
        result = audit_table.query(
            where="1=1",
            out_fields=out_fields_str,
            return_geometry=False,
        )

        if not result.features:
            print("   ℹ️ No prior audit records found.")
            return pd.DataFrame()

        df = pd.DataFrame([f.attributes for f in result.features])
        df_latest = (
            df.sort_values("run_timestamp", ascending=False)
              .drop_duplicates(subset=["portal", "item_id", "sub_layer_id"], keep="first")
        )

        print(f"   ✅ Loaded {len(df_latest)} most recent records (latest per layer)\n")
        return df_latest

    except Exception as e:
        print(f"   ⚠️ Could not fetch previous snapshot: {e}")
        return pd.DataFrame()


def upload_records(audit_table: FeatureLayer, records: List[Dict]) -> tuple[int, int]:
    """Upload records in batches."""
    total_records = len(records)
    success_count = 0

    print(f"🚀 Uploading {total_records} records in batches of {CONFIG.BATCH_SIZE}...\n")

    for batch_num, i in enumerate(range(0, total_records, CONFIG.BATCH_SIZE), start=1):
        batch = records[i:i + CONFIG.BATCH_SIZE]
        batch_end = min(i + len(batch), total_records)

        print(f"🟢 Batch {batch_num} ({len(batch)} records, {i+1}-{batch_end} of {total_records})...")

        try:
            adds = [{"attributes": r} for r in batch]
            result = audit_table.edit_features(adds=adds)

            if "addResults" in result:
                batch_success = sum(1 for r in result["addResults"] if r.get("success"))
                success_count += batch_success

                if batch_success == len(batch):
                    print(f"   ✅ All {batch_success} records uploaded\n")
                else:
                    failed = len(batch) - batch_success
                    print(f"   ⚠️ Partial success: {batch_success} succeeded, {failed} failed")

                    for r in result["addResults"]:
                        if not r.get("success"):
                            error_msg = r.get('error', {}).get('description', 'Unknown')
                            print(f"      Error: {error_msg}\n")
                            break
            else:
                print(f"   ⚠️ Unexpected result format\n")

        except Exception as e:
            print(f"   ❌ Error: {e}\n")

    return success_count, total_records
