````md
# 🛰️ ArcGIS Audit Uploader (AGOL + ArcGIS Enterprise)

Audit **Feature Services + sublayers** across **ArcGIS Online** and **ArcGIS Enterprise**, then write a clean “snapshot” of key metadata (owner, edit dates, feature counts, authoritative flag, etc.) into a **hosted audit table** (FeatureServer table). :contentReference[oaicite:0]{index=0}

This is useful when you want:
- A single **inventory + health view** of services across portals
- Monthly / fiscal year reporting (FY) and “what changed” tracking
- Automated logging + exports for skipped/unchanged layers

---

## ✅ What this script audits

For each **Feature Service** (and each **sublayer** inside it), the script collects:

- Portal source (`ArcGIS Online` or `ArcGIS Enterprise`)
- Item title + Item ID
- Owner
- Created / updated timestamps (item + data + schema)
- Last edited user + created user (via editor tracking fields if available)
- Total feature count
- Authoritative flag (based on content status)
- Fiscal Year (FY) + report month
- Run metadata (run id, timestamp, label, timezone)

Optional fields are auto-detected from your audit table schema (if they exist), such as:
- `sub_layer_name`, `sub_layer_id`, `owner`, `item_url`, `delta_features` :contentReference[oaicite:1]{index=1}

---

## ⚙️ How it works (pipeline)

1. **Connect to both portals** using credentials from `.env` :contentReference[oaicite:2]{index=2}  
2. **Validate the hosted audit table** (must allow Create/edit) and detect optional fields :contentReference[oaicite:3]{index=3}  
3. **Collect all Feature Services** from each portal (parallel) and extract sublayer details :contentReference[oaicite:4]{index=4}  
   - AGOL: keeps only **hosted source layers** (excludes views)
   - AGOL: skips collaboration/reference services and “collab” tagged items
4. (Optional) **Compute delta feature counts** using previous run’s stored counts :contentReference[oaicite:5]{index=5}  
5. (Optional) If `FIRST_RUN = False`, **skip unchanged layers** and export them to CSV :contentReference[oaicite:6]{index=6}  
6. Transform/clean values for upload (dates → epoch ms, NaN → None, optional item URL building) :contentReference[oaicite:7]{index=7}  
7. Upload records to the audit table in **batches** (default 2000) :contentReference[oaicite:8]{index=8}  
8. Write a log file and auto-clean old logs/exports :contentReference[oaicite:9]{index=9}  

---

## 📦 Requirements

- Python 3.9+
- ArcGIS API for Python
- pandas, numpy
- python-dotenv
- pytz

Install (example):
```bash
pip install arcgis pandas numpy python-dotenv pytz
````

---

## 🔐 Create your `.env`

Create a file named `.env` in the same folder as `main.py`:

```env
# ArcGIS Online
PORTAL_URL=https://www.arcgis.com
USERNAME=your_agol_username
PASSWORD=your_agol_password

# ArcGIS Enterprise
PORTAL_URL1=https://your-enterprise-portal.domain.com/portal
USERNAME1=your_enterprise_username
PASSWORD1=your_enterprise_password
```

> Tip: use an admin/service account if you want to audit everything consistently.

---

## 🧾 Configure the run

Open `config_context.py` and adjust:

* `TEST_MODE` (True = single item only)
* `TEST_ITEM_ID` (item id used in test mode)
* `MAX_ITEMS`, `MAX_WORKERS`
* `BATCH_SIZE`
* `FIRST_RUN` (True uploads everything; False enables “skip unchanged” mode)
* Timezone defaults to `America/Chicago` 

---

## 🏃 Run the audit

### Option A — Run directly

```bash
python main.py
```

### Option B — Update the audit table URL in `main.py`

Set this to your hosted table layer (FeatureServer/0):

```python
AUDIT_TABLE_URL = "https://services.arcgis.com/.../FeatureServer/0"
```



---

## 🧠 Notes on AGOL filtering (important)

This script intentionally avoids “noise” in AGOL results:

* Skips **referenced** services (not true hosted services)
* Skips items tagged `collab` (useful for distributed collaboration environments)
* Keeps only **hosted source Feature Services** (not views)

This logic lives in `collector.py`. 

---

## 🏷️ Optional: auto-tag “collab” items in AGOL groups

If you maintain specific AGOL groups for collaboration items, the script includes a helper to tag items in those groups with `collab`. That helps the collector skip them automatically later. 

The tagging function is in `update_tags_groups_items.py` (called from `main.py`). 

---

## 📤 Output artifacts

### 1) Logs

A log file is created under:

```
/logs/audit_log_YYYYMMDD_HHMMSS.txt
```

Old logs auto-delete after 7 days. 

### 2) Exported “skipped unchanged layers” (when FIRST_RUN = False)

```
/audit_exports_unchanged_data/skipped_layers_YYYYMMDD_HHMMSS.csv
```

Old exports auto-delete after 7 days. 

### 3) Audit table updates

Records are uploaded in batches to your hosted audit table. 

---

## 🧪 Sample console output (example)

> Your numbers/titles will differ—this is the typical flow:

```text
🪵 Logging started → .../logs/audit_log_20260208_104455.txt

============================================================
🚀 Edit Audit Run: 2026-02-08 10:44 AM CST
🔹 Run ID: 7f5d4a3d-8dbb-4b9b-8f34-8c7d1b2a91c0
🔹 Mode: PRODUCTION (All Items)
============================================================

🧩 Connected: https://services.arcgis.com/.../FeatureServer/0
✅ Editing enabled.
📋 Optional fields: sub_layer_name=True, sub_layer_id=True, owner=True, item_url=True, delta_features=True

📥 Fetching previous feature counts for delta calculation...
   ✅ Found previous counts for 312 layers

🔄 Starting parallel data collection from both portals...

🔎 [ArcGIS Enterprise] Searching Feature Services...
✅ [ArcGIS Enterprise] Public Works - Assets: 6 sublayers (Δ: +12, +0, -3)
🏁 [ArcGIS Enterprise] Collected 420 records

🔎 [ArcGIS Online] Searching Feature Services...
🔎 [ArcGIS Online] Found 860 Feature Services → kept 510 hosted sources (views removed).
⏭️ [ArcGIS Online] Skipping collab-tagged item: Shared Hydrants
✅ [ArcGIS Online] Parks - Inspections: 2 sublayers (Δ: +5, +0)
🏁 [ArcGIS Online] Collected 380 records

📊 Transforming 800 records...
✅ Transformation complete

🚀 Uploading 800 records in batches of 2000...

🟢 Batch 1 (800 records, 1-800 of 800)...
   ✅ All 800 records uploaded

============================================================
🏁 AUDIT UPLOAD COMPLETE
============================================================
📅 Fiscal Year: FY26
⏰ Completed: 2026-02-08 10:46 AM CST
🔹 Mode: PRODUCTION
📊 Processed: 800
✅ Succeeded: 800
🔹 Run ID: 7f5d4a3d-8dbb-4b9b-8f34-8c7d1b2a91c0
============================================================
⏱️ Total Runtime: 1m 22s
```

---

## 🧩 Audit table schema (recommended)

Minimum required fields (must exist):

* `portal`
* `layer_name`
* `item_id`
* `FY`
* `last_edited_user`
* `created_user`
* `item_created`
* `item_updated`
* `data_updated`
* `schema_updated`
* `report_month`
* `total_features`
* `is_authoritative`
* `run_timestamp`
* `data_run_label`
* `edit_run_id`
* `time_zone`

Optional fields (script detects automatically if present):

* `sub_layer_name`, `sub_layer_id`, `owner`, `item_url`, `delta_features` 

---

## 🛠️ Troubleshooting

### “Editing not enabled for this table”

Your audit table must support “Create” edits. The validator checks capabilities and exits if Create is missing. 

### No records uploaded / no data collected

* Verify credentials in `.env`
* Confirm both portals are reachable
* Try `TEST_MODE=True` with a known `TEST_ITEM_ID` 

### Delta features always 0

* Ensure your audit table has `delta_features`
* Make sure it’s not the first run (previous records must exist for delta comparisons) 

---

## 📁 Project structure

* `main.py` — entry point (connect, collect, transform, upload, summary) 
* `collector.py` — searches items, collects sublayer metadata (parallelized) 
* `audit_table_io.py` — validate table, previous snapshot, batch upload 
* `transform_filter.py` — transforms dates, builds URLs, skip unchanged exports 
* `fields_edit.py` — detects editor tracking fields + extracts edit users/dates 
* `logging_utils.py` — log tee + cleanup old logs/exports 
* `time_utils.py` — timezone-safe timestamp helpers + FY logic 
* `update_tags_groups_items.py` — optional group-based tagging helper 

---

## 📌 License / Usage

Internal automation / ops tooling. Customize freely for your org’s audit table schema and reporting needs.

```
```
