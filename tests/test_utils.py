from typing import Dict

import pytest

from cloudpub.utils import get_url_params


@pytest.mark.parametrize(
    "url,params",
    [
        ("https://foo.com/bar", {}),
        ("https://foo.com/bar?foo=bar", {"foo": "bar"}),
        ("https://foo.com/bar?foo=bar", {"foo": "bar"}),
        ("https://foo.com/bar?foo=bar&test=pass", {"foo": "bar", "test": "pass"}),
    ],
)
def test_get_url_params(url: str, params: Dict[str, str]) -> None:
    p = get_url_params(url)
    assert p == params
