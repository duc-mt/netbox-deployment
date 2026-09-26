#!/usr/bin/env bash
# ==============================================================================
# Banner thông báo quyền truy cập & Healthcheck hệ thống Ubuntu + NetBox
# Tự động hiển thị mỗi khi khởi động interactive session (SSH / Bash)
# Maintainer: Mai Tan Duc <duc.mt@cmctelecom.vn>
# ==============================================================================

# Thiết lập mã màu ANSI
BOLD="\033[1m"
RED="\033[1;31m"
GREEN="\033[1;32m"
YELLOW="\033[1;33m"
BLUE="\033[1;34m"
CYAN="\033[1;36m"
WHITE="\033[1;37m"
GRAY="\033[0;90m"
RESET="\033[0m"

# ------------------------------------------------------------------------------
# 1. WARNING & AUTHORIZED ACCESS BANNER
# ------------------------------------------------------------------------------
echo -e "${YELLOW}╔════════════════════════════════════════════════════════════════════════════════╗${RESET}"
echo -e "${YELLOW}║                  ⚠️   CẢNH BÁO: TRUY CẬP CÓ ỦY QUYỀN (RESTRICTED)               ║${RESET}"
echo -e "${YELLOW}║${WHITE}  Hệ thống quản trị hạ tầng mạng nội bộ CMC Telecom (MNS).                      ${YELLOW}║${RESET}"
echo -e "${YELLOW}║${WHITE}  Nghiêm cấm mọi hành vi truy cập trái phép. Toàn bộ phiên làm việc được log.   ${YELLOW}║${RESET}"
echo -e "${YELLOW}║                                                                                ║${RESET}"
echo -e "${YELLOW}║${CYAN}  Chủ quản / Maintainer: ${WHITE}Mai Tan Duc (duc.mt@cmctelecom.vn)                     ${YELLOW}║${RESET}"
echo -e "${YELLOW}║${CYAN}  Bộ phận quản trị:       ${WHITE}Team Hạ tầng MNS - CMC Telecom                        ${YELLOW}║${RESET}"
echo -e "${YELLOW}╚════════════════════════════════════════════════════════════════════════════════╝${RESET}"

# ------------------------------------------------------------------------------
# 2. UBUNTU SYSTEM HEALTHCHECK
# ------------------------------------------------------------------------------
echo -e "\n${BOLD}${BLUE}── [1] TÌNH TRẠNG HỆ ĐIỀU HÀNH UBUNTU ──${RESET}"

# Uptime
UPTIME_STR="$(uptime -p 2>/dev/null | sed 's/up //')"
echo -e "  • ${GRAY}Uptime:${RESET}        ${WHITE}${UPTIME_STR}${RESET}"

# CPU Load & Cores
CORES="$(nproc 2>/dev/null || echo 1)"
read -r LOAD_1 LOAD_5 LOAD_15 _ < /proc/loadavg
LOAD_INT="${LOAD_1%.*}"
if [[ -z "$LOAD_INT" ]]; then LOAD_INT=0; fi

CPU_COLOR="$GREEN"
CPU_STATUS="Bình thường"
if (( LOAD_INT >= CORES * 2 )); then
    CPU_COLOR="$RED"
    CPU_STATUS="QUÁ TẢI NGHIÊM TRỌNG"
elif (( LOAD_INT >= CORES )); then
    CPU_COLOR="$YELLOW"
    CPU_STATUS="Tải cao"
fi
echo -e "  • ${GRAY}CPU Load:${RESET}      ${CPU_COLOR}${LOAD_1}${RESET} (1m), ${LOAD_5} (5m), ${LOAD_15} (15m) / ${CORES} Cores [${CPU_COLOR}${CPU_STATUS}${RESET}]"

# RAM Usage
read -r RAM_USED RAM_TOTAL RAM_PCT <<< "$(free -m | awk '/Mem:/ {print $3, $2, int($3*100/$2)}')"
RAM_COLOR="$GREEN"
RAM_STATUS="Bình thường"
if (( RAM_PCT >= 90 )); then
    RAM_COLOR="$RED"
    RAM_STATUS="SẮP HẾT RAM"
elif (( RAM_PCT >= 80 )); then
    RAM_COLOR="$YELLOW"
    RAM_STATUS="Cảnh báo tải cao"
fi
echo -e "  • ${GRAY}Bộ nhớ RAM:${RESET}    ${RAM_COLOR}${RAM_USED} MB / ${RAM_TOTAL} MB (${RAM_PCT}%)${RESET} [${RAM_COLOR}${RAM_STATUS}${RESET}]"

# Disk Usage
read -r DISK_USED DISK_TOTAL DISK_PCT <<< "$(df -h / | awk 'NR==2 {gsub("%","",$5); print $3, $2, $5}')"
DISK_COLOR="$GREEN"
DISK_STATUS="Bình thường"
if (( DISK_PCT >= 90 )); then
    DISK_COLOR="$RED"
    DISK_STATUS="SẮP ĐẦY Ổ CỨNG"
elif (( DISK_PCT >= 80 )); then
    DISK_COLOR="$YELLOW"
    DISK_STATUS="Cảnh báo dung lượng"
fi
echo -e "  • ${GRAY}Ổ cứng (/):${RESET}    ${DISK_COLOR}${DISK_USED} / ${DISK_TOTAL} (${DISK_PCT}%)${RESET} [${DISK_COLOR}${DISK_STATUS}${RESET}]"

# ------------------------------------------------------------------------------
# 3. NETBOX STACK & SERVICES HEALTHCHECK
# ------------------------------------------------------------------------------
echo -e "\n${BOLD}${CYAN}── [2] TÌNH TRẠNG DỊCH VỤ NETBOX DOCKER ──${RESET}"

DOCKER_DIR="/home/duc.mt/netbox-docker"
ISSUES=()

# Kiểm tra Docker daemon
if systemctl is-active --quiet docker; then
    echo -e "  • ${GRAY}Docker Daemon:${RESET}    ${GREEN}● Đang hoạt động (active)${RESET}"
else
    echo -e "  • ${GRAY}Docker Daemon:${RESET}    ${RED}✖ ĐÃ DỪNG HOẠT ĐỘNG${RESET}"
    ISSUES+=("Docker daemon đang tắt")
fi

# Kiểm tra kết nối tới PostgreSQL ngoài (192.168.20.11:5432)
if timeout 1 bash -c "</dev/tcp/192.168.20.11/5432" 2>/dev/null; then
    echo -e "  • ${GRAY}PostgreSQL DB:${RESET}    ${GREEN}● Kết nối tốt (192.168.20.11:5432)${RESET}"
else
    echo -e "  • ${GRAY}PostgreSQL DB:${RESET}    ${RED}✖ KHÔNG THỂ KẾT NỐI (192.168.20.11:5432)${RESET}"
    ISSUES+=("Không thể kết nối PostgreSQL tại 192.168.20.11:5432")
fi

# Kiểm tra HTTP response của Netbox Web
HTTP_CODE="$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 2 http://127.0.0.1:8080/ 2>/dev/null || echo "000")"
if [[ "$HTTP_CODE" =~ ^(200|301|302)$ ]]; then
    echo -e "  • ${GRAY}NetBox Web HTTP:${RESET}  ${GREEN}● Phản hồi tốt (HTTP $HTTP_CODE)${RESET}"
else
    echo -e "  • ${GRAY}NetBox Web HTTP:${RESET}  ${RED}✖ LỖI PHẢN HỒI (Mã HTTP: $HTTP_CODE)${RESET}"
    ISSUES+=("NetBox Web không phản hồi HTTP hợp lệ (Code: $HTTP_CODE)")
fi

# Kiểm tra trạng thái từng container trong compose
echo -e "  • ${GRAY}Container Stack:${RESET}"
SERVICES=("netbox" "netbox-worker" "redis" "redis-cache")
for svc in "${SERVICES[@]}"; do
    STATUS_LINE="$(docker compose -f "$DOCKER_DIR/docker-compose.yml" ps "$svc" --format '{{.Status}}' 2>/dev/null || true)"
    if [[ -z "$STATUS_LINE" ]]; then
        echo -e "      - ${svc}: ${RED}✖ Không tìm thấy / Chưa khởi động${RESET}"
        ISSUES+=("Service $svc chưa chạy")
    elif [[ "$STATUS_LINE" == *"healthy"* ]]; then
        echo -e "      - ${svc}: ${GREEN}● ${STATUS_LINE}${RESET}"
    elif [[ "$STATUS_LINE" == *"starting"* ]]; then
        echo -e "      - ${svc}: ${YELLOW}⟳ Đang khởi động (${STATUS_LINE})${RESET}"
        ISSUES+=("Service $svc đang khởi động/chưa sẵn sàng")
    else
        echo -e "      - ${svc}: ${RED}✖ LỖI / BẤT THƯỜNG (${STATUS_LINE})${RESET}"
        ISSUES+=("Service $svc gặp sự cố: $STATUS_LINE")
    fi
done

# Kiểm tra bản backup gần nhất
LATEST_BACKUP="$(find /home/duc.mt/backup/netbox/db -type f -name "netbox_db_*.dump" -printf "%T@ %Tc %p\n" 2>/dev/null | sort -n | tail -1)"
if [[ -n "$LATEST_BACKUP" ]]; then
    BACKUP_EPOCH="$(echo "$LATEST_BACKUP" | awk '{print int($1)}')"
    NOW_EPOCH="$(date +%s)"
    HOURS_AGO="$(( (NOW_EPOCH - BACKUP_EPOCH) / 3600 ))"
    BACKUP_TIME_STR="$(echo "$LATEST_BACKUP" | awk '{$1=""; $NF=""; print $0}' | sed 's/^[ \t]*//')"
    
    if (( HOURS_AGO > 36 )); then
        echo -e "  • ${GRAY}Backup Netbox DB:${RESET}    ${YELLOW}⚠️  ${BACKUP_TIME_STR} (${HOURS_AGO} giờ trước - Cần kiểm tra cronjob!)${RESET}"
        ISSUES+=("Bản sao lưu Netbox DB gần nhất đã quá 36 giờ (${HOURS_AGO}h)")
    else
        echo -e "  • ${GRAY}Backup Netbox DB:${RESET}    ${GREEN}● ${BACKUP_TIME_STR} (${HOURS_AGO} giờ trước)${RESET}"
    fi
else
    echo -e "  • ${GRAY}Backup Netbox DB:${RESET}    ${RED}✖ Chưa có bản sao lưu nào!${RESET}"
    ISSUES+=("Chưa phát hiện bản sao lưu Netbox DB nào trong /home/duc.mt/backup/netbox/db")
fi

# Kiểm tra bản backup Inventory gần nhất
LATEST_INV_BACKUP="$(find /home/duc.mt/import_netbox/import_automation/backups -type f -name "inventory_backup_*.yaml" -printf "%T@ %Tc %p\n" 2>/dev/null | sort -n | tail -1)"
if [[ -n "$LATEST_INV_BACKUP" ]]; then
    INV_BACKUP_EPOCH="$(echo "$LATEST_INV_BACKUP" | awk '{print int($1)}')"
    NOW_EPOCH="$(date +%s)"
    INV_HOURS_AGO="$(( (NOW_EPOCH - INV_BACKUP_EPOCH) / 3600 ))"
    INV_BACKUP_TIME_STR="$(echo "$LATEST_INV_BACKUP" | awk '{$1=""; $NF=""; print $0}' | sed 's/^[ \t]*//')"
    
    if (( INV_HOURS_AGO > 36 )); then
        echo -e "  • ${GRAY}Backup Inventory:${RESET}    ${YELLOW}⚠️  ${INV_BACKUP_TIME_STR} (${INV_HOURS_AGO} giờ trước - Cần kiểm tra cronjob!)${RESET}"
        ISSUES+=("Bản sao lưu Inventory gần nhất đã quá 36 giờ (${INV_HOURS_AGO}h)")
    else
        echo -e "  • ${GRAY}Backup Inventory:${RESET}    ${GREEN}● ${INV_BACKUP_TIME_STR} (${INV_HOURS_AGO} giờ trước)${RESET}"
    fi
else
    echo -e "  • ${GRAY}Backup Inventory:${RESET}    ${RED}✖ Chưa có bản sao lưu nào!${RESET}"
    ISSUES+=("Chưa phát hiện bản sao lưu Inventory nào trong /home/duc.mt/import_netbox/import_automation/backups")
fi

# ------------------------------------------------------------------------------
# 4. TỔNG KẾT TRẠNG THÁI (SUMMARY BANNER)
# ------------------------------------------------------------------------------
echo ""
if [[ ${#ISSUES[@]} -eq 0 ]]; then
    echo -e "${GREEN}✔ TẤT CẢ DỊCH VỤ HOẠT ĐỘNG BÌNH THƯỜNG - KHÔNG PHÁT HIỆN CAO TẢI HOẶC TREO DỊCH VỤ${RESET}"
else
    echo -e "${RED}✖ CẢNH BÁO PHÁT HIỆN ${#ISSUES[@]} VẤN ĐỀ CẦN KIỂM TRA:${RESET}"
    for issue in "${ISSUES[@]}"; do
        echo -e "   ${RED}▶ ${issue}${RESET}"
    done
fi
echo -e "${GRAY}────────────────────────────────────────────────────────────────────────────────${RESET}\n"
