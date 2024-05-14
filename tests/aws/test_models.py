import json
import re
from typing import Any, Dict

import pytest

from cloudpub.models.aws import (
    AccessEndpointUrl,
    AmiDeliveryOptionsDetails,
    AMISource,
    DeliveryOption,
    DeliveryOptionsDetails,
    DescribeEntityResponse,
    ProductDetailResponse,
    ProductVersionsBase,
    ProductVersionsCloudFormationSource,
    ProductVersionsVirtualizationSource,
    SecurityGroup,
    Version,
    VersionMapping,
    convert_source,
)


@pytest.fixture
def describe_entity_response_base() -> Dict[str, Any]:
    return {
        'EntityType': 'SaaSProduct@1.0',
        'EntityIdentifier': '3edd5534-75d7-49a5-bd3b-8e106e35f13f@12',
        'EntityArn': 'arn:aws:aws-marketplace:us-east-1:000000000000:AWSMarketplace/SaaSProduct/0',
        'LastModifiedDate': '2022-07-28T14:41:06Z',
    }


def test_aws_resource_props(
    version_obj: Version,
    ami_obj: AMISource,
    security_group_obj: SecurityGroup,
    access_endpoint_url_obj: AccessEndpointUrl,
    delivery_options_obj: DeliveryOption,
    delivery_options_details_obj: DeliveryOptionsDetails,
    ami_delivery_options_details_obj: AmiDeliveryOptionsDetails,
    version_mapping_obj: VersionMapping,
) -> None:
    # Version testing
    assert version_obj.version_title == "Test-Version-Title"
    assert version_obj.release_notes == "Test notes"

    # AMI testing
    assert ami_obj.ami_id == "ffffffff-ffff-ffff-ffff-ffffffffffff"
    assert ami_obj.access_role_arn == "arn:aws:iam::000000000000:role/FakeScanning"
    assert ami_obj.username == "ec2-user"
    assert ami_obj.operating_system_name == "fake"
    assert ami_obj.operating_system_version == "Fake-9.0.3_HVM-203325325232-x86_64-2"
    assert ami_obj.scanning_port == 22

    # Security Group testing
    assert security_group_obj.from_port == 22
    assert security_group_obj.ip_protocol == "Test notes"
    assert security_group_obj.ip_ranges == ["22.22.22.22", "00.00.00.00"]
    assert security_group_obj.to_port == 22

    # Delivery Options
    assert delivery_options_obj.id is None
    assert delivery_options_obj.details == delivery_options_details_obj

    # Delivery Options Details testing
    assert ami_delivery_options_details_obj.ami_source == ami_obj
    assert ami_delivery_options_details_obj.usage_instructions == "Test notes"
    assert ami_delivery_options_details_obj.recommended_instance_type == "x1.medium"
    assert ami_delivery_options_details_obj.security_groups == [security_group_obj]
    assert ami_delivery_options_details_obj.access_endpoint_url == access_endpoint_url_obj

    # Delivery Version testing
    assert version_mapping_obj.version == version_obj
    assert version_mapping_obj.delivery_options[0] == delivery_options_obj


def test_aws_resource_props_no_aeu(
    ami_delivery_options_details: Dict[str, Any],
) -> None:
    ami_delivery_options_details["AccessEndpointUrl"] = None
    ami_delivery_options_details_obj = AmiDeliveryOptionsDetails.from_json(
        ami_delivery_options_details
    )
    assert ami_delivery_options_details_obj.access_endpoint_url is None

    ami_json = ami_delivery_options_details_obj.to_json()
    assert ami_json.get("AccessEndpointUrl", "doesn't exist") == "doesn't exist"


def test_product_versions_base_invalid_type() -> None:
    err = "Invalid value for type. Expected: ['AmazonMachineImage', 'CloudFormationTemplate']"
    with pytest.raises(ValueError, match=re.escape(err)):
        ProductVersionsBase.from_json(
            {
                "type": "invalid",
                "source_id": "source",
            }
        )


def test_convert_source(
    product_versions_cloud_formation_source: Dict[str, Any],
    product_versions_virtualization_source: Dict[str, Any],
) -> None:
    assert isinstance(
        convert_source(product_versions_cloud_formation_source), ProductVersionsCloudFormationSource
    )
    assert isinstance(
        convert_source(product_versions_virtualization_source), ProductVersionsVirtualizationSource
    )


def test_describe_entity_response_parsed_details(
    describe_entity_response_base: Dict[str, Any], details_entity_json: Dict[str, Any]
) -> None:
    describe_entity_response_base["Details"] = json.dumps(details_entity_json)
    describe_entity_response_base["DetailsDocument"] = details_entity_json
    resp = DescribeEntityResponse.from_json(describe_entity_response_base)
    assert isinstance(resp.details_document, ProductDetailResponse)
