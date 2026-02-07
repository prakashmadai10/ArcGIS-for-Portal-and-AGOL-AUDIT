# fields_edit.py
from typing import Optional, Dict, Tuple

from arcgis.features import FeatureLayer

from time_utils import ms_to_datetime


class EditFieldDetector:
    """Detects editor tracking field names in layers with caching."""

    FIELD_CANDIDATES = {
        "creatorField": ("Creator", "Creator_1", "created_user", "createdby"),
        "createDateField": ("CreationDate", "CreationDate_1", "created_date", "date_created", "CreateDate"),
        "editorField": ("Editor", "Editor_1", "last_edited_user", "editedby", "edit_user"),
        "editDateField": ("EditDate", "EditDate_1", "last_edited_date", "last_edit_date", "LastEditDate"),
    }

    _cache: Dict[str, Dict[str, Optional[str]]] = {}

    @classmethod
    def detect(cls, layer: FeatureLayer) -> Dict[str, Optional[str]]:
        layer_url = layer.url

        if layer_url in cls._cache:
            return cls._cache[layer_url]

        result = {field_type: None for field_type in cls.FIELD_CANDIDATES.keys()}
        props = layer.properties

        edit_info = getattr(props, "editFieldsInfo", None)
        if edit_info:
            result["creatorField"] = edit_info.get("creatorField") or edit_info.get("creatorfield")
            result["createDateField"] = (
                edit_info.get("creationDateField")
                or edit_info.get("createDateField")
                or edit_info.get("createdDateField")
            )
            result["editorField"] = edit_info.get("editorField") or edit_info.get("editUserField")
            result["editDateField"] = edit_info.get("editDateField") or edit_info.get("lastEditDateField")

        if not all(result.values()):
            existing_fields = {f["name"].lower(): f["name"] for f in props.fields}

            for field_type, candidates in cls.FIELD_CANDIDATES.items():
                if not result[field_type]:
                    for candidate in candidates:
                        if candidate and candidate.lower() in existing_fields:
                            result[field_type] = existing_fields[candidate.lower()]
                            break

        cls._cache[layer_url] = result
        return result


def get_latest_user(layer: FeatureLayer, user_field: str, date_field: str,
                    order: str = "DESC") -> Optional[str]:
    if not user_field or not date_field:
        return None

    try:
        query_result = layer.query(
            where=f"{user_field} IS NOT NULL AND {date_field} IS NOT NULL",
            out_fields=f"{user_field},{date_field}",
            order_by_fields=f"{date_field} {order}",
            result_record_count=1,
            return_geometry=False,
        )
        if query_result.features:
            return query_result.features[0].get_value(user_field)
    except Exception:
        pass

    return None


def get_last_creator(layer: FeatureLayer) -> Optional[str]:
    fields = EditFieldDetector.detect(layer)
    return get_latest_user(layer, fields.get("creatorField"), fields.get("createDateField"), order="DESC")


def get_last_editor(layer: FeatureLayer) -> Optional[str]:
    fields = EditFieldDetector.detect(layer)
    return get_latest_user(layer, fields["editorField"], fields["editDateField"])


def extract_edit_dates(layer_props, service_props) -> Tuple[Optional[int], Optional[int]]:
    """Extract data and schema edit dates from properties."""
    data_ms = schema_ms = None

    if hasattr(layer_props, "editingInfo") and layer_props.editingInfo:
        try:
            edit_info = layer_props.editingInfo
            data_ms = edit_info.get("dataLastEditDate")
            schema_ms = edit_info.get("schemaLastEditDate")
        except Exception:
            pass

    if (not data_ms or not schema_ms) and hasattr(service_props, "editingInfo"):
        try:
            edit_info = service_props.editingInfo
            data_ms = data_ms or edit_info.get("dataLastEditDate")
            schema_ms = schema_ms or edit_info.get("schemaLastEditDate")
        except Exception:
            pass

    if not schema_ms:
        schema_ms = getattr(layer_props, "lastSchemaEditDate", None) \
                    or getattr(service_props, "lastSchemaEditDate", None)

    return data_ms, schema_ms
