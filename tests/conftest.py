from typing import Any, Dict

import pytest


@pytest.fixture
def common_metadata() -> Dict[str, Any]:
    return {
        "image_path": "/foo/bar/image.img",
        "architecture": "x86_64",
        "destination": "destination",
    }
