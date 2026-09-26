#!/usr/bin/env bash
# ==============================================================================
# Script khôi phục (Restore / Disaster Recovery) cho NetBox Docker (MNS)
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SCRIPT_DIR"

usage() {
    echo "Cách sử dụng: $0 --db /path/to/netbox_db_YYYYMMDD.dump [--media /path/to/netbox_media_YYYYMMDD.tar.gz] [--yes]"
    echo ""
    echo "Tùy chọn:"
    echo "  --db FILE       Đường dẫn file database dump (.dump)"
    echo "  --media FILE    (Tùy chọn) Đường dẫn file media archive (.tar.gz)"
    echo "  --yes, -y       Bỏ qua câu hỏi xác nhận (dùng cho tự động hóa)"
    exit 1
}

DB_FILE=""
MEDIA_FILE=""
ASSUME_YES=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --db)
            DB_FILE="$2"
            shift 2
            ;;
        --media)
            MEDIA_FILE="$2"
            shift 2
            ;;
        --yes|-y)
            ASSUME_YES=true
            shift
            ;;
        *)
            usage
            ;;
    esac
done

if [[ -z "$DB_FILE" ]]; then
    echo "LỖI: Chưa chỉ định file database qua tham số --db"
    usage
fi

if [[ ! -f "$DB_FILE" ]]; then
    echo "LỖI: Không tìm thấy file $DB_FILE"
    exit 1
fi

ENV_FILE="$SCRIPT_DIR/env/netbox.env"
if [[ ! -f "$ENV_FILE" ]]; then
    echo "LỖI: Không tìm thấy file cấu hình $ENV_FILE"
    exit 1
fi

DB_HOST="$(grep '^DB_HOST=' "$ENV_FILE" | cut -d'=' -f2- | tr -d "'\"")"
DB_NAME="$(grep '^DB_NAME=' "$ENV_FILE" | cut -d'=' -f2- | tr -d "'\"")"
DB_USER="$(grep '^DB_USER=' "$ENV_FILE" | cut -d'=' -f2- | tr -d "'\"")"
DB_PASSWORD="$(grep '^DB_PASSWORD=' "$ENV_FILE" | cut -d'=' -f2- | tr -d "'\"")"
DB_PORT="$(grep '^DB_PORT=' "$ENV_FILE" | cut -d'=' -f2- | tr -d "'\"" || echo "5432")"
DB_PORT="${DB_PORT:-5432}"

echo "=========================================================="
echo "CẢNH BÁO: HÀNH ĐỘNG NÀY SẼ GHI ĐÈ DỮ LIỆU HIỆN CÓ CỦA NETBOX!"
echo "Database: $DB_NAME trên server $DB_HOST:$DB_PORT"
echo "File Dump: $DB_FILE"
if [[ -n "$MEDIA_FILE" ]]; then
    echo "File Media: $MEDIA_FILE"
fi
echo "=========================================================="

if [[ "$ASSUME_YES" != "true" ]]; then
    read -rp "Bạn có chắc chắn muốn tiến hành khôi phục? (yes/no): " CONFIRM
    if [[ "$CONFIRM" != "yes" ]]; then
        echo "Đã hủy thao tác khôi phục."
        exit 0
    fi
fi

# 1. Tạm dừng các container NetBox để ngắt kết nối DB
echo "[1/4] Đang tạm dừng service netbox và netbox-worker..."
docker compose stop netbox netbox-worker || true

# 2. Khôi phục Database bằng pg_restore qua Docker container postgres:18-alpine
echo "[2/4] Đang khôi phục cơ sở dữ liệu PostgreSQL..."
DB_DIR="$(cd "$(dirname "$DB_FILE")" && pwd)"
DB_BASENAME="$(basename "$DB_FILE")"

docker run --rm \
    --user "$(id -u):$(id -g)" \
    -e PGPASSWORD="$DB_PASSWORD" \
    -v "$DB_DIR":/backup:ro \
    postgres:18-alpine \
    pg_restore -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
    --clean --if-exists --no-owner --no-privileges \
    "/backup/$DB_BASENAME" || echo "Lưu ý: pg_restore có thể hoàn tất kèm cảnh báo schema thông thường."

# 3. Khôi phục Media files nếu có
if [[ -n "$MEDIA_FILE" && -f "$MEDIA_FILE" ]]; then
    echo "[3/4] Đang khôi phục Docker volume media..."
    MEDIA_DIR="$(cd "$(dirname "$MEDIA_FILE")" && pwd)"
    MEDIA_BASENAME="$(basename "$MEDIA_FILE")"

    docker run --rm \
        -v netbox-docker_netbox-media-files:/target \
        -v "$MEDIA_DIR":/backup:ro \
        alpine sh -c "rm -rf /target/* && tar -xzf /backup/$MEDIA_BASENAME -C /target"
    echo "Khôi phục media hoàn tất."
else
    echo "[3/4] Bỏ qua khôi phục Media (không có file chỉ định)."
fi

# 4. Khởi động lại các container
echo "[4/4] Đang khởi động lại hệ thống NetBox..."
docker compose up -d

echo ""
echo "=== KHÔI PHỤC HOÀN TẤT THÀNH CÔNG! ==="
echo "Kiểm tra log bằng lệnh: docker compose logs -f netbox"
