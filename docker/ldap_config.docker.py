"""
==============================================================================
Module Name:   ldap_config.docker.py
Description:   Implementation and logic for ldap_config.docker.
Author:        Mai Tan Duc <ducmai.network@gmail.com>
Created:       2026-10-10
Version:       1.0.0
License:       MIT
==============================================================================
Usage:         python3 ldap_config.docker.py [options]
Notes:         Requires Python 3.8+
==============================================================================
"""
from .configuration import read_configurations

_loaded_configurations = read_configurations(
    config_dir="/etc/netbox/config/ldap/",
    config_module="netbox.configuration.ldap",
    main_config="ldap_config",
)


def __getattr__(name):
    for config in _loaded_configurations:
        try:
            return getattr(config, name)
        except Exception:
            pass
    raise AttributeError


def __dir__():
    names = []
    for config in _loaded_configurations:
        names.extend(config.__dir__())
    return names
