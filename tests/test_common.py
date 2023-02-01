from abc import ABC
from typing import Any, Dict

import pytest

from cloudpub.common import BaseService, PublishingMetadata


class TestPublishingMetadata:
    def test_publishing_metadata_with_defaults(self, common_metadata: Dict[str, Any]) -> None:
        m = PublishingMetadata(**common_metadata)
        err_template = "The attribute \"{attribute}\" must default to \"{default}\"."
        assert m.overwrite is False, err_template.format(attribute="overwrite", default="False")
        assert m.keepdraft is False, err_template.format(attribute="keepdraft", default="False")

    @pytest.mark.parametrize(
        "invalid_dict,expected_err",
        [
            ({"architecture": None}, "The parameter \"architecture\" must not be None."),
            ({"destination": None}, "The parameter \"destination\" must not be None."),
            ({"image_path": None}, "The parameter \"image_path\" must not be None."),
        ],
    )
    def test_metadata_invalid(
        self, invalid_dict: Dict[str, str], expected_err: str, common_metadata: Dict[str, Any]
    ) -> None:
        common_metadata.update(invalid_dict)

        with pytest.raises(ValueError, match=expected_err):
            PublishingMetadata(**common_metadata)


class TestBaseService:
    def test_has_publish(self) -> None:
        assert hasattr(BaseService, "publish"), "The abstract method \"publish\" is not defined."

    def test_base_service_abstract(self) -> None:
        assert issubclass(BaseService, ABC), "The BaseService must be a subclass of \"ABC\"."
