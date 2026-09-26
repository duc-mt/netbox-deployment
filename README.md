# NetBox Unified Deployment

[![CI Pipeline](https://github.com/duc-mt/netbox-deployment/actions/workflows/ci.yml/badge.svg)](https://github.com/duc-mt/netbox-deployment/actions/workflows/ci.yml)
[![Python Version](https://img.shields.io/badge/python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12-blue)](https://pypi.org/project/netbox-deployment/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

This repository provides a self-contained, highly portable deployment for **NetBox**, combining the standard Docker deployment with custom data import/export automation scripts. It is designed to be easily deployed in any new environment.

## 🚀 Quick Start

The easiest way to get started from zero to a fully seeded NetBox instance is using the provided deployment script.

```bash
# 1. Run the deploy script to generate a .env file and secrets
./deploy.sh

# 2. Review the generated .env file and change default credentials
# (e.g., Database passwords, SUPERUSER_NAME, SUPERUSER_PASSWORD, SUPERUSER_API_TOKEN)
nano .env

# 3. Run the script again to bring up the stack and seed data
./deploy.sh
```

**What the script does:**
- Generates a secure `SECRET_KEY`.
- Brings up the PostgreSQL, Redis, NetBox, and Worker containers.
- Waits for NetBox database migrations to complete.
- Provisions a superuser account and static API token based on your `.env` configuration.
- Syncs the NetBox Community Device Type Library for common hardware templates.
- Seeds the initial infrastructure data by running the automation script against `automation/data/inventory.yaml`.

## 📁 Repository Structure

```text
netbox-deployment/
├── .env.example               # Unified environment variables
├── docker-compose.yml         # Standardized docker-compose setup
├── deploy.sh                  # Bootstrap script
├── automation/                # Python scripts for DCIM & IPAM automation
│   ├── Dockerfile             # Container definition for automation tools
│   ├── netbox_import.py       # Import data from YAML to NetBox
│   ├── export_netbox.py       # Export data from NetBox to YAML
│   ├── rollback_netbox.py     # Rollback imports using generated manifests
│   ├── wipe_netbox.py         # Wipe all DCIM/IPAM data (Use with care!)
│   └── data/
│       └── inventory.yaml     # Initial configuration seed data
└── configuration/             # NetBox specific configurations
```

## 🛠 Using the Automation Tools

The automation tools have been containerized so they can be run securely within the same Docker network as NetBox without requiring local Python installation or credentials parsing. 

To run any script, use `docker compose run --rm automation <command>`.

### 1. Import Data
```bash
docker compose run --rm automation python netbox_import.py data/inventory.yaml
```

### 2. Export Data
```bash
docker compose run --rm automation python export_netbox.py backups/my_backup.yaml
```

### 3. Rollback
```bash
# Preview rollback
docker compose run --rm automation python rollback_netbox.py manifests/manifest_file.json --dry-run
# Execute
docker compose run --rm automation python rollback_netbox.py manifests/manifest_file.json
```

### 4. Wipe Data
⚠️ **WARNING: Action cannot be undone.**
```bash
docker compose run --rm automation python wipe_netbox.py
```

## 🔒 Configuration

All application configurations, database credentials, and automation API tokens are centrally managed in the `.env` file at the root of the project. This makes migrating to a new environment as simple as copying the `.env` file and bringing up the stack.
