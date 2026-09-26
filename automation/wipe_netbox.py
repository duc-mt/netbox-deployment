#!/usr/bin/env python3
"""
XOÁ SẠCH toàn bộ dữ liệu inventory + IPAM trên NetBox, chuẩn bị import lại
từ đầu bằng import_to_netbox.py / import_subnets.py.

Xoá: IP Address, Interface, Device, Rack, Location, Prefix, VLAN,
     Device Type, Device Role, Platform, Manufacturer, Site.
KHÔNG đụng tới: user, token, custom field definitions (netops_*), plugin,
     hay bất kỳ object nào ngoài danh sách trên.

**HÀNH ĐỘNG NÀY KHÔNG THỂ HOÀN TÁC.** Không có rollback cho script này —
nếu cần giữ lại dữ liệu, hãy backup database (pg_dump) trước khi chạy.

Cách dùng:
    export NETBOX_URL="https://netbox.example.com"
    export NETBOX_TOKEN="..."
    python3 wipe_netbox.py --dry-run     # xem trước sẽ xoá bao nhiêu object
    python3 wipe_netbox.py               # xoá thật, sẽ hỏi xác nhận
    python3 wipe_netbox.py --yes         # xoá thật, bỏ qua xác nhận (CẨN THẬN)
"""

import argparse
import os
import sys
from typing import Any, Dict, List, Optional

try:
    import pynetbox
except ImportError:
    sys.exit("Thiếu thư viện pynetbox. Chạy: pip install pynetbox")


# Thứ tự xoá: từ "lá" (phụ thuộc nhiều nhất) tới "gốc", để không bị NetBox
# chặn vì ràng buộc khoá ngoại (PROTECT) — vd không xoá được Site khi vẫn
# còn Rack/Location/Prefix/VLAN tham chiếu tới nó.
PLAN = [
    ("ipam", "ip_addresses"),
    ("dcim", "interfaces"),
    ("dcim", "devices"),
    ("dcim", "racks"),
    ("dcim", "locations"),
    ("ipam", "prefixes"),
    ("ipam", "vlans"),
    ("dcim", "device_types"),
    ("dcim", "device_roles"),
    ("dcim", "platforms"),
    ("dcim", "manufacturers"),
    ("dcim", "sites"),
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Chỉ đếm, không xoá")
    parser.add_argument("--yes", action="store_true", help="Bỏ qua bước xác nhận")
    args = parser.parse_args()

    url = os.environ.get("NETBOX_URL")
    token = os.environ.get("NETBOX_TOKEN")
    if not url or not token:
        sys.exit("Thiếu NETBOX_URL / NETBOX_TOKEN trong biến môi trường.")

    nb = pynetbox.api(url, token=token)

    print(f"Chuẩn bị xoá dữ liệu trên: {url}")
    print("Đang đếm số lượng object hiện có...\n")

    counted = []
    for app, ep_name in PLAN:
        endpoint = getattr(getattr(nb, app), ep_name)
        objs = list(endpoint.all())
        counted.append((app, ep_name, objs))
        print(f"  {app}.{ep_name}: {len(objs)}")

    total = sum(len(objs) for _, _, objs in counted)
    print(f"\nTổng cộng: {total} object sẽ bị xoá.")

    if args.dry_run:
        print("\n[dry-run] Không xoá gì cả — chỉ hiển thị số lượng ở trên.")
        return

    if total == 0:
        print("\nKhông có gì để xoá.")
        return

    if not args.yes:
        print("\n*** HÀNH ĐỘNG NÀY KHÔNG THỂ HOÀN TÁC ***")
        answer = input(f"Gõ chính xác XOA SACH để xác nhận xoá {total} object: ")
        if answer.strip() != "XOA SACH":
            print("Huỷ — không có gì bị xoá.")
            return

    print()
    deleted_total, failed_total = 0, 0
    for app, ep_name, objs in counted:
        if not objs:
            continue
        endpoint = getattr(getattr(nb, app), ep_name)
        try:
            endpoint.delete(objs)
            print(f"  - Đã xoá {len(objs)} {ep_name}")
            deleted_total += len(objs)
        except pynetbox.RequestError as e:
            print(f"  ! Lỗi khi xoá {ep_name}: {e}")
            failed_total += len(objs)

    print(f"\n== Hoàn tất == Đã xoá: {deleted_total}, lỗi: {failed_total}")
    if failed_total:
        print(
            "Một số object không xoá được, thường do vẫn còn object khác "
            "(ngoài danh sách trên) tham chiếu tới. Kiểm tra thủ công trên NetBox."
        )


if __name__ == "__main__":
    main()
