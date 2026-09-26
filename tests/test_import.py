import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from automation.netbox_import import slugify


def test_slugify():
    assert slugify("Test Device!") == "test-device"
    assert slugify("Some String With Spaces") == "some-string-with-spaces"
    assert slugify("Already-slugified") == "already-slugified"

def test_get_or_create():
    # Simple mock for get_or_create logic if needed, skipped for now to just get base coverage
    pass
