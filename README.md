# ArcGIS Feature Service Audit Tool (Modular)

Tracks editing activity and service metadata across **ArcGIS Enterprise** and **ArcGIS Online**, then writes results into a hosted **Audit Table**.
Designed for **large org-wide inventories** with optimized batching, caching, and parallel collection.

## What this tool captures

* Item + layer identifiers (portal, item id, sublayer id/name)
* Data and schema “last updated” timestamps
* Feature counts + delta from previous run (optional)
* Editor tracking values (Creator / Editor) **only when fields exist**
* Service URL + Item URL
* Optional: Sharing level + group sharing (if fields exist in audit table)
* Skips uploads for unchanged layers (configurable rule)

---

## Repository layout

### `main.py`

**Entry point.**

* Connects to AGOL + Enterprise (from `.env`)
* Validates audit table schema (detects optional fields)
* Loads previous snapshot / previous counts (for delta)
* Collects layer records from both portals (parallel)
* Filters unchanged layers (delta-only or date+delta)
* Transforms data for upload (epoch ms + NaN → None)
* Uploads to hosted audit table in batches

---

### `config_context.py`

Central configuration + run metadata.

* `Config` dataclass: workers, batch size, test mode, timezone, retention days
* `RunContext`: run id, run label, run timestamp (ms), local/utc time helpers

---

### `logger_utils.py`

Logging + housekeeping utilities.

* Tee logging (console + file)
* Log folder creation
* Cleanup old logs / exports by retention settings

---

### `time_utils.py`

Fast timestamp conversions (optimized + cached).

* `ms_to_datetime(ms)` cached conversion to local datetime
* `datetime_to_epoch(dt)` converts any datetime-like into epoch ms safely
* Fiscal year helpers (`get_fiscal_year`, cached variants)
* Month floor helper for reporting month grouping

---

### `fields_edit.py`

Editor tracking field detection + user lookup.

* `EditFieldDetector.detect(layer)`
  Detects actual editor tracking field names using:

  * `editFieldsInfo` if present
  * fallback scan of schema fields (`Creator`, `Editor`, `CreationDate`, `EditDate`, plus variants)
  * cached by `layer.url` to reduce repeated work
* `get_last_creator(layer)` / `get_last_editor(layer)`
  Returns most recent creator/editor **only if fields exist and values are present**
* `has_editor_tracking(layer)`
  Checks tracking availability using BOTH:

  * detected mapping (`EditFieldDetector`)
  * physical schema check (`Creator/CreationDate/Editor/EditDate`)

> No fallback to item owner (audit integrity preserved).

---

### `audit_table_io.py`

Audit table validation + previous-run retrieval + upload.

* `validate_audit_table(audit_table_url, gis)`

  * connects to hosted table
  * checks Create capability
  * detects optional fields like:

    * `sub_layer_id`, `sub_layer_name`
    * `item_url`, `service_url`
    * `delta_features`
    * `sharing`, `shared_groups` (if enabled in your schema)
* `get_last_run_snapshot(audit_table)`
  Loads last known record per (portal, item_id, sub_layer_id) for comparisons
* `get_previous_counts(audit_table, run_timestamp)`
  Builds lookup dict for delta calculation
* `upload_records(audit_table, records, batch_size)`
  Adds rows in batches with partial failure reporting

---

### `collector.py`

Core data collection engine.

* Searches feature services from each portal
* Filters out **AGOL View Services** (keeps only hosted source layers)
* Iterates through FeatureLayerCollection layers and builds one record per sublayer
* Extracts:

  * service URL, layer URL (optional)
  * item created/modified times
  * data/schema “last edit” info with fallbacks
  * feature counts + delta
  * creator/editor values **only when tracking exists**
* Parallelized with `ThreadPoolExecutor`

---

### `transform.py` (or `data_transform.py`)

Final transformation step before upload.

* Converts datetime columns → epoch milliseconds (UTC)
* Converts **NaN/inf → None** (required to avoid SQL Server float errors)
* Formats `report_month` (`YYYY-MM`)
* Builds item URLs if `item_url` exists in audit table
* Optional stats output (delta summary)

> This file is where you fixed the error:
> `Parameter ("@schema_updated"): value is not a valid instance of float`
> by forcing `None` instead of NaN.

---

### `filters.py` (optional)

Filtering logic for upload reduction.

Common modes:

* **Delta-only mode (recommended)**: upload only when `delta_features != 0` or item is new
* **Date + delta mode**: upload if any timestamps changed OR delta != 0

---

## Configuration

### `.env` (local only – DO NOT commit)

Example keys:

```bash
PORTAL_URL=https://www.arcgis.com
USERNAME=your_agol_username
PASSWORD=your_agol_password

PORTAL_URL1=https://your-enterprise-portal-url/portal
USERNAME1=your_enterprise_username
PASSWORD1=your_enterprise_password
```

---

## Audit table requirements

Your hosted Audit Table should include required fields such as:

* `portal`
* `item_id`
* `layer_name`
* `run_timestamp`
* `data_updated`
* `schema_updated`
* `total_features`
* etc.

Optional (auto-detected if present):

* `sub_layer_id`, `sub_layer_name`
* `item_url`
* `service_url`
* `delta_features`
* `sharing`
* `shared_groups`

---

## Run modes

* **TEST_MODE**: run only one service by item id
* **FIRST_RUN**: process all services and load initial snapshot
* **Incremental runs**: skip unchanged layers (delta-only recommended)

---

## Notes and limitations

* Editor tracking fields do not backfill old features automatically.
* Some layers may have tracking fields but still return null values until edited.
* Sharing/groups are item-level (service), not per-sublayer.

---

## Example output

* Logs saved under `./logs/`
* Optional export of skipped layers under `./audit_exports_unchanged_data/`

---
What it’s used for (practical use cases)

Typical uses include:

1) Governance / Inventory checks (one-off reports)

List all hosted services that are:

public

shared to org

shared to specific groups

Identify services that violate policy (e.g., public when they shouldn’t be)

2) Troubleshooting audit results

When the audit shows created_user / last_edited_user as NULL:

confirm whether tracking fields exist

confirm whether the fields are populated

verify whether the layer is a view or source

quickly inspect schema without running the full audit

3) Admin diagnostics for collaboration / content lifecycle

identify services in collaboration groups

identify items missing the collab tag

validate tag-based filtering works before an audit run

4) Targeted remediation / quality control

Instead of running changes org-wide, you can isolate:

only items in a group

only items updated in last X days

only items with missing schema properties
then validate safely.
