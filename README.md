# 🛰️ ArcGIS Audit Script (AGOL + ArcGIS Enterprise)

This repository contains a **Python-based auditing automation** for **ArcGIS Online (AGOL)** and **ArcGIS Enterprise**.
It scans **Feature Services and their sublayers**, captures key metadata and statistics, and writes a clean audit snapshot into a **hosted audit table** (FeatureServer table).

Designed for **GIS administrators, data governance teams, and enterprise reporting**.

---

## 🎯 What this script does

For every **Feature Service** and **each sublayer**, the script audits and records:

* Portal source (AGOL or Enterprise)
* Item title and Item ID
* Sublayer name and sublayer ID
* Owner
* Item URL
* Feature count
* Change in feature count since last run (delta)
* Created, updated, schema-updated timestamps
* Last edited user and created user (editor tracking)
* Authoritative status
* Fiscal Year (FY) and report month
* Run metadata (run ID, timestamp, timezone)

All results are **written to a hosted audit table** for dashboards, QA/QC, or compliance reporting.

---

## 🧠 Why this is useful

* 📋 Centralized inventory of GIS services
* 🔍 Detect silent changes in production layers
* 📊 Feed ArcGIS Dashboards or BI tools
* 🧾 Support annual, quarterly, or FY reporting
* ⚙️ Reduce manual portal audits

---

## ⚙️ How it works (high level)

1. Connects to **ArcGIS Online** and **ArcGIS Enterprise**
2. Validates the audit table (must allow Create)
3. Collects all Feature Services and their sublayers
4. Filters out:

   * Feature views
   * Referenced services
   * Collaboration-tagged items (`collab`)
5. Compares feature counts with the previous run
6. Uploads new audit records in batches
7. Logs everything and exports skipped (unchanged) layers

---

## 📦 Requirements

* Python 3.9+
* ArcGIS API for Python
* pandas
* numpy
* python-dotenv
* pytz

---

## 🔐 Environment setup (`.env`)

Create a `.env` file in the project root:

```
# ArcGIS Online
PORTAL_URL=https://www.arcgis.com
USERNAME=your_agol_username
PASSWORD=your_agol_password

# ArcGIS Enterprise
PORTAL_URL1=https://your-enterprise-portal.domain.com/portal
USERNAME1=your_enterprise_username
PASSWORD1=your_enterprise_password
```

> 💡 Use an admin or service account for full visibility.

---

## 🏃 How to run

1. Update the **audit table URL** in `main.py`
2. (Optional) Configure run behavior in `config_context.py`
3. Run:

```
python main.py
```

---

## 🧪 Sample audit table output (dummy data)

Below is an example of what gets written to the **audit FeatureServer table**.

| portal     | layer_name          | sub_layer_name | sub_layer_id | owner      | item_id  | item_url                                                                                                     | total_features | delta_features | is_authoritative | FY   | report_month |
| ---------- | ------------------- | -------------- | ------------ | ---------- | -------- | ------------------------------------------------------------------------------------------------------------ | -------------- | -------------- | ---------------- | ---- | ------------ |
| AGOL       | Water Utilities     | Hydrants       | 0            | gis_admin  | a1b2c3d4 | [https://services.arcgis.com/xxx/FeatureServer/0](https://services.arcgis.com/xxx/FeatureServer/0)           | 2,415          | +32            | Yes              | FY26 | Feb          |
| AGOL       | Water Utilities     | Valves         | 1            | gis_admin  | a1b2c3d4 | [https://services.arcgis.com/xxx/FeatureServer/1](https://services.arcgis.com/xxx/FeatureServer/1)           | 1,108          | 0              | Yes              | FY26 | Feb          |
| Enterprise | Public Works Assets | Street Signs   | 2            | pw_editor  | z9y8x7w6 | [https://portal.domain.com/server/rest/services/.../2](https://portal.domain.com/server/rest/services/.../2) | 18,450         | -12            | No               | FY26 | Feb          |
| Enterprise | Code Enforcement    | Open Cases     | 0            | code_admin | q4r5t6u7 | [https://portal.domain.com/server/rest/services/.../0](https://portal.domain.com/server/rest/services/.../0) | 3,902          | +145           | Yes              | FY26 | Feb          |

**Notes**

* `delta_features` shows change since the previous audit run
* `0` means no change
* Negative values indicate deletions or cleanup
* Values are auto-calculated if `delta_features` exists in the schema

---

## 📤 Generated outputs

### 🪵 Logs

Stored in `/logs/`
Automatically cleaned after 7 days.

### 📄 Skipped layers export

If `FIRST_RUN = False`, unchanged layers are exported to CSV:

```
/audit_exports_unchanged_data/skipped_layers_YYYYMMDD_HHMMSS.csv
```

---

## 📁 Project structure

* `main.py` – Entry point and orchestration
* `collector.py` – Searches portals and collects sublayer data
* `audit_table_io.py` – Validates audit table and uploads records
* `transform_filter.py` – Data cleanup, delta logic, exports
* `fields_edit.py` – Editor tracking field detection
* `logging_utils.py` – Logging and cleanup
* `time_utils.py` – Fiscal year and timezone handling
* `update_tags_groups_items.py` – Optional helper for tagging collaboration items

---

## 🛠️ Common issues

**No records uploaded**

* Check credentials in `.env`
* Ensure audit table allows Create
* Try `TEST_MODE = True` with a known item ID

**Delta always zero**

* Confirm previous audit data exists
* Ensure `delta_features` field exists in the table

---

## 📌 Intended use

Enterprise GIS operations, internal audits, governance automation, and production monitoring.

Feel free to adapt the schema or extend it with dashboards and alerts.

---

