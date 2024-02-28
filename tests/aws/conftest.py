from typing import Any, Dict
from unittest import mock

import pytest

from cloudpub.aws.service import AWSProductService, AWSVersionMetadata
from cloudpub.models.aws import (
    AccessEndpointUrl,
    AmiDeliveryOptionsDetails,
    AMISource,
    DeliveryOption,
    DeliveryOptionsDetails,
    SecurityGroup,
    Version,
    VersionMapping,
)


@pytest.fixture
def version() -> Dict[str, Any]:
    return {"VersionTitle": "Test-Version-Title", "ReleaseNotes": "Test notes"}


@pytest.fixture
def ami_source() -> Dict[str, Any]:
    return {
        "AmiId": "ffffffff-ffff-ffff-ffff-ffffffffffff",
        "AccessRoleArn": "arn:aws:iam::000000000000:role/FakeScanning",
        "UserName": "ec2-user",
        "OperatingSystemName": "fake",
        "OperatingSystemVersion": "Fake-9.0.3_HVM-203325325232-x86_64-2",
        "ScanningPort": 22,
    }


@pytest.fixture
def security_group() -> Dict[str, Any]:
    return {
        "FromPort": 22,
        "IpProtocol": "Test notes",
        "IpRanges": ["22.22.22.22", "00.00.00.00"],
        "ToPort": 22,
    }


@pytest.fixture
def access_endpoint_url() -> Dict[str, Any]:
    return {
        "Port": 22,
        "Protocol": "http",
    }


@pytest.fixture
def ami_delivery_options_details(
    ami_source: Dict[str, Any], security_group: Dict[str, Any], access_endpoint_url: Dict[str, Any]
) -> Dict[str, Any]:
    return {
        "AmiSource": ami_source,
        "UsageInstructions": "Test notes",
        "RecommendedInstanceType": "x1.medium",
        "SecurityGroups": [security_group],
        "AccessEndpointUrl": access_endpoint_url,
    }


@pytest.fixture
def delivery_options_details(ami_delivery_options_details: Dict[str, Any]) -> Dict[str, Any]:
    return {"AmiDeliveryOptionDetails": ami_delivery_options_details}


@pytest.fixture
def delivery_options(delivery_options_details: Dict[str, Any]) -> Dict[str, Any]:
    return {"Details": delivery_options_details, "Visibility": "Public"}


@pytest.fixture
def version_mapping(version: Dict[str, Any], delivery_options: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "Version": version,
        "DeliveryOptions": [delivery_options],
    }


@pytest.fixture
def product_versions_virtualization_source() -> Dict[str, Any]:
    return {
        "Type": "AmazonMachineImage",
        "VirtualizationType": "hvm",
        "Id": "d047e6cf-390e-311f-a99c-342863e042a2",
        "Architecture": "x86_64",
        "Compatibility": {
            "AvailableInstanceTypes": [
                "g5.48xlarge",
            ],
            "RestrictedInstanceTypes": [],
        },
        "Image": "ami-0c2c8f774b8b54883",
        "OperatingSystem": {
            "Name": "RHEL",
            "ScanningPort": 22,
            "Username": "ec2-user",
            "Version": "PROUCT-7-TEST-7.4.0_HVM_GA-20220804-x86_64-0",
        },
    }


@pytest.fixture
def product_versions_cloud_formation_source() -> Dict[str, Any]:
    return {
        "AWSDependentServices": ["Amazon EC2"],
        "ConsumedSources": ["72a2adac-2566-3a5e-8d95-831454b2ecd8"],
        "Id": "f25b306d-e62d-335c-8d9d-b20e1a79a55b",
        "NestedDocuments": None,
        "Type": "CloudFormationTemplate",
    }


@pytest.fixture
def product_detail_description() -> Dict[str, Any]:
    return {
        "ProductTitle": "TITLE",
        "ProductCode": "9fashf9sa8yf09a8y0f9",
        "ShortDescription": "Short description.",
        "Manufacturer": "Some Manufacter",
        "LongDescription": "Long description.",
        "Sku": "AAAAAA",
        "Highlights": ["Cool product"],
        "AssociatedProducts": None,
        "SearchKeywords": ["test", "no purchase"],
        "Visibility": "Limited",
        "ProductState": "Active",
        "Categories": ["Streaming solutions"],
    }


@pytest.fixture
def promotional_resource() -> Dict[str, Any]:
    return {
        "LogoUrl": "https://foo.com/bar.png",
        "Videos": [],
        "AdditionalResources": [
            {
                "Type": "Link",
                "Text": "What is Love?",
                "Url": "https://www.youtube.com/watch?v=HEXWRTEbj1I",
            }
        ],
        "PromotionalMedia": None,
    }


@pytest.fixture
def support_information() -> Dict[str, Any]:
    return {
        "Description": "https://test.com/support",
        "Resources": [],
    }


@pytest.fixture
def dimension_1() -> Dict[str, Any]:
    return {
        "Name": "Time active streaming is happening",
        "Description": "Time active streaming is happening",
        "Key": "cluster_hour",
        "Unit": "Units",
        "Types": ["ExternallyMetered"],
    }


@pytest.fixture
def dimension_2() -> Dict[str, Any]:
    return {
        "Name": "Storage in GB/hr",
        "Description": "Storage in GB/hr",
        "Key": "storage_gb",
        "Unit": "Units",
        "Types": ["ExternallyMetered"],
    }


@pytest.fixture
def dimension_3() -> Dict[str, Any]:
    return {
        "Name": "Data I/O in GB",
        "Description": "Data I/O in GB",
        "Key": "transfer_gb",
        "Unit": "Units",
        "Types": ["ExternallyMetered"],
    }


@pytest.fixture
def delivery_option() -> Dict[str, str]:
    return {
        "Id": "do-qx3pi2xndxsqg",
        "Type": "SoftwareRegistration",
        "FulfillmentUrl": "https://foo.com/bar",
        "Visibility": "Public",
    }


@pytest.fixture
def product_version_response(delivery_option: Dict[str, str]) -> Dict[str, Any]:
    return {
        "Id": "version-6viuxnnz24h5e",
        "VersionTitle": "12.34.56",
        "DeliveryOptions": [delivery_option],
        "CreationDate": "2018-02-27T13:45:22Z",
    }


@pytest.fixture
def targeting_detail() -> Dict[str, Any]:
    return {
        "PositiveTargeting": {
            "BuyerAccounts": [
                "213772884920",
                "027933477046",
                "568056954830",
                "896801664647",
                "967235393410",
                "297512042063",
                "795061427196",
                "782858285006",
                "589173575009",
            ]
        }
    }


@pytest.fixture
def details_entity_json(
    product_detail_description: Dict[str, Any],
    promotional_resource: Dict[str, Any],
    support_information: Dict[str, Any],
    dimension_1: Dict[str, Any],
    dimension_2: Dict[str, Any],
    dimension_3: Dict[str, Any],
    product_version_response: Dict[str, Any],
    targeting_detail: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "Description": product_detail_description,
        "PromotionalResources": promotional_resource,
        "SupportInformation": support_information,
        "Dimensions": [
            dimension_1,
            dimension_2,
            dimension_3,
        ],
        "Versions": [
            product_version_response,
        ],
        "Targeting": targeting_detail,
    }


@pytest.fixture
def describe_entity_response() -> Dict[str, Any]:
    return {
        "EntityType": "AmiProduct",
        "EntityIdentifier": "fake-entity-identififer",
        "EntityArn": "fake-arn",
        "LastModifiedDate": "2018-02-27T13:45:22Z",
        "ResponseMetadata": {"RequestId": "fake-req-id", "HTTPStatusCode": 200, "HTTPHeaders": {}},
    }


@pytest.fixture
def version_obj(version: Dict[str, Any]) -> Version:
    return Version.from_json(version)


@pytest.fixture
def ami_obj(ami_source: Dict[str, Any]) -> AMISource:
    return AMISource.from_json(ami_source)


@pytest.fixture
def security_group_obj(security_group: Dict[str, Any]) -> SecurityGroup:
    return SecurityGroup.from_json(security_group)


@pytest.fixture
def access_endpoint_url_obj(access_endpoint_url: Dict[str, Any]) -> AccessEndpointUrl:
    return AccessEndpointUrl.from_json(access_endpoint_url)


@pytest.fixture
def delivery_options_details_obj(delivery_options_details: Dict[str, Any]) -> DeliveryOption:
    return DeliveryOptionsDetails.from_json(delivery_options_details)


@pytest.fixture
def ami_delivery_options_details_obj(
    ami_delivery_options_details: Dict[str, Any]
) -> DeliveryOption:
    return AmiDeliveryOptionsDetails.from_json(ami_delivery_options_details)


@pytest.fixture
def delivery_options_obj(delivery_options: Dict[str, Any]) -> DeliveryOption:
    return DeliveryOption.from_json(delivery_options)


@pytest.fixture
def version_mapping_obj(version_mapping: Dict[str, Any]) -> VersionMapping:
    return VersionMapping.from_json(version_mapping)


@pytest.fixture
def version_metadata_obj(version_mapping: Dict[str, Any]) -> AWSVersionMetadata:
    aws_version_metadata = AWSVersionMetadata(
        image_path="path/to/dir",
        architecture="x86",
        destination="fake-entity-id",
        version_mapping=VersionMapping.from_json(version_mapping),
        marketplace_entity_type="fake-product-type",
    )

    return aws_version_metadata


@pytest.fixture
def aws_service() -> AWSProductService:
    return AWSProductService("fake-id", "fake-secret", "fake-region", 1, 0)


@pytest.fixture
def mock_describe_entity(aws_service: AWSProductService) -> mock.MagicMock:
    return mock.patch.object(aws_service.marketplace, "describe_entity").start()


@pytest.fixture
def mock_list_entities(aws_service: AWSProductService) -> mock.MagicMock:
    return mock.patch.object(aws_service.marketplace, "list_entities").start()


@pytest.fixture
def mock_start_change_set(aws_service: AWSProductService) -> mock.MagicMock:
    return mock.patch.object(aws_service.marketplace, "start_change_set").start()


@pytest.fixture
def mock_cancel_change_set(aws_service: AWSProductService) -> mock.MagicMock:
    return mock.patch.object(aws_service.marketplace, "cancel_change_set").start()


@pytest.fixture
def mock_describe_change_set(aws_service: AWSProductService) -> mock.MagicMock:
    return mock.patch.object(aws_service.marketplace, "describe_change_set").start()
