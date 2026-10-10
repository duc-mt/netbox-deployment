"""
==============================================================================
Module Name:   granian.py
Description:   Source module granian.py.
Author:        Mai Tan Duc <ducmai.network@gmail.com>
Created:       2026-10-10
Version:       1.0.0
License:       MIT
==============================================================================
Usage:         python3 granian.py [options]
Notes:         Requires Python 3.8+
==============================================================================
"""

from granian.utils.proxies import wrap_wsgi_with_proxy_headers
from netbox.wsgi import application

application = wrap_wsgi_with_proxy_headers(
    application,
    trusted_hosts=[
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "fc00::/7",
        "fe80::/10",
    ],
)
