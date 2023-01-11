import logging

import pytest
from _pytest.logging import LogCaptureFixture

from cloudpub.models.common import AttrsJSONDecodeMixin


def test_decode_invalid_json(caplog: LogCaptureFixture) -> None:
    expected_err = "Got an unsupported JSON type: \"<class 'str'>\". Expected: \"<class 'dict'>\'"

    with caplog.at_level(logging.ERROR):
        with pytest.raises(ValueError, match=expected_err):
            AttrsJSONDecodeMixin.from_json("invalid")
        assert expected_err in caplog.text
