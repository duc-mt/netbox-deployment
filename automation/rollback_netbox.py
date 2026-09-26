#!/usr/bin/env python3
"""
Rollback lần chạy netbox_import.py gần nhất bằng file manifest nó tạo ra.

CHỈ xoá đúng những object mà lần chạy đó đã TẠO MỚI (không đụng tới object
có sẵn từ trước trong NetBox, kể cả khi trùng tên/trùng dải IP).

Cách dùng:
    export NETBOX_URL="https://netbox.example.com"
    export NETBOX_TOKEN="..."
    python3 rollback_netbox.py netbox_import_manifest_20260101-120000.json

    Thêm --dry-run để xem trước sẽ xoá gì mà chưa xoá thật.

Thứ tự xoá đi từ "lá" (phụ thuộc nhiều nhất) tới "gốc", để không bị NetBox
chặn vì ràng buộc khoá ngoại (vd không xoá được Site khi vẫn còn Rack,
Location, Prefix hay VLAN đang tham chiếu tới nó):
    ip_addresses -> interfaces -> devices -> device_types -> racks
    -> locations -> prefixes -> vlans -> platforms -> device_roles
    -> manufacturers -> sites
"""

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional

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
                obj = endpoint.get(item["id"]) # type: ignore
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
