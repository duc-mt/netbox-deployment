#!/usr/bin/env bash
set -e

echo "============================================================"
echo "    NetBox Unified Deployment & Bootstrap Script"
echo "============================================================"

# 1. Check for .env file
if [ ! -f .env ]; then
    echo "[!] .env file not found. Creating from .env.example..."
    cp .env.example .env
    
    # Generate a random SECRET_KEY and update .env
    SECRET=$(python3 -c 'import secrets; print(secrets.token_urlsafe(50))')
    if [ "$(uname)" = "Darwin" ]; then
        sed -i '' "s/replace-me-with-a-secure-secret-key/${SECRET}/g" .env
    else
        sed -i "s/replace-me-with-a-secure-secret-key/${SECRET}/g" .env
    fi
    echo "[+] Generated new SECRET_KEY in .env"
    echo "[!] Please review .env if you wish to change default passwords before proceeding."
    echo "    Run ./deploy.sh again when you are ready."
    exit 0
fi

# 2. Build automation container
echo "[+] Building automation container..."
docker compose build automation

# 3. Bring up the stack
echo "[+] Starting NetBox stack (postgres, redis, netbox, worker)..."
docker compose up -d

# 4. Wait for NetBox API to be ready
echo "[+] Waiting for NetBox to become healthy (this may take a few minutes for initial DB migrations)..."
# We loop until the netbox container reports healthy
until [ "`docker inspect -f {{.State.Health.Status}} $(docker compose ps -q netbox)`" == "healthy" ]; do
    sleep 5
    echo -n "."
done
echo " [OK]"

# Load environment variables
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Set default values if not defined in .env
SUPERUSER_NAME=${SUPERUSER_NAME:-admin}
SUPERUSER_EMAIL=${SUPERUSER_EMAIL:-admin@example.com}
SUPERUSER_PASSWORD=${SUPERUSER_PASSWORD:-admin}
SUPERUSER_API_TOKEN=${SUPERUSER_API_TOKEN:-0123456789abcdef0123456789abcdef01234567}

# 5. Create superuser
echo "[+] Creating initial superuser (${SUPERUSER_NAME})..."
# We inject a script to create superuser if it doesn't exist
docker compose exec -T netbox /opt/netbox/venv/bin/python /opt/netbox/netbox/manage.py shell -c "
from django.contrib.auth import get_user_model;
User = get_user_model();
if not User.objects.filter(username='${SUPERUSER_NAME}').exists():
    User.objects.create_superuser('${SUPERUSER_NAME}', '${SUPERUSER_EMAIL}', '${SUPERUSER_PASSWORD}')
    print('Superuser created.')
else:
    print('Superuser already exists.')
"

# 6. Create static API token for automation
echo "[+] Provisioning API token for automation..."
docker compose exec -T netbox /opt/netbox/venv/bin/python /opt/netbox/netbox/manage.py shell -c "
from django.contrib.auth import get_user_model;
from users.models import Token;
User = get_user_model();
user = User.objects.get(username='${SUPERUSER_NAME}');
token_key = '${SUPERUSER_API_TOKEN}'
if not Token.objects.filter(key=token_key).exists():
    Token.objects.create(user=user, key=token_key)
    print('Token created.')
else:
    print('Token already exists.')
"

# 6.5 Import Device Templates from Community Library
echo "[+] Syncing NetBox Community Device Type Library..."
if [ ! -d "automation/Device-Type-Library-Import" ]; then
    git clone https://github.com/netbox-community/devicetype-library-import.git automation/Device-Type-Library-Import
fi

echo "[+] Running community template importer for common vendors..."
docker compose run --rm \
    -e REPO_URL="https://github.com/netbox-community/devicetype-library.git" \
    -e REPO_BRANCH="master" \
    automation python Device-Type-Library-Import/nb-dt-import.py --vendors Cisco Juniper Ubiquiti CheckPoint Fortinet Linksys Draytek TP-Link Hikvision Zyxel 3Com Planet

# 7. Seed data via automation container
if [ -f automation/data/inventory.yaml ]; then
    echo "[+] Seeding initial data from automation/data/inventory.yaml..."
    docker compose run --rm automation python netbox_import.py data/inventory.yaml
else
    echo "[-] No automation/data/inventory.yaml found. Skipping data import."
fi

echo "============================================================"
echo "Deployment Complete!"
echo "NetBox is available at http://localhost:8080"
echo "Login: admin / admin"
echo "============================================================"
