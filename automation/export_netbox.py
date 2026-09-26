#!/usr/bin/env python3
"""
Export Device + Prefix/VLAN từ NetBox ra file YAML — đúng định dạng mà
netbox_import.py đọc vào (devices: [...] + subnets: [...]) — dùng để backup
hoặc để có bản YAML mới nhất khớp với những gì đang thật sự có trên NetBox.

Cách dùng:
    export NETBOX_URL="https://netbox.example.com"
    export NETBOX_TOKEN="..."
    python3 export_netbox.py inventory_export.yaml

LƯU Ý — vài chỗ không thể khôi phục 100% y hệt file gốc:
    - Nếu lúc import model bị để trống, script import đã đặt tạm
      "Generic-<vendor>-<kind>" làm Device Type — export ra sẽ thấy đúng
      chuỗi placeholder đó trong `model`, không phải model rỗng ban đầu.
    - `kind` được suy ngược từ tên Device Role (Access Point -> ap,
      Switch -> switch, Firewall -> firewall, Router -> router; role khác
      thì lấy chính tên role viết thường, có thể không khớp 100% giá trị
      `kind` gốc nếu nhiều kind khác nhau từng dùng chung 1 role).
    - Field lạ từng bị gộp vào Comments (theo format "key: value" mỗi dòng)
      sẽ được tách lại thành field riêng khi export, nhưng nếu comment gốc
      có xuống dòng/định dạng khác thường thì có thể tách sai.
"""

import argparse
import ipaddress
import os
import sys

import yaml

try:
    import pynetbox
except ImportError:
    sys.exit("Thiếu thư viện pynetbox. Chạy: pip install pynetbox pyyaml")


# Đảo ngược ROLE_NAME_MAP trong netbox_import.py — Device Role -> kind
ROLE_TO_KIND = {
    "Access Point": "ap",
    "Switch": "switch",
    "Router": "router",
    "Firewall": "firewall",
}


def parse_comments(comments):
    """Tách lại các field lạ đã bị gộp vào Comments (mỗi dòng "key: value")."""
    extra = {}
    if not comments:
        return extra
    for line in comments.splitlines():
        if ": " in line:
            k, v = line.split(": ", 1)
            extra[k.strip()] = v.strip()
    return extra


def mgmt_interface_name(nb, device):
    """Tìm tên interface đang giữ primary IPv4 của device (mặc định 'mgmt0')."""
    if not device.primary_ip4:
        return None
    ip_obj = nb.ipam.ip_addresses.get(device.primary_ip4.id)
    if ip_obj and ip_obj.assigned_object:
        return ip_obj.assigned_object.name
    return None


def export_device(nb, device):
    d = {}
    d["kind"] = ROLE_TO_KIND.get(str(device.role), str(device.role).lower())
    d["vendor"] = device.device_type.manufacturer.name.lower()
    d["name"] = device.name
    if device.primary_ip4:
        d["ip"] = str(ipaddress.ip_interface(device.primary_ip4.address).ip)
    d["model"] = device.device_type.model
    if device.serial:
        d["serial"] = device.serial
    if device.description:
        d["description"] = device.description
    d["status"] = device.status.value if device.status else "active"
    if device.location:
        d["location"] = device.location.name
    d["site"] = device.site.name
    cf = device.custom_fields or {}
    if cf.get("netops_layer"):
        d["layer"] = cf["netops_layer"]
    if cf.get("netops_credential_key"):
        d["credential_key"] = cf["netops_credential_key"]
    if cf.get("netops_os_version"):
        d["os_version"] = cf["netops_os_version"]
    if device.platform:
        d["os"] = device.platform.name
    if device.rack:
        d["rack"] = device.rack.name
        if device.position:
            d["rack_u"] = int(device.position)
    iface_name = mgmt_interface_name(nb, device)
    if iface_name and iface_name != "mgmt0":
        d["mgmt_interface"] = iface_name
    # Field lạ từng bị gộp vào Comments (xem build_comments trong netbox_import.py)
    d.update(parse_comments(device.comments))
    return d


def export_subnet(prefix):
    s = {"prefix": str(prefix.prefix)}
    if prefix.vlan:
        s["vlan_id"] = prefix.vlan.vid
        s["vlan_name"] = prefix.vlan.name

    # NetBox < 4.7 dùng field 'site'
    if getattr(prefix, "site", None):
        s["site"] = prefix.site.name
    # NetBox >= 4.7 dùng 'scope' và 'scope_type'
    elif getattr(prefix, "scope", None) and getattr(prefix, "scope_type", None):
        scope_type_str = getattr(prefix.scope_type, "value", str(prefix.scope_type))
        if scope_type_str == "dcim.site":
            s["site"] = prefix.scope.name

    return s


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_file", help="Đường dẫn file YAML sẽ ghi ra")
    args = parser.parse_args()

    url = os.environ.get("NETBOX_URL")
    token = os.environ.get("NETBOX_TOKEN")
    if not url or not token:
        sys.exit("Thiếu NETBOX_URL / NETBOX_TOKEN trong biến môi trường.")

    nb = pynetbox.api(url, token=token)

    print("Đang tải danh sách Device từ NetBox...")
    devices = [export_device(nb, dev) for dev in nb.dcim.devices.all()]
    print(f"  -> {len(devices)} device")

    print("Đang tải danh sách Prefix từ NetBox...")
    subnets = [export_subnet(p) for p in nb.ipam.prefixes.all()]
    print(f"  -> {len(subnets)} prefix")

    data = {"devices": devices, "subnets": subnets}
    with open(args.output_file, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False, default_flow_style=False)

    print(f"\nĐã ghi ra: {args.output_file}")


if __name__ == "__main__":
    main()
