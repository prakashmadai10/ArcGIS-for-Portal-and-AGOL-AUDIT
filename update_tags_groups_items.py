from typing import Dict, Any, Optional, Set, List

def tag_items_in_groups_from_raw(
    gis,
    raw_group_ids: str,
    tag_to_add: str = "collab",
    allowed_types: Optional[Set[str]] = None,
    max_items_per_group: int = 2000,
    verbose: bool = True,
) -> Dict[str, Any]:
    """
    One-call function:
      - parses raw comma/newline-separated group IDs
      - loops through groups
      - tags allowed item types with tag_to_add

    Call from main.py with ONLY:
        tag_items_in_groups_from_raw(gis_agol, raw_group_ids)

    Returns a summary dict.
    """
    if allowed_types is None:
        allowed_types = {"Feature Service", "Feature Layer"}

    # ---- Parse group IDs inside the function ----
    group_ids: List[str] = [
        g.strip()
        for g in raw_group_ids.replace("\n", "").split(",")
        if g.strip()
    ]

    tag_lower = tag_to_add.strip().lower()

    summary: Dict[str, Any] = {
        "groups_total": len(group_ids),
        "groups_not_found": 0,
        "items_seen": 0,
        "tagged_updated": 0,
        "already_tagged": 0,
        "skipped_type": 0,
        "failed": 0,
        "errors": [],  # list of dicts
    }

    def _add_tag(item) -> str:
        """Return: 'updated' | 'already' | 'failed'"""
        try:
            tags = list(item.tags or [])
            if tag_lower in {t.lower() for t in tags}:
                return "already"

            ok = item.update(item_properties={"tags": tags + [tag_to_add]})
            return "updated" if ok else "failed"
        except Exception:
            return "failed"

    for gid in group_ids:
        try:
            grp = gis.groups.get(gid)
            if not grp:
                summary["groups_not_found"] += 1
                if verbose:
                    print(f"\n❌ Group not found: {gid}")
                continue

            if verbose:
                print(f"\n==============================")
                print(f"👥 Group: {grp.title}")
                print(f"ID: {grp.id}")
                print(f"==============================")

            items = grp.content(max_items=max_items_per_group) or []
            if verbose:
                print(f"Items in group: {len(items)}")

            for item in items:
                summary["items_seen"] += 1

                try:
                    if (item.type or "") not in allowed_types:
                        summary["skipped_type"] += 1
                        continue

                    status = _add_tag(item)

                    if status == "updated":
                        summary["tagged_updated"] += 1
                        if verbose:
                            print(f"🏷️ Tagged: {item.title} ({item.id})")
                    elif status == "already":
                        summary["already_tagged"] += 1
                    else:
                        summary["failed"] += 1
                        if verbose:
                            print(f"❌ Failed to tag: {item.title} ({item.id})")

                except Exception as e:
                    summary["failed"] += 1
                    summary["errors"].append(
                        {"group_id": gid, "item_id": getattr(item, "id", None), "error": str(e)}
                    )
                    if verbose:
                        print(f"❌ Error tagging item {getattr(item,'id',None)}: {e}")

        except Exception as e:
            summary["errors"].append({"group_id": gid, "error": str(e)})
            if verbose:
                print(f"\n❌ Error reading group {gid}: {e}")

    if verbose:
        print("\n========== TAGGING SUMMARY ==========")
        print(f"Groups total     : {summary['groups_total']}")
        print(f"Groups not found : {summary['groups_not_found']}")
        print(f"Items seen       : {summary['items_seen']}")
        print(f"Tagged (updated) : {summary['tagged_updated']}")
        print(f"Already tagged   : {summary['already_tagged']}")
        print(f"Skipped (type)   : {summary['skipped_type']}")
        print(f"Failed           : {summary['failed']}")

    return summary
