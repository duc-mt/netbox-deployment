#!/usr/bin/env bash
# ==============================================================================
# Script sao lưu tự động cho hệ thống NetBox Docker (MNS Deployment)
# - Database PostgreSQL: Sử dụng container postgres:18-alpine (tương thích 100% với PostgreSQL 18 trên 192.168.20.11)
# - Media files: Sao lưu Docker volume netbox-docker_netbox-media-files
# - Cấu hình: Sao lưu env/netbox.env và docker-compose.override.yml
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SCRIPT_DIR"

BACKUP_DIR="${BACKUP_DIR:-/home/duc.mt/backup/netbox}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
DATE="$(date +%Y%m%d_%H%M%S)"
LOG_FILE="$BACKUP_DIR/backup.log"

# Tạo cấu trúc thư mục lưu trữ
mkdir -p "$BACKUP_DIR/db" "$BACKUP_DIR/media" "$BACKUP_DIR/config"

log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    echo "$msg"
    echo "$msg" >> "$LOG_FILE"
}

log "=== Bắt đầu sao lưu hệ thống NetBox ($DATE) ==="

# 1. Đọc cấu hình từ env/netbox.env
ENV_FILE="$SCRIPT_DIR/env/netbox.env"
if [[ ! -f "$ENV_FILE" ]]; then
    log "LỖI: Không tìm thấy file cấu hình $ENV_FILE"
    exit 1
fi

DB_HOST="$(grep '^DB_HOST=' "$ENV_FILE" | cut -d'=' -f2- | tr -d "'\"")"
DB_NAME="$(grep '^DB_NAME=' "$ENV_FILE" | cut -d'=' -f2- | tr -d "'\"")"
DB_USER="$(grep '^DB_USER=' "$ENV_FILE" | cut -d'=' -f2- | tr -d "'\"")"
DB_PASSWORD="$(grep '^DB_PASSWORD=' "$ENV_FILE" | cut -d'=' -f2- | tr -d "'\"")"
DB_PORT="$(grep '^DB_PORT=' "$ENV_FILE" | cut -d'=' -f2- | tr -d "'\"" || echo "5432")"
DB_PORT="${DB_PORT:-5432}"

# 2. Sao lưu Database PostgreSQL bằng Docker container postgres:18-alpine
DB_BACKUP_FILE="$BACKUP_DIR/db/netbox_db_${DATE}.dump"
log "Đang sao lưu PostgreSQL database ($DB_NAME trên $DB_HOST:$DB_PORT)..."

if docker run --rm \
    --user "$(id -u):$(id -g)" \
    -e PGPASSWORD="$DB_PASSWORD" \
    -v "$BACKUP_DIR/db":/backup \
    postgres:18-alpine \
    pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -F c -b -f "/backup/netbox_db_${DATE}.dump"; then
    
    DB_SIZE="$(du -h "$DB_BACKUP_FILE" | cut -f1)"
    log "Sao lưu DB thành công: $DB_BACKUP_FILE (Dung lượng: $DB_SIZE)"
else
    log "LỖI: Sao lưu Database thất bại!"
    exit 1
fi

# 3. Sao lưu Docker Volume Media files
MEDIA_BACKUP_FILE="$BACKUP_DIR/media/netbox_media_${DATE}.tar.gz"
log "Đang sao lưu Docker volume media files..."

if docker run --rm \
    --user "$(id -u):$(id -g)" \
    -v netbox-docker_netbox-media-files:/source:ro \
    -v "$BACKUP_DIR/media":/backup \
    alpine tar -czf "/backup/netbox_media_${DATE}.tar.gz" -C /source . ; then
    
    MEDIA_SIZE="$(du -h "$MEDIA_BACKUP_FILE" | cut -f1)"
    log "Sao lưu Media thành công: $MEDIA_BACKUP_FILE (Dung lượng: $MEDIA_SIZE)"
else
    log "CẢNH BÁO: Sao lưu Media volume thất bại."
fi

# 4. Sao lưu File cấu hình nhạy cảm (netbox.env, docker-compose.override.yml)
CONFIG_BACKUP_FILE="$BACKUP_DIR/config/netbox_config_${DATE}.tar.gz"
log "Đang sao lưu file cấu hình..."
tar -czf "$CONFIG_BACKUP_FILE" -C "$SCRIPT_DIR" \
    env/netbox.env \
    docker-compose.override.yml \
    2>/dev/null || true

chmod 600 "$CONFIG_BACKUP_FILE"
CONFIG_SIZE="$(du -h "$CONFIG_BACKUP_FILE" | cut -f1)"
log "Sao lưu Config thành công: $CONFIG_BACKUP_FILE (Dung lượng: $CONFIG_SIZE)"

# 5. Dọn dẹp bản sao lưu cũ theo chính sách lưu trữ (Retention)
log "Đang dọn dẹp các bản sao lưu cũ hơn $RETENTION_DAYS ngày..."
find "$BACKUP_DIR/db" -type f -name "netbox_db_*.dump" -mtime +"$RETENTION_DAYS" -delete
find "$BACKUP_DIR/media" -type f -name "netbox_media_*.tar.gz" -mtime +"$RETENTION_DAYS" -delete
find "$BACKUP_DIR/config" -type f -name "netbox_config_*.tar.gz" -mtime +"$RETENTION_DAYS" -delete

log "=== Quá trình sao lưu hoàn tất thành công! ==="
