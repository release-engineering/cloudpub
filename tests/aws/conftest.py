from typing import Any, Dict
from unittest import mock

import pytest

from cloudpub.aws.service import AWSProductService, AWSVersionMetadata
from cloudpub.models.aws import (
    AmiDeliveryOptionsDetails,
    AMISource,
    DeliveryOptions,
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
def ami_delivery_options_details(
    ami_source: Dict[str, Any], security_group: Dict[str, Any]
) -> Dict[str, Any]:
    return {
        "AmiSource": ami_source,
        "UsageInstructions": "Test notes",
        "RecommendedInstanceType": "x1.medium",
        "SecurityGroups": [security_group],
    }


@pytest.fixture
def delivery_options_details(ami_delivery_options_details: Dict[str, Any]) -> Dict[str, Any]:
    return {"AmiDeliveryOptionDetails": ami_delivery_options_details}


@pytest.fixture
def delivery_options(delivery_options_details: Dict[str, Any]) -> Dict[str, Any]:
    return {"Details": delivery_options_details}


@pytest.fixture
def version_mapping(version: Dict[str, Any], delivery_options: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "Version": version,
        "DeliveryOptions": [delivery_options],
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
def delivery_options_details_obj(delivery_options_details: Dict[str, Any]) -> DeliveryOptions:
    return DeliveryOptionsDetails.from_json(delivery_options_details)


@pytest.fixture
def ami_delivery_options_details_obj(
    ami_delivery_options_details: Dict[str, Any]
) -> DeliveryOptions:
    return AmiDeliveryOptionsDetails.from_json(ami_delivery_options_details)


@pytest.fixture
def delivery_options_obj(delivery_options: Dict[str, Any]) -> DeliveryOptions:
    return DeliveryOptions.from_json(delivery_options)


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
    return AWSProductService("fake-id", "fake-secret", "fake-region")


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
