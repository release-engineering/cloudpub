import logging

import pytest
from _pytest.logging import LogCaptureFixture
from attrs import define

from cloudpub.models.common import AttrsJSONDecodeMixin


def test_decode_invalid_json(caplog: LogCaptureFixture) -> None:
    expected_err = "Got an unsupported JSON type: \"<class 'str'>\". Expected: \"<class 'dict'>\'"

    with caplog.at_level(logging.ERROR):
        with pytest.raises(ValueError, match=expected_err):
            AttrsJSONDecodeMixin.from_json("invalid")
        assert expected_err in caplog.text


def test_invalid_to_json(caplog: LogCaptureFixture) -> None:
    class TestCls(int):
        pass

    @define
    class TestAttrsCls(AttrsJSONDecodeMixin):
        test_cls: object

    expected_warning = (
        "Not converting the object "
        "\"<class 'tests.test_models.test_invalid_to_json.<locals>.TestCls'>\""
        " with value \"3\" to JSON"
    )

    test_attrs = TestAttrsCls(test_cls=TestCls(3))

    with caplog.at_level(logging.WARNING):
        _ = test_attrs.to_json()
        assert expected_warning in caplog.text
