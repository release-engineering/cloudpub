import logging
from operator import attrgetter
from typing import Any, Dict

import pytest
from _pytest.logging import LogCaptureFixture

from cloudpub.models.ms_azure import (
    ConfigureStatus,
    DiskVersion,
    VMImageDefinition,
    VMImageSource,
    VMIPlanTechConfig,
)
from cloudpub.ms_azure.utils import (
    AzurePublishingMetadata,
    create_disk_version_from_scratch,
    get_image_type_mapping,
    is_azure_job_not_complete,
    is_disk_version_gt,
    is_sas_present,
    prepare_vm_images,
    update_skus,
)


@pytest.mark.parametrize(
    "status",
    [
        {"jobStatus": "completed", "jobId": 'job-id'},
        {"jobStatus": "incomplete", "jobId": 1},
        {"jobStatus": "whatever", "jobId": "test"},
    ],
)
def test_is_job_not_complete(
    status: Dict[str, Any], caplog: LogCaptureFixture, job_details_not_started: Dict[str, Any]
) -> None:
    with caplog.at_level(logging.DEBUG):
        job_details_not_started.update(status)
        job_details = ConfigureStatus.from_json(job_details_not_started)
        res = is_azure_job_not_complete(job_details)

        assert f"Checking if the job \"{job_details.job_id}\" is still running" in caplog.text
        assert f"job {job_details.job_id} is in {job_details.job_status} state" in caplog.text

        if job_details.job_status != "completed":
            assert res is True
        else:
            assert res is False


class TestAzurePublishingMetadata:
    def test_metadata_with_defaults(self, metadata_azure: Dict[str, Any]) -> None:
        # Test for generation 2 without legacy support
        m = AzurePublishingMetadata(**metadata_azure)
        plan_name = metadata_azure["destination"].split("/")[-1]
        err_template = "The attribute \"{attribute}\" must default to \"{default}\"."
        assert m.sku_id == plan_name, err_template.format(attribute="sku_id", default=plan_name)
        assert m.recommended_sizes == [], err_template.format(
            attribute="recommended_sizes", default="[]"
        )
        assert not m.legacy_sku_id, "The attribute \"legacy_sku_id\" must not be set."

        # Test for generation 2 with legacy support
        metadata_azure.update({"support_legacy": True})
        m = AzurePublishingMetadata(**metadata_azure)
        assert m.legacy_sku_id == f"{plan_name}-gen1", err_template.format(
            attribute="legacy_sku_id", default=f"{plan_name}-gen1"
        )

        # Test for generation 1
        metadata_azure.update({"generation": "V1"})
        m = AzurePublishingMetadata(**metadata_azure)
        assert not m.legacy_sku_id, "The attribute \"legacy_sku_id\" must not be set."

    @pytest.mark.parametrize(
        "invalid_dict,expected_err",
        [
            ({"generation": "foo"}, "Invalid generation \"foo\". Expected: \"V1\" or \"V2\"."),
            ({"image_path": "foo"}, "Invalid SAS URI \"foo\". Expected: http/https URL"),
            ({"image_path": None}, "The parameter \"image_path\" must not be None."),
            ({"generation": None}, "The parameter \"generation\" must not be None."),
        ],
    )
    def test_metadata_invalid(
        self, invalid_dict: Dict[str, str], expected_err: str, metadata_azure: Dict[str, Any]
    ):
        metadata_azure.update(invalid_dict)

        with pytest.raises(ValueError, match=expected_err):
            AzurePublishingMetadata(**metadata_azure)


class TestAzureUtils:
    @pytest.mark.parametrize(
        "val1,val2,expected",
        [
            ("1.0.0", "0.5.0", True),
            ("1.1.0", "1.0.0", True),
            ("1.0.0", "2.0.0", False),
            ("1.1.0", "1.9.1", False),
        ],
    )
    def test_is_disk_version_gt(self, val1: str, val2: str, expected: bool) -> None:
        assert is_disk_version_gt(val1, val2) == expected

    @pytest.mark.parametrize(
        "val1,val2",
        [
            ("1.", "0"),
            ("1.0", "1"),
            ("1.0.0", "1.0"),
            ("1.0.0.0", "1.0.0"),
        ],
    )
    def test_is_disk_version_gt_raises_format(self, val1: str, val2: str) -> None:
        expected_err = (
            "Invalid format. "
            "Expecting to receive \"\\(int\\)\\.\\(int\\)\\.\\(int\\)\""
            " Got \"%s\" - \"%s" % (val1, val2)
        )
        with pytest.raises(ValueError, match=expected_err):
            is_disk_version_gt(val1, val2)

    @pytest.mark.parametrize(
        "val1,val2",
        [
            ("1", ""),
            ("a", "1"),
            ("1.0.0", "1.0.b"),
        ],
    )
    def test_is_disk_version_gt_raises_noint(self, val1: str, val2: str) -> None:
        expected_err = "invalid literal for int\\(\\) with base 10:"
        with pytest.raises(ValueError, match=expected_err):
            is_disk_version_gt(val1, val2)

    def test_get_image_type_mapping(self, metadata_azure_obj: AzurePublishingMetadata) -> None:
        # Test Gen1
        res = get_image_type_mapping(metadata_azure_obj.architecture, "V1")
        assert res == "x64Gen1"

        # Test Gen2
        res = get_image_type_mapping(metadata_azure_obj.architecture, "V2")
        assert res == "x64Gen2"

    @pytest.mark.parametrize(
        "sas1,sas2,expected",
        [
            ("https://foo.com/bar", "https://foo.com/bar?foo=bar", False),
            ("https://foo.com/bar?foo=bar&st=aaaaa", "https://foo.com/bar?foo=bar&st=bbb", True),
            (
                "https://foo.com/bar?foo=bar&st=a&se=b&sig=c&bar=foo",
                "https://foo.com/bar?foo=bar&st=d&se=e&sig=f&bar=foo",
                True,
            ),
            (
                "https://foo.com/bar?foo=bar&st=a&se=b&sig=c&bar=foo",
                "https://foo.com/bar?foo=foo&st=d&se=e&sig=f",
                False,
            ),
            ("https://foo.com/bar?foo=bar&st=aaaaa", "https://bar.com/foo?foo=bar&st=bbb", False),
        ],
    )
    def test_is_sas_present(
        self, sas1: str, sas2: str, expected: bool, disk_version_obj: DiskVersion
    ) -> None:
        # Test positive
        disk_version_obj.vm_images[0].source.os_disk.uri = sas1

        res = is_sas_present(disk_version=disk_version_obj, sas_uri=sas2)
        assert res is expected

    def test_prepare_vm_images_gen1(
        self,
        metadata_azure_obj: AzurePublishingMetadata,
        gen1_image_obj: VMImageDefinition,
        gen2_image_obj: VMImageDefinition,
    ) -> None:
        metadata_azure_obj.generation = "V1"
        new_source = VMImageSource.from_json(
            {
                "sourceType": "sasUri",
                "osDisk": {"uri": "https://foo.com/bar"},
                "dataDisks": [],
            }
        )
        gen1_image_obj.source = new_source
        res = prepare_vm_images(
            metadata=metadata_azure_obj, gen1=gen1_image_obj, gen2=gen2_image_obj, source=new_source
        )
        assert res == [gen1_image_obj]

    def test_prepare_vm_images_gen2(
        self,
        metadata_azure_obj: AzurePublishingMetadata,
        gen1_image_obj: VMImageDefinition,
        gen2_image_obj: VMImageDefinition,
    ) -> None:
        metadata_azure_obj.generation = "V2"
        new_source = VMImageSource.from_json(
            {
                "sourceType": "sasUri",
                "osDisk": {"uri": "https://foo.com/bar"},
                "dataDisks": [],
            }
        )

        # Test Gen2 only
        gen2_image_obj.source = new_source
        res = prepare_vm_images(
            metadata=metadata_azure_obj, gen1=gen1_image_obj, gen2=gen2_image_obj, source=new_source
        )
        assert res == [gen2_image_obj]

        # Test Gen1 + Gen2
        metadata_azure_obj.support_legacy = True
        gen1_image_obj.source = new_source
        res = prepare_vm_images(
            metadata=metadata_azure_obj, gen1=gen1_image_obj, gen2=gen2_image_obj, source=new_source
        )
        assert res == [gen2_image_obj, gen1_image_obj]

    def test_prepare_vm_images_empty(
        self, metadata_azure_obj: AzurePublishingMetadata, caplog: LogCaptureFixture
    ) -> None:
        expected_err = "At least one argument of \"gen1\" or \"gen2\" must be set."

        new_source = VMImageSource.from_json(
            {
                "sourceType": "sasUri",
                "osDisk": {"uri": "https://foo.com/bar"},
                "dataDisks": [],
            }
        )

        with caplog.at_level(logging.ERROR):
            with pytest.raises(ValueError, match=expected_err):
                prepare_vm_images(
                    metadata=metadata_azure_obj, gen1=None, gen2=None, source=new_source
                )
            assert expected_err in caplog.text

    def test_update_skus(
        self, technical_config_obj: VMIPlanTechConfig, metadata_azure_obj: AzurePublishingMetadata
    ) -> None:
        """Test for a "SKU update" from scratch."""
        skus = technical_config_obj.skus

        res = update_skus(
            disk_versions=technical_config_obj.disk_versions,
            generation=metadata_azure_obj.generation,
            plan_name="plan-1",
        )
        assert res == skus

    def test_create_disk_version_from_scratch(
        self,
        disk_version_obj: DiskVersion,
        vmimage_source_obj: VMImageSource,
        metadata_azure_obj: AzurePublishingMetadata,
    ):
        metadata_azure_obj.support_legacy = True
        metadata_azure_obj.disk_version = "2.0.0"
        metadata_azure_obj.image_path = "https://uri.test.com"

        res = create_disk_version_from_scratch(
            metadata=metadata_azure_obj, source=vmimage_source_obj
        )
        res.vm_images = sorted(res.vm_images, key=attrgetter("image_type"))

        assert res == disk_version_obj
