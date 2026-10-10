"""
==============================================================================
Module Name:   test_config.py
Description:   Implementation and logic for test_config.
Author:        Mai Tan Duc <ducmai.network@gmail.com>
Created:       2026-10-10
Version:       1.0.0
License:       MIT
==============================================================================
Usage:         python3 test_config.py [options]
Notes:         Requires Python 3.8+
==============================================================================
"""
LOGGING = {"version": 1, "disable_existing_loggers": True}

PLUGINS = [
    "netbox.tests.dummy_plugin",
]

ALLOW_TOKEN_RETRIEVAL = True

DEFAULT_PERMISSIONS = {}

API_TOKEN_PEPPERS = {
    1: "TEST-VALUE-DO-NOT-USE-TEST-VALUE-DO-NOT-USE-TEST-VALUE-DO-NOT-USE",
}

RQ = {
    "COMMIT_MODE": "auto",
}
