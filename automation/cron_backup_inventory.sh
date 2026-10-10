#!/bin/bash
# ==============================================================================
# Script Name:   cron_backup_inventory.sh
# Description:   Implementation and logic for cron_backup_inventory.
# Author:        Mai Tan Duc <ducmai.network@gmail.com>
# Created:       2026-10-10
# Version:       1.0.0
# License:       MIT
# ==============================================================================
# Usage:         ./cron_backup_inventory.sh [options] [arguments]
# Notes:         Automated bash utility script
# ==============================================================================

# Load environment variables (NETBOX_URL, NETBOX_TOKEN)
source /home/duc.mt/.bashrc

# Activate virtual environment
source /home/duc.mt/import_netbox/env/bin/activate

# Go to script directory
cd /home/duc.mt/import_netbox/import_automation

# Ensure directories exist
mkdir -p backups logs data manifests

# Run the export script and save as daily backup
python3 export_netbox.py "backups/inventory_backup_$(date +%Y%m%d).yaml" >> logs/cron_backup.log 2>&1

# Xóa các file backup inventory cũ hơn 30 ngày để tránh đầy ổ cứng
find /home/duc.mt/import_netbox/import_automation/backups -name "inventory_backup_*.yaml" -type f -mtime +30 -exec rm -f {} \; >> logs/cron_backup.log 2>&1
