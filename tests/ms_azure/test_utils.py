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
    VMISku,
)
from cloudpub.ms_azure.utils import (
    AzurePublishingMetadata,
    create_disk_version_from_scratch,
    get_image_type_mapping,
    is_azure_job_not_complete,
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
    def test_get_image_type_mapping(self, metadata_azure_obj: AzurePublishingMetadata) -> None:
        # Test Gen1
        res = get_image_type_mapping(metadata_azure_obj.architecture, "V1")
        assert res == "x64Gen1"

        # Test Gen2
        res = get_image_type_mapping(metadata_azure_obj.architecture, "V2")
        assert res == "x64Gen2"

    @pytest.mark.parametrize(
        "sas1,sas2,base_only,expected",
        [
            ("https://foo.com/bar", "https://foo.com/bar?foo=bar", False, False),
            (
                "https://foo.com/bar?foo=bar&st=aaaaa",
                "https://foo.com/bar?foo=bar&st=bbb",
                False,
                True,
            ),
            (
                "https://foo.com/bar?foo=bar&st=a&se=b&sig=c&bar=foo",
                "https://foo.com/bar?foo=bar&st=d&se=e&sig=f&bar=foo",
                False,
                True,
            ),
            (
                "https://foo.com/bar?foo=bar&st=a&se=b&sig=c&bar=foo",
                "https://foo.com/bar?foo=foo&st=d&se=e&sig=f",
                False,
                False,
            ),
            (
                "https://foo.com/bar?foo=bar&st=aaaaa",
                "https://bar.com/foo?foo=bar&st=bbb",
                False,
                False,
            ),
            (
                "https://foo.com/bar?bar=foo&st=aaaaa",
                "https://foo.com/bar?foo=bar&st=bbb",
                False,
                False,
            ),
            (
                "https://foo.com/bar?foo=bar&st=aaaaa",
                "https://bar.com/foo?foo=bar&st=bbb",
                True,
                False,
            ),
            (
                "https://foo.com/bar?bar=foo&st=aaaaa",
                "https://foo.com/bar?foo=bar&st=bbb",
                True,
                True,
            ),
        ],
    )
    def test_is_sas_present(
        self,
        sas1: str,
        sas2: str,
        base_only: bool,
        expected: bool,
        technical_config_obj: VMIPlanTechConfig,
    ) -> None:
        # Test positive
        technical_config_obj.disk_versions[0].vm_images[0].source.os_disk.uri = sas1

        res = is_sas_present(tech_config=technical_config_obj, sas_uri=sas2, base_only=base_only)
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

    def test_update_new_skus_x86_gen2_default(
        self, technical_config_obj: VMIPlanTechConfig, metadata_azure_obj: AzurePublishingMetadata
    ) -> None:
        """Ensure the creation of 2 new SKUs for x86 from scratch, defaulting to Gen1."""
        expected = technical_config_obj.skus

        res = update_skus(
            disk_versions=technical_config_obj.disk_versions,
            generation=metadata_azure_obj.generation,
            plan_name="plan-1",
        )
        assert res == expected

    def test_update_new_skus_x86_gen1_default(
        self, technical_config_obj: VMIPlanTechConfig
    ) -> None:
        """Ensure the creation of 2 new SKUs for x86 from scratch, defaulting to Gen1."""
        expected = [
            VMISku.from_json(x)
            for x in [
                {"imageType": "x64Gen1", "skuId": "plan1", "security_type": None},
                {"imageType": "x64Gen2", "skuId": "plan1-gen2", "security_type": None},
            ]
        ]
        res = update_skus(
            disk_versions=technical_config_obj.disk_versions,
            generation="V1",
            plan_name="plan1",
        )
        assert res == expected

    def test_update_new_skus_arm64(
        self,
        disk_version_arm64_obj: DiskVersion,
    ) -> None:
        """Ensure the creation of 1 new SKU for ARM64 from scratch."""
        expected = [
            VMISku.from_json(x)
            for x in [
                {"imageType": "arm64Gen2", "skuId": "plan1-arm64", "security_type": None},
            ]
        ]
        res = update_skus(
            disk_versions=[disk_version_arm64_obj],
            generation="V2",
            plan_name="plan1",
        )
        assert res == expected

    def test_update_new_skus_mixed_x64_arm64_gen2_default(
        self,
        disk_version_arm64_obj: DiskVersion,
        technical_config_obj: VMIPlanTechConfig,
    ) -> None:
        """Ensure the creation of 3 new SKUs: 2 for x64 (V2/V1) and 1 for ARM64 from scratch."""
        expected = [
            VMISku.from_json(x)
            for x in [
                {"imageType": "x64Gen2", "skuId": "plan1", "security_type": None},
                {"imageType": "arm64Gen2", "skuId": "plan1-arm64", "security_type": None},
                {"imageType": "x64Gen1", "skuId": "plan1-gen1", "security_type": None},
            ]
        ]
        res = update_skus(
            disk_versions=[disk_version_arm64_obj] + technical_config_obj.disk_versions,
            generation="V2",
            plan_name="plan1",
        )
        assert res == expected

    def test_update_new_skus_mixed_x64_arm64_gen1_default(
        self,
        disk_version_arm64_obj: DiskVersion,
        technical_config_obj: VMIPlanTechConfig,
    ) -> None:
        """Ensure the creation of 3 new SKUs: 2 for x64 (V1/V2) and 1 for ARM64 from scratch."""
        expected = [
            VMISku.from_json(x)
            for x in [
                {"imageType": "x64Gen1", "skuId": "plan1", "security_type": None},
                {"imageType": "arm64Gen2", "skuId": "plan1-arm64-gen2", "security_type": None},
                {"imageType": "x64Gen2", "skuId": "plan1-gen2", "security_type": None},
            ]
        ]
        res = update_skus(
            disk_versions=[disk_version_arm64_obj] + technical_config_obj.disk_versions,
            generation="V1",
            plan_name="plan1",
        )
        assert res == expected

    def test_update_new_skus_mixed_arm64_x64_gen2_default(
        self,
        disk_version_arm64_obj: DiskVersion,
        technical_config_obj: VMIPlanTechConfig,
    ) -> None:
        """Ensure the creation of 3 new SKUs: 2 for x64 (V2/V1) and 1 for ARM64 from scratch."""
        expected = [
            VMISku.from_json(x)
            for x in [
                {"imageType": "x64Gen2", "skuId": "plan1", "security_type": None},
                {"imageType": "arm64Gen2", "skuId": "plan1-arm64", "security_type": None},
                {"imageType": "x64Gen1", "skuId": "plan1-gen1", "security_type": None},
            ]
        ]
        technical_config_obj.disk_versions.append(disk_version_arm64_obj)
        res = update_skus(
            disk_versions=technical_config_obj.disk_versions,
            generation="V2",
            plan_name="plan1",
        )
        assert res == expected

    def test_update_new_skus_mixed_arm64_x64_gen1_default(
        self,
        disk_version_arm64_obj: DiskVersion,
        technical_config_obj: VMIPlanTechConfig,
    ) -> None:
        """Ensure the creation of 3 new SKUs: 2 for x64 (V1/V2) and 1 for ARM64 from scratch."""
        expected = [
            VMISku.from_json(x)
            for x in [
                {"imageType": "x64Gen1", "skuId": "plan1", "security_type": None},
                {"imageType": "arm64Gen2", "skuId": "plan1-arm64-gen2", "security_type": None},
                {"imageType": "x64Gen2", "skuId": "plan1-gen2", "security_type": None},
            ]
        ]
        technical_config_obj.disk_versions.append(disk_version_arm64_obj)
        res = update_skus(
            disk_versions=technical_config_obj.disk_versions,
            generation="V1",
            plan_name="plan1",
        )
        assert res == expected

    def test_update_existing_skus_x86_gen2_default(
        self, technical_config_obj: VMIPlanTechConfig, metadata_azure_obj: AzurePublishingMetadata
    ) -> None:
        """Ensure 2 x64 SKUS are properly created using Gen2 as default."""
        skus = [
            VMISku.from_json(x)
            for x in [
                {"imageType": "x64Gen1", "skuId": "plan-1-gen1"},
            ]
        ]
        technical_config_obj.skus = skus
        res = update_skus(
            disk_versions=technical_config_obj.disk_versions,
            generation=metadata_azure_obj.generation,
            plan_name="plan-1",
            old_skus=technical_config_obj.skus,
        )
        assert res == [
            VMISku.from_json(x)
            for x in [
                {"imageType": "x64Gen2", "skuId": "plan-1", "securityType": None},
                {"imageType": "x64Gen1", "skuId": "plan-1-gen1", "securityType": None},
            ]
        ]

    def test_update_existing_skus_x86_gen1_default(
        self, technical_config_obj: VMIPlanTechConfig
    ) -> None:
        """Ensure 2 x64 SKUS are properly created using Gen1 as default."""
        skus = [
            VMISku.from_json(x)
            for x in [
                {"imageType": "x64Gen2", "skuId": "plan1-gen2", "securityType": ["trusted"]},
            ]
        ]
        technical_config_obj.skus = skus
        res = update_skus(
            disk_versions=technical_config_obj.disk_versions,
            generation="V1",
            plan_name="plan1",
            old_skus=technical_config_obj.skus,
        )
        assert res == [
            VMISku.from_json(x)
            for x in [
                {"imageType": "x64Gen1", "skuId": "plan1"},
                {"imageType": "x64Gen2", "skuId": "plan1-gen2", "securityType": ["trusted"]},
            ]
        ]

    @pytest.mark.parametrize("generation", ["V1", "V2"])
    def test_update_existing_skus_x86_gen1_single(
        self, generation: str, technical_config_obj: VMIPlanTechConfig
    ) -> None:
        """Ensure the alternate x64 SKU is created while the default Gen1 is preserved."""
        skus = [VMISku.from_json({"imageType": "x64Gen1", "skuId": "plan1"})]
        technical_config_obj.skus = skus
        res = update_skus(
            disk_versions=technical_config_obj.disk_versions,
            generation=generation,
            plan_name="plan1",
            old_skus=technical_config_obj.skus,
        )
        assert res == [
            VMISku.from_json(x)
            for x in [
                {"imageType": "x64Gen1", "skuId": "plan1", "securityType": None},
                {"imageType": "x64Gen2", "skuId": "plan1-gen2", "securityType": None},
            ]
        ]

    @pytest.mark.parametrize("generation", ["V1", "V2"])
    def test_update_existing_skus_x86_gen2_single(
        self, generation: str, technical_config_obj: VMIPlanTechConfig
    ) -> None:
        """Ensure the alternate x64 SKU is created while the default Gen2 is preserved."""
        skus = [VMISku.from_json({"imageType": "x64Gen2", "skuId": "plan1"})]
        technical_config_obj.skus = skus
        res = update_skus(
            disk_versions=technical_config_obj.disk_versions,
            generation=generation,
            plan_name="plan1",
            old_skus=technical_config_obj.skus,
        )
        assert res == [
            VMISku.from_json(x)
            for x in [
                {"imageType": "x64Gen2", "skuId": "plan1", "securityType": None},
                {"imageType": "x64Gen1", "skuId": "plan1-gen1", "securityType": None},
            ]
        ]

    def test_update_existing_skus_mixed_arches(
        self, gen1_image: Dict[str, Any], gen2_image: Dict[str, Any], arm_image: Dict[str, Any]
    ) -> None:
        """Ensure the SKUs are properly made for disk versions using x86 and ARM arches."""
        disk_versions = [
            DiskVersion.from_json(
                {
                    "versionNumber": "2.0.0",
                    "vmImages": [gen1_image, gen2_image, arm_image],
                    "lifecycleState": "generallyAvailable",
                }
            )
        ]
        skus = [
            VMISku.from_json(
                {"imageType": "x64Gen2", "skuId": "plan1", "securityType": ["trusted"]}
            )
        ]
        res = update_skus(
            disk_versions=disk_versions,
            generation="V2",
            plan_name="plan1",
            old_skus=skus,
        )

        assert res == [
            VMISku.from_json(x)
            for x in [
                {"imageType": "x64Gen2", "skuId": "plan1", "securityType": ["trusted"]},
                {"imageType": "arm64Gen2", "skuId": "plan1-arm64"},
                {"imageType": "x64Gen1", "skuId": "plan1-gen1"},
            ]
        ]

    @pytest.mark.parametrize("generation", ["V1", "V2"])
    def test_update_existing_skus_arm64_single(
        self,
        generation: str,
        technical_config_obj: VMIPlanTechConfig,
        disk_version_arm64_obj: DiskVersion,
    ) -> None:
        """Ensure a single Arm64 SKU is preserved."""
        skus = [VMISku.from_json({"imageType": "arm64Gen2", "skuId": "plan1-arm64"})]
        technical_config_obj.skus = skus

        res = update_skus(
            disk_versions=[disk_version_arm64_obj],
            generation=generation,
            plan_name="plan1",
            old_skus=technical_config_obj.skus,
        )
        assert res == [
            VMISku.from_json(x)
            for x in [
                {"imageType": "arm64Gen2", "skuId": "plan1-arm64", "securityType": None},
            ]
        ]

    @pytest.mark.parametrize("generation", ["V1", "V2"])
    def test_update_skus_return_existing_unconventional_naming(
        self,
        generation: str,
        technical_config_obj: VMIPlanTechConfig,
    ) -> None:
        """Ensure the existing SKUs are returned even if they doesn't present expected namings."""
        skus = [
            VMISku.from_json(x)
            for x in [
                {"imageType": "x64Gen2", "skuId": "differentNaming"},
                {"imageType": "x64Gen1", "skuId": "gen1GotDifferentNaming"},
            ]
        ]
        res = update_skus(
            disk_versions=technical_config_obj.disk_versions,
            generation=generation,
            plan_name="plan1",
            old_skus=skus,
        )
        assert res == [
            VMISku.from_json(x)
            for x in [
                {"imageType": "x64Gen2", "skuId": "differentNaming", "securityType": None},
                {"imageType": "x64Gen1", "skuId": "gen1GotDifferentNaming"},
            ]
        ]

    def test_create_disk_version_from_scratch_x86(
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

    def test_create_disk_version_from_scratch_arm64(
        self,
        disk_version_arm64_obj: DiskVersion,
        vmimage_source_obj: VMImageSource,
        metadata_azure_obj: AzurePublishingMetadata,
    ):
        metadata_azure_obj.support_legacy = True
        metadata_azure_obj.disk_version = "2.1.0"
        metadata_azure_obj.image_path = "https://uri.test.com"
        metadata_azure_obj.architecture = "arm64"

        res = create_disk_version_from_scratch(
            metadata=metadata_azure_obj, source=vmimage_source_obj
        )
        res.vm_images = sorted(res.vm_images, key=attrgetter("image_type"))

        assert res == disk_version_arm64_obj
