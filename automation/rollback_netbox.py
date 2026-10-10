"""
==============================================================================
Module Name:   rollback_netbox.py
Description:   Source module rollback_netbox.py.
Author:        Mai Tan Duc <ducmai.network@gmail.com>
Created:       2026-10-10
Version:       1.0.0
License:       MIT
==============================================================================
Usage:         python3 rollback_netbox.py [options]
Notes:         Requires Python 3.8+
==============================================================================
"""

#!/usr/bin/env python3
import argparse
import json
import os
import sys

try:
    import pynetbox
except ImportError:
    sys.exit("Thiếu thư viện pynetbox. Chạy: pip install pynetbox")


ORDER = [
    ("ip_addresses", "ipam", "ip_addresses"),
    ("interfaces", "dcim", "interfaces"),
    ("devices", "dcim", "devices"),
    ("device_types", "dcim", "device_types"),
    ("racks", "dcim", "racks"),
    ("locations", "dcim", "locations"),
    ("prefixes", "ipam", "prefixes"),
    ("vlans", "ipam", "vlans"),
    ("platforms", "dcim", "platforms"),
    ("device_roles", "dcim", "device_roles"),
    ("manufacturers", "dcim", "manufacturers"),
    ("sites", "dcim", "sites"),
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest_file")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    url = os.environ.get("NETBOX_URL")
    token = os.environ.get("NETBOX_TOKEN")
    if not args.dry_run and (not url or not token):
        sys.exit("Thiếu NETBOX_URL / NETBOX_TOKEN trong biến môi trường.")

    with open(args.manifest_file, encoding="utf-8") as f:
        manifest = json.load(f)

    print(f"Manifest tạo lúc: {manifest.get('created_at')}")

    nb = None
    if not args.dry_run:
        nb = pynetbox.api(url, token=token)

    deleted, failed = 0, 0
    for category, app, endpoint_name in ORDER:
        items = manifest.get(category, [])
        if not items:
            continue
        endpoint = getattr(getattr(nb, app), endpoint_name) if nb else None
        for item in items:
            label = f"{category}: {item['name']} (id={item['id']})"
            if args.dry_run:
                print(f"  [dry-run] sẽ xoá {label}")
                continue
            try:
                obj = endpoint.get(item["id"])  # type: ignore
                if obj is None:
                    print(f"  ~ Không tìm thấy (có thể đã bị xoá trước đó): {label}")
                    continue
                obj.delete()
                print(f"  - Đã xoá {label}")
                deleted += 1
            except pynetbox.RequestError as e:
                print(f"  ! Không xoá được {label}: {e}")
                failed += 1

    print(f"\nHoàn tất. Đã xoá: {deleted}, lỗi: {failed}")
    if failed:
        print(
            "Một số object không xoá được, thường vì đang bị object khác "
            "(ngoài phạm vi manifest này) tham chiếu tới. Kiểm tra thủ công trên NetBox."
        )


if __name__ == "__main__":
    main()
