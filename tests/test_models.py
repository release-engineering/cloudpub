import logging

import pytest
from _pytest.logging import LogCaptureFixture
from attrs import define, field

from cloudpub.models.common import AttrsJSONDecodeMixin


@define
class FooClass(AttrsJSONDecodeMixin):
    foo: str = field(metadata={"const": "FIXED_VALUE"})
    bar: str


def test_decode_invalid_json(caplog: LogCaptureFixture) -> None:
    expected_err = "Got an unsupported JSON type: \"<class 'str'>\". Expected: \"<class 'dict'>\'"

    with caplog.at_level(logging.ERROR):
        with pytest.raises(ValueError, match=expected_err):
            AttrsJSONDecodeMixin.from_json("invalid")
        assert expected_err in caplog.text


def test_constant():
    test_data = {
        "foo": "bar",
        "bar": "foo",
    }

    a = FooClass.from_json(test_data)

    assert a.foo == "FIXED_VALUE"
    assert a.bar == "foo"
