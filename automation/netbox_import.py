#!/usr/bin/env python3
"""
Import devices + subnet/VLAN (định dạng CMC_NMS_Tool) vào NetBox — MỘT file
YAML, MỘT script import, MỘT script rollback (gộp import_to_netbox.py +
import_subnets.py trước đây).

Cách dùng:
    pip install pynetbox pyyaml
    export NETBOX_URL="https://netbox.example.com"
    export NETBOX_TOKEN="0123456789abcdef0123456789abcdef01234567"
    python3 netbox_import.py inventory.yaml

    Thêm --dry-run để xem trước sẽ tạo những gì mà KHÔNG ghi vào NetBox.

File YAML có 2 phần, đều tuỳ chọn (thiếu phần nào thì bỏ qua phần đó):
    devices:
      - name: ...
        kind: ...
        ...                 # như devices_1.yaml trước đây
    subnets:
      - prefix: 172.28.188.128/26
        vlan_id: 117
        vlan_name: VLAN117
        site: DCTT          # site nên đã có (script tạo Site ở phần devices
                             # trước, rồi mới xử lý phần subnets)

Script tự tạo (nếu chưa có, dùng get_or_create — chạy lại nhiều lần an toàn):
    - Site            (từ field `site`)
    - Location        (từ field `location`, thuộc Site tương ứng)
    - Manufacturer    (từ field `vendor`)
    - Device Role     (từ field `kind`: ap -> "Access Point", switch ->
                        "Switch", firewall -> "Firewall", còn lại dùng
                        chính tên `kind` viết hoa chữ đầu)
    - Platform        (từ field `os`, nếu có)
    - Device Type     (từ field `model`; nếu model rỗng thì dùng
                        "Generic-<vendor>-<kind>" làm placeholder, u_height=1)
    - Rack            (từ field `rack`, thuộc site tương ứng, 48U mặc định
                        như comment trong YAML, NetBox mặc định đếm U từ
                        dưới lên nên khớp với rack_u trong file)
    - Device          (name, site, location, role, device_type, platform,
                        rack+position, serial, description, status, và các
                        custom field netops_credential_key / netops_layer /
                        netops_os_version nếu có)
    - Interface + IP  (interface lấy tên theo `mgmt_interface`, mặc định là
                        "mgmt0"; gán IP field `ip` /32 vào interface đó rồi
                        set làm primary IPv4 của device — mỗi device có
                        object IP riêng dù trùng địa chỉ với device khác,
                        vd cặp switch/firewall HA dùng chung IP quản lý)
    - VLAN            (từ `vlan_id` + `vlan_name`, thuộc site nếu có)
    - Prefix          (từ `prefix`, gán site + vlan tương ứng)

Field nào chưa có ô tương ứng trong NetBox (nếu YAML có thêm field lạ sau
này) sẽ tự động được gộp vào phần Comments của device để không mất dữ liệu.

Sau khi chạy xong (không phải --dry-run), script ghi ra một file
netbox_import_manifest_<thời-gian>.json liệt kê đúng những object vừa TẠO
MỚI (không ghi object có sẵn hay chỉ bị update) — dùng file này với
rollback_netbox.py để undo nếu cần.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone

import yaml

try:
    import pynetbox
except ImportError:
    sys.exit("Thiếu thư viện pynetbox. Chạy: pip install pynetbox pyyaml")


# kind -> tên Device Role trên NetBox
ROLE_NAME_MAP = {
    "ap": "Access Point",
    "switch": "Switch",
    "router": "Router",
    "firewall": "Firewall",
}

# Các kind chỉ hiện trên rack layout, không giám sát (theo comment trong YAML)
RACK_ONLY_KINDS = {"server", "storage", "ups", "patch_panel", "pdu", "other"}

# Các field trong YAML đã có "chỗ" tương ứng trên NetBox — field nào KHÔNG
# nằm trong danh sách này sẽ tự động được gộp vào Comments (xem build_comments).
KNOWN_FIELDS = {
    "name",
    "kind",
    "vendor",
    "model",
    "os",
    "os_version",
    "ip",
    "serial",
    "description",
    "status",
    "location",
    "site",
    "layer",
    "credential_key",
    "rack",
    "rack_u",
    "mgmt_interface",
}


def slugify(text):
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return re.sub(r"-+", "-", text).strip("-")


def get_or_create(endpoint, defaults, **lookup):
    obj = endpoint.get(**lookup)
    if obj:
        return obj, False
    payload = {**lookup, **defaults}
    obj = endpoint.create(payload)
    return obj, True


class Importer:
    def __init__(self, nb, dry_run=False):
        self.nb = nb
        self.dry_run = dry_run
        self.stats = {"created": 0, "skipped": 0, "updated": 0, "errors": 0}
        self._cache = {}
        # Nhật ký mọi object được TẠO MỚI trong lần chạy này (không ghi object
        # đã tồn tại từ trước hoặc chỉ bị update) — dùng để rollback chính xác.
        self.manifest = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "ip_addresses": [],
            "interfaces": [],
            "devices": [],
            "device_types": [],
            "racks": [],
            "locations": [],
            "platforms": [],
            "device_roles": [],
            "manufacturers": [],
            "sites": [],
            "prefixes": [],
            "vlans": [],
        }

    def log(self, msg):
        print(msg)

    def record(self, category, obj):
        if obj is not None:
            self.manifest[category].append({"id": obj.id, "name": str(obj)})

    def save_manifest(self, path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.manifest, f, ensure_ascii=False, indent=2)
        return path

    # ---- lookups / creation helpers -------------------------------------

    def get_site(self, code):
        key = ("site", code)
        if key in self._cache:
            return self._cache[key]
        if self.dry_run:
            self.log(f"  [dry-run] site: {code}")
            return None
        site, created = get_or_create(
            self.nb.dcim.sites,
            {"slug": slugify(code)},
            name=code,
        )
        if created:
            self.log(f"  + Tạo Site: {code}")
            self.stats["created"] += 1
            self.record("sites", site)
        self._cache[key] = site
        return site

    def get_location(self, location_name, site):
        if not location_name or not site:
            return None
        key = ("location", site.id, location_name)
        if key in self._cache:
            return self._cache[key]
        if self.dry_run:
            self.log(f"  [dry-run] location: {location_name}")
            return None
        # Tránh filter theo "site=<id>" (numeric PK) — dùng slug (string) để
        # không đi qua ModelChoiceField dễ lỗi với site vừa tạo (xem get_rack).
        loc_slug = slugify(f"{site.slug}-{location_name}")
        existing = self.nb.dcim.locations.get(slug=loc_slug)
        if existing:
            location, created = existing, False
        else:
            location = self.nb.dcim.locations.create(
                {"name": location_name, "slug": loc_slug, "site": site.id}
            )
            created = True
        if created:
            self.log(f"  + Tạo Location: {location_name} ({site.name})")
            self.stats["created"] += 1
            self.record("locations", location)
        self._cache[key] = location
        return location

    def get_manufacturer(self, vendor):
        key = ("mfr", vendor)
        if key in self._cache:
            return self._cache[key]
        name = vendor.title() if vendor.islower() else vendor
        if self.dry_run:
            self.log(f"  [dry-run] manufacturer: {name}")
            return None
        mfr, created = get_or_create(
            self.nb.dcim.manufacturers,
            {"slug": slugify(vendor)},
            name=name,
        )
        if created:
            self.log(f"  + Tạo Manufacturer: {name}")
            self.stats["created"] += 1
            self.record("manufacturers", mfr)
        self._cache[key] = mfr
        return mfr

    def get_role(self, kind):
        key = ("role", kind)
        if key in self._cache:
            return self._cache[key]
        name = ROLE_NAME_MAP.get(kind, kind.replace("_", " ").title())
        if self.dry_run:
            self.log(f"  [dry-run] device role: {name}")
            return None
        role, created = get_or_create(
            self.nb.dcim.device_roles,
            {"slug": slugify(name), "color": "9e9e9e"},
            name=name,
        )
        if created:
            self.log(f"  + Tạo Device Role: {name}")
            self.stats["created"] += 1
            self.record("device_roles", role)
        self._cache[key] = role
        return role

    def get_platform(self, os_name):
        if not os_name:
            return None
        key = ("platform", os_name)
        if key in self._cache:
            return self._cache[key]
        if self.dry_run:
            self.log(f"  [dry-run] platform: {os_name}")
            return None
        platform, created = get_or_create(
            self.nb.dcim.platforms,
            {"slug": slugify(os_name)},
            name=os_name,
        )
        if created:
            self.log(f"  + Tạo Platform: {os_name}")
            self.stats["created"] += 1
            self.record("platforms", platform)
        self._cache[key] = platform
        return platform

    def get_device_type(self, vendor, model, kind, manufacturer):
        model_name = model or f"Generic-{vendor}-{kind}"
        key = ("dtype", vendor, model_name)
        if key in self._cache:
            return self._cache[key]
        if self.dry_run:
            self.log(f"  [dry-run] device type: {model_name}")
            return None
        # LƯU Ý: kiểm tra tồn tại KHÔNG được filter theo "manufacturer=<id>"
        # (numeric PK) — NetBox 4.7 validate filter này qua ModelChoiceField
        # và không nhận ra manufacturer vừa tạo trong cùng phiên làm việc,
        # trả lỗi "Select a valid choice..." dù ID đó tồn tại thật trong DB
        # (đã kiểm chứng bằng curl + pynetbox thuần). Dùng slug (duy nhất,
        # do chính script sinh ra) để tránh hẳn filter FK này.
        dtype_slug = slugify(f"{vendor}-{model_name}")
        existing = self.nb.dcim.device_types.get(slug=dtype_slug)
        if existing:
            dtype, created = existing, False
        else:
            dtype = self.nb.dcim.device_types.create(
                {
                    "manufacturer": manufacturer.id,
                    "model": model_name,
                    "slug": dtype_slug,
                    "u_height": 1,
                }
            )
            created = True
        if created:
            self.log(f"  + Tạo Device Type: {model_name} ({vendor})")
            self.stats["created"] += 1
            self.record("device_types", dtype)
        self._cache[key] = dtype
        return dtype

    def get_rack(self, rack_name, site, location=None):
        if not rack_name:
            return None
        key = ("rack", site.id if site else None, rack_name)
        if key in self._cache:
            rack = self._cache[key]
        elif self.dry_run:
            self.log(f"  [dry-run] rack: {rack_name}")
            return None
        else:
            # Cùng lý do như Device Type ở trên: tránh filter theo "site=<id>"
            # (numeric PK), dùng "site=<slug>" (string) để không đi qua
            # ModelChoiceField validation dễ lỗi với site vừa tạo.
            existing = self.nb.dcim.racks.get(name=rack_name, site=site.slug)
            if existing:
                rack, created = existing, False
            else:
                payload = {"name": rack_name, "site": site.id, "u_height": 48}
                if location:
                    payload["location"] = location.id
                rack = self.nb.dcim.racks.create(payload)
                created = True
            if created:
                self.log(f"  + Tạo Rack: {rack_name}")
                self.stats["created"] += 1
                self.record("racks", rack)
            self._cache[key] = rack

        # Rack đã tồn tại nhưng chưa gắn location (hoặc gắn sai location so
        # với device hiện tại) — NetBox yêu cầu rack.location phải khớp với
        # device.location nếu cả hai đều được set, nên cần đồng bộ lại.
        if (
            not self.dry_run
            and rack
            and location
            and (not rack.location or rack.location.id != location.id)
        ):
            rack.location = location.id
            rack.save()
        return rack

    # ---- main per-device flow -------------------------------------------

    def build_comments(self, d):
        # Tự động gộp bất kỳ field nào trong YAML mà chưa có ô tương ứng
        # trên NetBox (KNOWN_FIELDS) — để không mất dữ liệu nếu file có
        # thêm cột mới sau này mà script chưa kịp cập nhật.
        extra = [
            f"{k}: {v}"
            for k, v in d.items()
            if k not in KNOWN_FIELDS and v not in (None, "")
        ]
        return "\n".join(extra)

    def import_device(self, d):
        name = d.get("name")
        kind = d.get("kind")
        vendor = d.get("vendor")
        ip = d.get("ip")
        layer = d.get("layer")

        if not name or not kind or not vendor:
            self.log(f"  ! Bỏ qua record thiếu name/kind/vendor: {d}")
            self.stats["errors"] += 1
            return

        if self.dry_run:
            self.log(f"[dry-run] Device: {name} ({vendor} {kind}) ip={ip}")
            self.get_site(d.get("site"))
            self.get_role(kind)
            self.get_platform(d.get("os"))
            self.get_device_type(vendor, d.get("model"), kind, None)
            self.get_rack(d.get("rack"), None)
            return

        try:
            site = self.get_site(d.get("site"))
            location = self.get_location(d.get("location"), site)
            manufacturer = self.get_manufacturer(vendor)
            role = self.get_role(kind)
            platform = self.get_platform(d.get("os"))
            device_type = self.get_device_type(
                vendor, d.get("model"), kind, manufacturer
            )
            rack = (
                self.get_rack(d.get("rack"), site, location)
                if kind not in RACK_ONLY_KINDS or d.get("rack")
                else None
            )

            existing = self.nb.dcim.devices.get(name=name)
            payload = {
                "name": name,
                "device_type": device_type.id,
                "role": role.id,
                "site": site.id,
                "status": d.get("status") or "active",
                "serial": d.get("serial") or "",
                "description": d.get("description") or "",
                "comments": self.build_comments(d),
            }
            if platform:
                payload["platform"] = platform.id
            if location:
                payload["location"] = location.id
            custom_fields = {}
            if d.get("credential_key"):
                custom_fields["netops_credential_key"] = d["credential_key"]
            if layer:
                custom_fields["netops_layer"] = layer
            if d.get("os_version"):
                custom_fields["netops_os_version"] = d["os_version"]
            if custom_fields:
                payload["custom_fields"] = custom_fields
            if rack and d.get("rack_u"):
                payload["rack"] = rack.id
                payload["position"] = int(d["rack_u"])
                payload["face"] = "front"

            if existing:
                for k, v in payload.items():
                    setattr(existing, k, v)
                existing.save()
                device = existing
                self.log(f"  ~ Cập nhật Device: {name}")
                self.stats["updated"] += 1
            else:
                device = self.nb.dcim.devices.create(payload)
                self.log(f"+ Tạo Device: {name}")
                self.stats["created"] += 1
                self.record("devices", device)

            if ip:
                self.attach_ip(device, ip, d.get("mgmt_interface"))

        except pynetbox.RequestError as e:
            self.log(f"  ! Lỗi khi xử lý {name}: {e}")
            self.stats["errors"] += 1

    def attach_ip(self, device, ip, mgmt_interface):
        iface_name = mgmt_interface or "mgmt0"
        iface = self.nb.dcim.interfaces.get(device_id=device.id, name=iface_name)
        if not iface:
            iface = self.nb.dcim.interfaces.create(
                {"device": device.id, "name": iface_name, "type": "virtual"}
            )
            self.log(f"    + Tạo Interface {iface_name} trên {device.name}")
            self.stats["created"] += 1
            self.record("interfaces", iface)

        # QUAN TRỌNG: không dùng .get(address=...) — nhiều thiết bị khác nhau
        # có thể dùng chung một địa chỉ IP (vd cặp switch/firewall HA dùng
        # chung IP quản lý), nên cùng một "address" có thể có NHIỀU object IP
        # Address khác nhau, mỗi cái gán cho một interface riêng. Phải lọc
        # đúng theo interface CỦA THIẾT BỊ NÀY, không tái sử dụng IP object
        # đã gán cho interface của thiết bị khác.
        address = f"{ip}/32"
        ip_obj = None
        for candidate in self.nb.ipam.ip_addresses.filter(address=address):
            if candidate.assigned_object_id == iface.id:
                ip_obj = candidate
                break

        if not ip_obj:
            try:
                ip_obj = self.nb.ipam.ip_addresses.create(
                    {
                        "address": address,
                        "assigned_object_type": "dcim.interface",
                        "assigned_object_id": iface.id,
                        "status": "active",
                    }
                )
                self.log(f"    + Gán IP {address} vào {iface_name}")
                self.stats["created"] += 1
                self.record("ip_addresses", ip_obj)
            except pynetbox.RequestError:
                # NetBox instance này bật "Enforce unique space" nên không
                # cho 2 object IP khác nhau trùng địa chỉ (thường gặp ở cặp
                # switch/firewall HA dùng chung IP quản lý). Bỏ qua việc gán
                # IP làm primary cho thiết bị này (device đã tạo/update
                # thành công ở bước trước), nhưng vẫn ghi lại địa chỉ đó vào
                # Comments để không mất thông tin.
                self.log(
                    f"    ! Không gán được IP {address} (trùng IP toàn cục), đã ghi vào Comments"
                )
                self.stats["errors"] += 1
                note = f"Không gán được làm primary IP do trùng IP toàn cục: {address}"
                existing_comments = device.comments or ""
                if note not in existing_comments:
                    device.comments = (existing_comments + "\n" + note).strip()
                    device.save()
                return

        if device.primary_ip4 is None or device.primary_ip4.id != ip_obj.id:
            device.primary_ip4 = ip_obj.id
            device.save()

    # ---- subnet / VLAN (IPAM) --------------------------------------------

    def import_subnet(self, entry):
        prefix_val = entry.get("prefix")
        vlan_id = entry.get("vlan_id")
        vlan_name = entry.get("vlan_name") or (f"VLAN{vlan_id}" if vlan_id else None)
        site_name = entry.get("site")

        if not prefix_val:
            self.log(f"  ! Bỏ qua subnet thiếu 'prefix': {entry}")
            self.stats["errors"] += 1
            return

        if self.dry_run:
            self.log(
                f"[dry-run] Prefix {prefix_val} — VLAN {vlan_id} ({vlan_name}) — site {site_name}"
            )
            return

        try:
            site = self.get_site(site_name) if site_name else None

            vlan = None
            if vlan_id:
                key = ("vlan", site.id if site else None, vlan_id)
                if key in self._cache:
                    vlan = self._cache[key]
                else:
                    vlan_lookup = {"vid": vlan_id}
                    if site:
                        vlan_lookup["site"] = site.slug
                    vlan = self.nb.ipam.vlans.get(**vlan_lookup)
                    if not vlan:
                        vlan_payload = {"vid": vlan_id, "name": vlan_name}
                        if site:
                            vlan_payload["site"] = site.id
                        vlan = self.nb.ipam.vlans.create(vlan_payload)
                        self.log(f"  + Tạo VLAN {vlan_id} ({vlan_name})")
                        self.stats["created"] += 1
                        self.record("vlans", vlan)
                    self._cache[key] = vlan

            existing = self.nb.ipam.prefixes.get(prefix=prefix_val)
            payload = {"prefix": prefix_val}
            if site:
                # NetBox 4.x: Prefix không còn field "site" trực tiếp, thay
                # bằng "scope"/"scope_type" (generic — Site/Region/Location...).
                payload["scope_type"] = "dcim.site"
                payload["scope_id"] = site.id
            if vlan:
                payload["vlan"] = vlan.id

            if existing:
                for k, v in payload.items():
                    setattr(existing, k, v)
                existing.save()
                self.log(f"  ~ Cập nhật Prefix {prefix_val}")
                self.stats["updated"] += 1
            else:
                new_prefix = self.nb.ipam.prefixes.create(payload)
                self.log(f"+ Tạo Prefix {prefix_val}")
                self.stats["created"] += 1
                self.record("prefixes", new_prefix)

        except pynetbox.RequestError as e:
            self.log(f"  ! Lỗi khi xử lý subnet {prefix_val}: {e}")
            self.stats["errors"] += 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("yaml_file", help="Đường dẫn tới file YAML (devices + subnets)")
    parser.add_argument(
        "--dry-run", action="store_true", help="Chỉ in ra, không ghi vào NetBox"
    )
    args = parser.parse_args()

    url = os.environ.get("NETBOX_URL")
    token = os.environ.get("NETBOX_TOKEN")
    if not args.dry_run and (not url or not token):
        sys.exit("Thiếu NETBOX_URL / NETBOX_TOKEN trong biến môi trường.")

    with open(args.yaml_file, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    devices = data.get("devices", [])
    subnets = data.get("subnets", [])
    print(
        f"Đọc được {len(devices)} thiết bị và {len(subnets)} subnet từ {args.yaml_file}"
    )

    nb = None
    if not args.dry_run:
        nb = pynetbox.api(url, token=token)
        nb.http_session.verify = (
            True  # đổi thành False nếu NetBox dùng cert tự ký (không khuyến khích)
        )

    importer = Importer(nb, dry_run=args.dry_run)

    for d in devices:
        importer.import_device(d)

    # Xử lý subnets SAU devices, vì subnet cần Site đã tồn tại (được tạo ở
    # bước devices) để gán vào Prefix/VLAN.
    for s in subnets:
        importer.import_subnet(s)

    print("\n== Tổng kết ==")
    for k, v in importer.stats.items():
        print(f"{k}: {v}")

    if not args.dry_run:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        manifests_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "manifests"
        )
        os.makedirs(manifests_dir, exist_ok=True)
        manifest_path = os.path.join(manifests_dir, f"netbox_import_manifest_{ts}.json")
        importer.save_manifest(manifest_path)
        print(f"\nNhật ký các object đã tạo: {manifest_path}")
        print("Giữ file này lại — dùng để rollback bằng rollback_netbox.py nếu cần.")


if __name__ == "__main__":
    main()
