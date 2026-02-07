# main.py
import os
import sys
import time
import traceback
import numpy as np
import urllib3
import pandas as pd  # if needed elsewhere
from arcgis.gis import GIS
from dotenv import load_dotenv

from config_context import CONFIG, RunContext
from logging_utils import setup_logging
from audit_table_io import (
    validate_audit_table,
    get_previous_counts,
    get_last_run_snapshot,
    upload_records,
)
from collector import *
from transform_filter import (
    transform_dataframe,
    filter_unchanged_layers,
    export_skipped_layers,
)

from update_tags_groups_items import *
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def print_summary(run_context: RunContext, success_count: int, total_records: int):
    from time_utils import get_fiscal_year

    print(f"{'='*60}")
    print(f"🏁 AUDIT UPLOAD COMPLETE")
    print(f"{'='*60}")
    print(f"📅 Fiscal Year: {get_fiscal_year(run_context.local_now)}")
    print(f"⏰ Completed: {run_context.local_now.strftime('%Y-%m-%d %I:%M %p %Z')}")
    print(f"🔹 Mode: {'TEST' if CONFIG.TEST_MODE else 'PRODUCTION'}")
    print(f"📊 Processed: {total_records}")
    print(f"✅ Succeeded: {success_count}")

    if success_count < total_records:
        print(f"❌ Failed: {total_records - success_count}")

    print(f"🔹 Run ID: {run_context.run_id}")
    print(f"{'='*60}")


def main(gis_ent, gis_agol, audit_table_url: str):
    start_time = time.time()

    setup_logging()
    run_context = RunContext()
    run_context.print_header()

    try:
        audit_table, config = validate_audit_table(audit_table_url, gis_agol)

        prev_counts = {}
        if config.delta_features:
            prev_counts = get_previous_counts(audit_table, run_context.run_timestamp)

        print("🔄 Starting parallel data collection from both portals...\n")

        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=2) as executor:
            future_ent = executor.submit(
                collect_all_items, gis_ent, "ArcGIS Enterprise", config, prev_counts, run_context
            )
            future_agol = executor.submit(
                collect_all_items, gis_agol, "ArcGIS Online", config, prev_counts, run_context
            )

            rows_ent = future_ent.result()
            rows_agol = future_agol.result()

        all_rows = rows_ent + rows_agol

        if not all_rows:
            print("⚠️ No data collected.")
            return

        df = pd.DataFrame(all_rows)

        if not CONFIG.FIRST_RUN:
            prev_snapshot = get_last_run_snapshot(audit_table)
            df, skipped_layers = filter_unchanged_layers(df, prev_snapshot, run_context)
            export_skipped_layers(skipped_layers, run_context)

        df = transform_dataframe(df, config)
        df = df.replace([np.nan, np.inf, -np.inf], None)

        records = df.to_dict("records")
        success_count, total_records = upload_records(audit_table, records)

        end_time = time.time()
        elapsed = end_time - start_time
        minutes, seconds = divmod(elapsed, 60)

        print_summary(run_context, success_count, total_records)
        print(f"⏱️ Total Runtime: {int(minutes)}m {int(seconds)}s\n")

    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        traceback.print_exc()
        raise

    finally:
        if hasattr(sys.stdout, 'close'):
            sys.stdout.close()


if __name__ == "__main__":
    # Load .env from the script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(script_dir, ".env")
    load_dotenv(dotenv_path=env_path, override=True)

    print(f"🔍 Loaded .env from: {env_path}")
    print("DEBUG → AGOL_USERNAME:", os.getenv("USERNAME"))
    print("DEBUG → AGOL_PASSWORD present:", bool(os.getenv("PASSWORD")))

    gis_agol = GIS(
        os.getenv("PORTAL_URL"),
        os.getenv("USERNAME"),
        os.getenv("PASSWORD"),
        verify_cert=True,
    )
    gis_ent = GIS(
        os.getenv("PORTAL_URL1"),
        os.getenv("USERNAME1"),
        os.getenv("PASSWORD1"),
        verify_cert=True,
    )
    print("✅ Connected to both AGOL and Enterprise.")
    
    
    
    
    RAW_GROUP_IDS = """
8a422fc62b134b7182e57ff3c78f5971, 4d168b55c84d4f1abc8797ffbfec5323, aa33558d2e3247ef9e341ac45ee091d8
"""

    tag_items_in_groups_from_raw(gis_agol, RAW_GROUP_IDS)

    AUDIT_TABLE_URL = (
        "https://services.arcgis.com/0H6bhghgh/arcgis/rest/services/"
        "GIS_Audit_Table_Final/FeatureServer/0"
    )
# --- Step 1: run auditing pipeline as usual ---

    main(gis_ent, gis_agol, AUDIT_TABLE_URL)
