# collector.py
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional

from arcgis.features import FeatureLayer, FeatureLayerCollection

from config_context import CONFIG, RunContext
from time_utils import ms_to_datetime, get_fiscal_year, month_floor
from fields_edit import EditFieldDetector, get_last_editor, get_last_creator, extract_edit_dates
from audit_table_io import AuditTableConfig

# collector.py
from urllib.parse import urlparse


def _is_agol_hosted_service_url(service_url: str) -> bool:
    """
    Returns True if the service URL is a true AGOL-hosted service
    (services.arcgis.com).
    """
    if not service_url:
        return False

    host = (urlparse(service_url).netloc or "").lower()
    return host.endswith("services.arcgis.com")


def _should_skip_agol_referenced_service(service_url: str) -> bool:
    """
    Returns True if the AGOL item is a reference to Enterprise / ArcGIS Server
    rather than a hosted AGOL service.
    """
    return bool(service_url) and not _is_agol_hosted_service_url(service_url)

def _has_tag(item, tag: str) -> bool:
    tags = getattr(item, "tags", None) or []
    return any(t.strip().lower() == tag.lower() for t in tags)

def is_hosted_source_feature_service(item) -> bool:
    """
    True only for AGOL hosted Feature Layer (source), not views.
    """
    kws = set(item.typeKeywords or [])
    return ("Hosted Service" in kws) and ("View Service" not in kws)


class LayerCollector:
    """Collects layer information from items with optimizations."""

    def __init__(self, gis_obj, portal_name: str, config: AuditTableConfig,
                 prev_counts: Dict, run_context: RunContext):
        self.gis = gis_obj
        self.portal_name = portal_name
        self.config = config
        self.prev_counts = prev_counts
        self.context = run_context
        self.is_enterprise = "arcgis.com" not in (gis_obj.url or "").lower()

    def collect_from_item(self, item) -> List[Dict]:
        records: List[Dict] = []
        try:
            flc = FeatureLayerCollection.fromitem(item)
            service_props = getattr(flc, "properties", {})
            owner_name = getattr(item, "owner", "Unknown")

            # ✅ Service URL (FeatureServer root for the item)
            # This is the value you want in the table
            service_url = getattr(flc, "url", None)
            
            # ✅ Skip AGOL reference layers (distributed collaboration, references, etc.)
            if self.portal_name == "ArcGIS Online" and _should_skip_agol_referenced_service(service_url):
                print(f"⏭️ [ArcGIS Online] Skipping referenced service: {item.title}")
                return []

            # ✅ Skip AGOL collab-tagged items
            if self.portal_name == "ArcGIS Online" and _has_tag(item, "collab"):
                print(f"⏭️ [ArcGIS Online] Skipping collab-tagged item: {item.title}")
                return []
            
            # collector.py inside LayerCollector.collect_from_item()
            if self.portal_name == "ArcGIS Online":
                kws = set(item.typeKeywords or [])
                if "Hosted Service" not in kws or "View Service" in kws:
                    return []

            
            content_status = (getattr(item, "content_status", "") or "").lower()
            is_authoritative = 1 if "authoritative" in content_status else 0

            item_created_dt = ms_to_datetime(getattr(item, "created", None))
            item_updated_dt = self._get_item_updated_date(item, service_props)

            layers = getattr(flc, "layers", None) or []

            timezone_flag = "CST" if self.is_enterprise else "AGOL_LOCAL"

            for layer in layers:
                record = self._collect_layer_record(
                    layer=layer,
                    item=item,
                    owner_name=owner_name,
                    is_authoritative=is_authoritative,
                    item_created_dt=item_created_dt,
                    item_updated_dt=item_updated_dt,
                    service_props=service_props,
                    timezone_flag=timezone_flag,
                    service_url=service_url,   # ✅ NEW
                )
                if record:
                    records.append(record)

        except Exception:
            # keep collector resilient
            pass

        return records

    def _get_item_updated_date(self, item, service_props):
        svc_last_edit = getattr(service_props, "serviceLastEditDate", None)

        if not svc_last_edit and hasattr(service_props, "editingInfo"):
            try:
                svc_last_edit = service_props.editingInfo.get("dataLastEditDate")
            except Exception:
                pass

        return (
            ms_to_datetime(svc_last_edit)
            or ms_to_datetime(getattr(item, "modified", None))
            or self.context.local_now
        )

    def _collect_layer_record(
        self,
        layer: FeatureLayer,
        item,
        owner_name: str,
        is_authoritative: int,
        item_created_dt,
        item_updated_dt,
        service_props,
        timezone_flag: str,
        service_url: Optional[str],  # ✅ NEW
    ) -> Optional[Dict]:
        props = layer.properties
        layer_id = getattr(props, "id", 0)

        # Edit dates
        data_ms, schema_ms = extract_edit_dates(props, service_props)
        data_updated_dt = ms_to_datetime(data_ms)
        schema_updated_dt = ms_to_datetime(schema_ms) 

        # Fallback using EditDate field (Enterprise sometimes)
        if not data_updated_dt:
            fields = EditFieldDetector.detect(layer)
            edit_date_field = fields.get("editDateField")

            if edit_date_field:
                try:
                    query_result = layer.query(
                        where=f"{edit_date_field} IS NOT NULL",
                        out_fields=edit_date_field,
                        order_by_fields=f"{edit_date_field} DESC",
                        result_record_count=1,
                        return_geometry=False,
                    )
                    if query_result.features:
                        latest_edit_val = query_result.features[0].get_value(edit_date_field)
                        data_updated_dt = ms_to_datetime(latest_edit_val)
                        print(f"🕓 Using fallback EditDate from {layer.properties.name}: {data_updated_dt}")
                except Exception as e:
                    print(f"⚠️ Could not fetch EditDate fallback for {layer.properties.name}: {e}")

        if not data_updated_dt:
            data_updated_dt = item_updated_dt

        fiscal_year = get_fiscal_year(data_updated_dt)
        report_month_dt = month_floor(data_updated_dt)

        # Feature count + delta
        current_features = int(layer.query(where="1=1", return_count_only=True))
        delta_features = self._calculate_delta(layer_id, item.id, current_features)

        # Users
        last_edited_user = get_last_editor(layer)
        created_user1 = get_last_creator(layer)

        record: Dict = {
            "portal": self.portal_name,
            "layer_name": item.title,
            "item_id": item.id,
            "FY": fiscal_year,
            "owner": owner_name,
            "last_edited_user": last_edited_user,
            "created_user": created_user1,
            "item_created": item_created_dt,
            "item_updated": item_updated_dt,
            "data_updated": data_updated_dt,
            "schema_updated": schema_updated_dt,
            "report_month": report_month_dt,
            "total_features": current_features,
            "is_authoritative": is_authoritative,
            "run_timestamp": self.context.run_timestamp,
            "data_run_label": self.context.run_label,
            "edit_run_id": self.context.run_id,
            "time_zone": timezone_flag,
        }

        # Optional fields
        self._add_optional_fields(
            record=record,
            props=props,
            layer_id=layer_id,
            owner_name=owner_name,
            delta_features=delta_features,
            service_url=service_url,   # ✅ NEW
        )

        return record

    def _calculate_delta(self, layer_id: int, item_id: str, current_features: int) -> int:
        if not self.config.delta_features:
            return 0

        lookup_key = (self.portal_name, item_id, layer_id)
        if lookup_key in self.prev_counts:
            return current_features - self.prev_counts[lookup_key]
        return 0

    def _add_optional_fields(
        self,
        record: Dict,
        props,
        layer_id: int,
        owner_name: str,
        delta_features: int,
        service_url: Optional[str],
    ):
        if self.config.sub_layer_name:
            record["sub_layer_name"] = getattr(props, "name", f"Layer {layer_id}")

        if self.config.sub_layer_id:
            record["sub_layer_id"] = layer_id

        if self.config.owner:
            record["owner"] = owner_name

        if self.config.delta_features:
            record["delta_features"] = delta_features



def _get_items(gis_obj, portal_name: str) -> List:
    if CONFIG.TEST_MODE:
        try:
            item = gis_obj.content.get(CONFIG.TEST_ITEM_ID)
            if item:
                print(f"🔎 [{portal_name}] TEST MODE: Using item '{item.title}' ({CONFIG.TEST_ITEM_ID})")
                return [item]
        except Exception as e:
            print(f"❌ [{portal_name}] Could not find test item {CONFIG.TEST_ITEM_ID}: {e}")
        return []

    items = gis_obj.content.search(
        query='type:"Feature Service" -type:"Hosted Table"',
        max_items=CONFIG.MAX_ITEMS,
    )

    # ✅ Filter views from AGOL only
    if portal_name == "ArcGIS Online":
        before = len(items)
        items = [it for it in items if is_hosted_source_feature_service(it)]
        print(f"🔎 [{portal_name}] Found {before} Feature Services → kept {len(items)} hosted sources (views removed).")
    else:
        print(f"🔎 [{portal_name}] Found {len(items)} Feature Services.")

    return items


def _format_delta_info(records: List[Dict], config: AuditTableConfig) -> str:
    if not config.delta_features or not records:
        return ""

    deltas = [r.get("delta_features", 0) for r in records]
    non_zero = [d for d in deltas if d != 0]

    if non_zero:
        delta_summary = ", ".join([f"{d:+d}" for d in non_zero])
        return f" (Δ: {delta_summary})"

    return ""


def collect_all_items(gis_obj, portal_name: str, config: AuditTableConfig,
                      prev_counts: Dict, run_context: RunContext) -> List[Dict]:
    print(f"🔎 [{portal_name}] Searching Feature Services...")

    items = _get_items(gis_obj, portal_name)
    if not items:
        return []

    collector = LayerCollector(gis_obj, portal_name, config, prev_counts, run_context)
    all_records: List[Dict] = []

    with ThreadPoolExecutor(max_workers=CONFIG.MAX_WORKERS) as executor:
        future_to_item = {executor.submit(collector.collect_from_item, item): item for item in items}

        for future in as_completed(future_to_item):
            item = future_to_item[future]
            try:
                records = future.result()
                all_records.extend(records)

                delta_info = _format_delta_info(records, config)
                print(f"✅ [{portal_name}] {item.title}: {len(records)} sublayers{delta_info}")
            except Exception:
                pass

    print(f"🏁 [{portal_name}] Collected {len(all_records)} records\n")
    return all_records
