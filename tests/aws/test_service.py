import json
import logging
from copy import deepcopy
from typing import Any, Dict
from unittest import mock

import pytest
from _pytest.logging import LogCaptureFixture

from cloudpub.aws import AWSProductService, AWSVersionMetadata
from cloudpub.error import InvalidStateError, NotFoundError, Timeout
from cloudpub.models.aws import (
    DeliveryOption,
    ListChangeSetsResponse,
    ProductVersionsResponse,
    VersionMapping,
)


@pytest.fixture
def fake_entity_summary() -> Dict[str, Any]:
    return {
        "Name": "fake-name",
        "EntityType": "fake-type",
        "EntityIdentifier": "fake-identifier",
        "EntityArn": "fake-arn",
        "LastModifiedDate": "fake-date",
        "Visibility": "Public",
    }


class TestAWSVersionMetadata:
    def test_load_data(self, version_mapping_obj: VersionMapping):
        aws_version_metadata = AWSVersionMetadata(
            image_path="path/to/dir",
            architecture="x86",
            destination="fake-entity-id",
            version_mapping=version_mapping_obj,
            marketplace_entity_type="fake-product-type",
        )

        assert aws_version_metadata.version_mapping == version_mapping_obj

    def test_to_json_version_mapping(self, version_metadata_obj: AWSVersionMetadata) -> None:
        version_mapping_json = version_metadata_obj.version_mapping.to_json()
        assert version_mapping_json["Version"]["VersionTitle"] == "Test-Version-Title"


class TestAWSProductService:
    def test_get_product_by_id(
        self,
        mock_describe_entity: mock.MagicMock,
        aws_service: AWSProductService,
        describe_entity_response: Dict[str, Any],
    ) -> None:
        describe_entity_response["DetailsDocument"] = {"Versions": []}
        mock_describe_entity.return_value = describe_entity_response
        product_details = aws_service.get_product_by_id("fake-entity-id")

        mock_describe_entity.assert_called_once_with(
            Catalog="AWSMarketplace", EntityId='fake-entity-id'
        )
        assert product_details is not None
        assert product_details.versions == []

    def test_get_product_by_id_missing_details(
        self,
        mock_describe_entity: mock.MagicMock,
        aws_service: AWSProductService,
        describe_entity_response: Dict[str, Any],
    ) -> None:
        mock_describe_entity.return_value = describe_entity_response
        with pytest.raises(
            NotFoundError, match="No such product with EntityId: \"fake-entity-id\""
        ):
            _ = aws_service.get_product_by_id("fake-entity-id")

    def test_get_product_by_product_name(
        self,
        mock_list_entities: mock.MagicMock,
        mock_describe_entity: mock.MagicMock,
        aws_service: AWSProductService,
        describe_entity_response: Dict[str, Any],
        fake_entity_summary: Dict[str, Any],
    ) -> None:
        fake_entity_summary["EntityId"] = "35235325234234"
        mock_list_entities.return_value = {"EntitySummaryList": [fake_entity_summary]}
        describe_entity_response["DetailsDocument"] = {"Versions": []}
        mock_describe_entity.return_value = describe_entity_response
        product_details = aws_service.get_product_by_name("fake-product-type", "fake-product")

        filter_list = [{"Name": "Name", "ValueList": ["fake-product"]}]
        mock_list_entities.assert_called_once_with(
            Catalog="AWSMarketplace", EntityType="fake-product-type", FilterList=filter_list
        )
        mock_describe_entity.assert_called_once_with(
            Catalog="AWSMarketplace", EntityId='35235325234234'
        )
        assert product_details is not None
        assert isinstance(product_details.versions, list)
        assert product_details.versions == []

    def test_get_product_by_product_name_no_product(
        self,
        mock_list_entities: mock.MagicMock,
        mock_describe_entity: mock.MagicMock,
        aws_service: AWSProductService,
    ) -> None:
        mock_list_entities.return_value = {"EntitySummaryList": []}
        details_json = json.dumps({"Versions": []})
        mock_describe_entity.return_value = {"Details": details_json}
        with pytest.raises(NotFoundError, match="No such product with name \"fake-product\""):
            _ = aws_service.get_product_by_name("fake-product-type", "fake-product")

    def test_get_product_by_product_name_no_match(
        self,
        mock_list_entities: mock.MagicMock,
        mock_describe_entity: mock.MagicMock,
        aws_service: AWSProductService,
    ) -> None:
        mock_list_entities.return_value = {"EntitySummaryList": [{}]}
        details_json = json.dumps({"Versions": []})
        mock_describe_entity.return_value = {"Details": details_json}
        with pytest.raises(NotFoundError, match="No such product with name \"fake-product\""):
            _ = aws_service.get_product_by_name("fake-product-type", "fake-product")

    def test_get_product_by_product_name_multiple_match(
        self,
        mock_list_entities: mock.MagicMock,
        mock_describe_entity: mock.MagicMock,
        aws_service: AWSProductService,
        fake_entity_summary: Dict[str, Any],
    ) -> None:
        entity1 = fake_entity_summary
        entity2 = deepcopy(fake_entity_summary)
        entity1["EntityId"] = "35235325234234"
        entity2["EntityId"] = "1234213412341234"
        mock_list_entities.return_value = {"EntitySummaryList": [entity1, entity2]}
        details_json = json.dumps({"Versions": []})
        mock_describe_entity.return_value = {"Details": details_json}
        with pytest.raises(
            InvalidStateError, match="Multiple responses found for \"fake-product\""
        ):
            _ = aws_service.get_product_by_name("fake-product-type", "fake-product")

    def test_get_product_version_details(
        self,
        mock_describe_entity: mock.MagicMock,
        aws_service: AWSProductService,
        fake_entity_summary: Dict[str, Any],
        delivery_option: Dict[str, str],
    ) -> None:
        do1 = delivery_option
        do2 = deepcopy(delivery_option)
        do1["Id"] = "some-version-id"
        do2["Id"] = "fake-id2"
        details_json: Dict[str, Any] = {
            "Versions": [
                {
                    "Id": "fake-version-id",
                    "CreationDate": "fake-creation-date",
                    "VersionTitle": "Fake-Version",
                    "DeliveryOptions": [
                        do1,
                        do2,
                    ],
                },
            ]
        }
        fake_entity_summary["DetailsDocument"] = details_json
        mock_describe_entity.return_value = fake_entity_summary
        version_details = aws_service.get_product_version_details(
            "fake-entity-id", "some-version-id"
        )

        mock_describe_entity.assert_called_once_with(
            Catalog="AWSMarketplace", EntityId='fake-entity-id'
        )
        assert isinstance(version_details, ProductVersionsResponse)
        assert version_details.version_title == "Fake-Version"

    def test_get_product_version_details_no_match(
        self,
        mock_describe_entity: mock.MagicMock,
        aws_service: AWSProductService,
        fake_entity_summary: Dict[str, Any],
    ) -> None:
        details_json = {
            "Versions": [
                {
                    "Id": "Fake-Id",
                    "VersionTitle": "Fake-Version",
                    "CreationDate": "Fake-date",
                    "DeliveryOptions": [
                        {"Id": "fake-id1", "Visibility": "Public"},
                        {"Id": "fake-id2", "Visibility": "Public"},
                    ],
                },
            ]
        }
        fake_entity_summary["DetailsDocument"] = details_json
        mock_describe_entity.return_value = fake_entity_summary
        with pytest.raises(NotFoundError, match="No such version with id \"some-version-id\""):
            _ = aws_service.get_product_version_details("fake-entity-id", "some-version-id")

    def test_get_product_versions(
        self,
        mock_describe_entity: mock.MagicMock,
        aws_service: AWSProductService,
        fake_entity_summary: Dict[str, Any],
    ) -> None:
        details_json = {
            "Versions": [
                {
                    "Id": "1",
                    "VersionTitle": "Fake-Version",
                    "CreationDate": "2023-02-24T12:41:25.503Z",
                    "Sources": [
                        {
                            "Id": "1234-1234-1234-1234",
                            "Type": "AmazonMachineImage",
                            "Image": "ami-id-fake",
                            "Architecture": "x86_64",
                            "VirtualizationType": "hvm",
                            "OperatingSystem": {
                                "Name": "RHEL",
                                "Version": "RHEL CoreOS",
                                "Username": "core",
                                "ScanningPort": 22,
                            },
                            "Compatibility": {
                                "AvailableInstanceTypes": [],
                                "RestrictedInstanceTypes": [],
                            },
                        }
                    ],
                    "DeliveryOptions": [
                        {
                            "Id": "fake-id1",
                            "Visibility": "Restricted",
                        },
                        {
                            "Id": "fake-id2",
                            "Visibility": "Public",
                        },
                    ],
                },
                {
                    "Id": "2",
                    "VersionTitle": "Fake-Version2",
                    "CreationDate": "2023-01-24T12:41:25.503Z",
                    "Sources": [
                        {
                            "Id": "1234-1234-1234-1234",
                            "Type": "AmazonMachineImage",
                            "Image": "ami-id-fake",
                            "Architecture": "x86_64",
                            "VirtualizationType": "hvm",
                            "OperatingSystem": {
                                "Name": "RHEL",
                                "Version": "RHEL CoreOS",
                                "Username": "core",
                                "ScanningPort": 22,
                            },
                            "Compatibility": {
                                "AvailableInstanceTypes": ["g5.48xlarge"],
                                "RestrictedInstanceTypes": [],
                            },
                        }
                    ],
                    "DeliveryOptions": [
                        {
                            "Id": "fake-id1",
                            "Visibility": "Limited",
                        },
                        {
                            "Id": "fake-id2",
                            "Visibility": "Restricted",
                        },
                    ],
                },
            ]
        }
        fake_entity_summary["DetailsDocument"] = details_json
        mock_describe_entity.return_value = fake_entity_summary
        version_details = aws_service.get_product_versions("fake-entity-id")

        mock_describe_entity.assert_called_once_with(
            Catalog="AWSMarketplace", EntityId='fake-entity-id'
        )
        for _, v in version_details.items():
            v["delivery_options"][0].id = "fake-id1"
            v["delivery_options"][0].id = "fake-id2"
            assert v["ami_ids"] == ["ami-id-fake"]

    def test_get_product_versions_no_version(
        self,
        mock_describe_entity: mock.MagicMock,
        aws_service: AWSProductService,
        fake_entity_summary: Dict[str, Any],
    ) -> None:
        details_json: Dict[str, Any] = {"Versions": []}
        fake_entity_summary["DetailsDocument"] = details_json
        mock_describe_entity.return_value = fake_entity_summary
        with pytest.raises(NotFoundError, match="This product has no versions"):
            _ = aws_service.get_product_versions("fake-entity-id")

    def test_get_product_version_by_name(
        self,
        mock_describe_entity: mock.MagicMock,
        aws_service: AWSProductService,
        fake_entity_summary: Dict[str, Any],
    ) -> None:
        details_json = {
            "Versions": [
                {
                    "Id": "1",
                    "VersionTitle": "Fake-Version",
                    "CreationDate": "Fake-date",
                    "DeliveryOptions": [
                        {"Id": "fake-id1", "Visibility": "Public"},
                        {"Id": "fake-id2", "Visibility": "Public"},
                    ],
                },
                {
                    "Id": "2",
                    "VersionTitle": "Fake-Version2",
                    "CreationDate": "Fake-date2",
                    "DeliveryOptions": [
                        {"Id": "fake-id1", "Visibility": "Public"},
                        {"Id": "fake-id2", "Visibility": "Public"},
                    ],
                },
            ]
        }
        fake_entity_summary["DetailsDocument"] = details_json
        mock_describe_entity.return_value = fake_entity_summary
        version_details = aws_service.get_product_version_by_name("fake-entity-id", "Fake-Version")

        mock_describe_entity.assert_called_once_with(
            Catalog="AWSMarketplace", EntityId='fake-entity-id'
        )
        assert version_details.id == "fake-id1"

    def test_get_product_version_by_name_no_version(
        self,
        mock_describe_entity: mock.MagicMock,
        aws_service: AWSProductService,
        fake_entity_summary: Dict[str, Any],
    ) -> None:
        details_json: Dict[str, Any] = {"Versions": []}
        fake_entity_summary["DetailsDocument"] = details_json
        mock_describe_entity.return_value = fake_entity_summary
        with pytest.raises(NotFoundError, match="This product has no versions"):
            _ = aws_service.get_product_version_by_name("fake-product-type", "Fake-Version")

    def test_get_product_version_by_name_no_match(
        self,
        mock_describe_entity: mock.MagicMock,
        aws_service: AWSProductService,
        fake_entity_summary: Dict[str, Any],
    ) -> None:
        details_json = {
            "Versions": [
                {
                    "Id": "1",
                    "VersionTitle": "Fake-Version1",
                    "CreationDate": "Fake-date",
                    "DeliveryOptions": [
                        {"Id": "fake-id1", "Visibility": "Public"},
                        {"Id": "fake-id2", "Visibility": "Public"},
                    ],
                },
                {
                    "Id": "2",
                    "VersionTitle": "Fake-Version2",
                    "CreationDate": "Fake-date2",
                    "DeliveryOptions": [
                        {"Id": "fake-id1", "Visibility": "Public"},
                        {"Id": "fake-id2", "Visibility": "Public"},
                    ],
                },
            ]
        }
        fake_entity_summary["DetailsDocument"] = details_json
        mock_describe_entity.return_value = fake_entity_summary
        with pytest.raises(NotFoundError, match="No such version with name \"Fake-Version\""):
            _ = aws_service.get_product_version_by_name("fake-entity-id", "Fake-Version")

    def test_set_restrict_versions(
        self, mock_start_change_set: mock.MagicMock, aws_service: AWSProductService
    ) -> None:
        ret = {"ChangeSetId": "Fake-Changeset"}
        mock_start_change_set.return_value = ret
        restrict_ids = ["1234-1234-1234-1234"]
        rep = aws_service.set_restrict_versions("fake-entity-id", "fake-product-type", restrict_ids)

        change_details = {"DeliveryOptionIds": restrict_ids}
        mock_start_change_set.assert_called_once_with(
            Catalog="AWSMarketplace",
            ChangeSet=[
                {
                    "ChangeType": "RestrictDeliveryOptions",
                    "Entity": {
                        "Type": "fake-product-type@1.0",
                        "Identifier": "fake-entity-id",
                    },
                    "Details": json.dumps(change_details),
                }
            ],
        )
        assert rep == "Fake-Changeset"

    def test_cancel_change_set(
        self, mock_cancel_change_set: mock.MagicMock, aws_service: AWSProductService
    ) -> None:
        ret = {"ChangeSetId": "Fake-Changeset"}
        mock_cancel_change_set.return_value = ret
        rep = aws_service.cancel_change_set("fake-change-set-id")

        mock_cancel_change_set.assert_called_once_with(
            Catalog="AWSMarketplace", ChangeSetId="fake-change-set-id"
        )
        assert rep == "Fake-Changeset"

    def test_check_publish_status(
        self, mock_describe_change_set: mock.MagicMock, aws_service: AWSProductService
    ) -> None:
        ret = {
            "ChangeSetId": "fake-id",
            "ChangeSetArn": "fake-arn",
            "StartTime": "fake-start-time",
            "Status": "Succeeded",
            "FailureCode": "",
            "ErrorDetailList": [],
        }
        mock_describe_change_set.return_value = ret
        status = aws_service.check_publish_status("fake-change-set-id")
        assert status == "Succeeded"

    def test_check_publish_status_failed(
        self, mock_describe_change_set: mock.MagicMock, aws_service: AWSProductService
    ) -> None:
        failure_list = [
            {
                "ErrorCode": "500",
                "ErrorMessage": "Multiple fake  failures happened",
            }
        ]
        change_set = [
            {
                "ChangeType": "RestrictDeliveryOptions",
                "Details": r"{}",
                "ErrorDetailList": failure_list,
            }
        ]
        ret = {
            "ChangeSetId": "change",
            "ChangeSetArn": "fake-arn",
            "Status": "Failed",
            "FailureCode": "fake-code",
            "ChangeSet": change_set,
            "StartTime": "fake-start-time",
            "EndTime": "fake-end-time",
        }
        mock_describe_change_set.return_value = ret
        with pytest.raises(InvalidStateError):
            _ = aws_service.check_publish_status("fake-change-set-id")

    def test_wait_for_changeset(
        self, mock_describe_change_set: mock.MagicMock, aws_service: AWSProductService
    ) -> None:
        ret = {
            "ChangeSetId": "change",
            "ChangeSetArn": "fake-arn",
            "Status": "Succeeded",
            "FailureCode": "",
            "ErrorDetailList": [],
            "StartTime": "fake-start-time",
            "EndTime": "fake-end-time",
        }
        mock_describe_change_set.return_value = ret
        aws_service.wait_for_changeset("fake-change-set-id")

    def test_wait_for_changeset_timeout(
        self, mock_describe_change_set: mock.MagicMock, aws_service: AWSProductService
    ) -> None:
        ret = {
            "ChangeSetId": "change",
            "ChangeSetArn": "fake-arn",
            "Status": "Blah",
            "FailureCode": "",
            "ErrorDetailList": [],
            "StartTime": "fake-start-time",
            "EndTime": "fake-end-time",
        }
        mock_describe_change_set.return_value = ret
        with pytest.raises(Timeout, match="Timed out waiting for fake-change-set-id to finish"):
            aws_service.wait_for_changeset("fake-change-set-id")

    @mock.patch("cloudpub.aws.AWSProductService.wait_for_changeset")
    def test_publish(
        self,
        mock_wait_for_changeset: mock.MagicMock,
        aws_service: AWSProductService,
        version_metadata_obj: AWSVersionMetadata,
        mock_start_change_set: mock.MagicMock,
        caplog: LogCaptureFixture,
    ) -> None:
        mock_start_change_set.return_value = {
            "ResponseMetadata": {
                "RequestId": "xxxxxxx",
                "HTTPStatusCode": 200,
                "HTTPHeaders": {
                    "date": "Tue, 14 May 2024 14:28:48 GMT",
                    "content-type": "application/json",
                    "content-length": "1019",
                    "connection": "keep-alive",
                    "x-amzn-requestid": "xxxxxx",
                },
                "RetryAttempts": 0,
            },
            "ChangeSetId": "fake-change-set-id",
            "ChangeSetArn": "xxxxxxxxx",
            "ChangeSetName": "xxxxxxxx",
            "Intent": "APPLY",
            "StartTime": "2024-04-22T12:23:41Z",
            "EndTime": "2024-04-22T12:38:47Z",
            "Status": "SUCCEEDED",
            "ChangeSet": [
                {
                    "ChangeType": "UpdateDeliveryOptions",
                    "Entity": {
                        "Type": "AmiProduct@1.0",
                        "Identifier": "xxxx-xxxx-xxxxx",
                    },
                    "Details": (
                        "a very long string repeated"
                        " since this will be very"
                        " long a very long string"
                        " repeated since this will"
                        " be very long a very long"
                        " string repeated since"
                        " this will be very long"
                    ),
                    "DetailsDocument": {
                        "someresponse1": "responses",
                        "someresponse2": "responses",
                        "someresponse3": "responses",
                        "someresponse4": "responses",
                        "someresponse5": "responses",
                    },
                    "ErrorDetailList": [],
                }
            ],
        }

        with caplog.at_level(logging.DEBUG):
            aws_service.publish(version_metadata_obj)
        assert "UpdateDeliveryOptions" in caplog.text
        assert "The response from publishing was: " in caplog.text

        mock_start_change_set.assert_called_once_with(
            Catalog="AWSMarketplace",
            ChangeSet=[
                {
                    "ChangeType": "AddDeliveryOptions",
                    "Entity": {
                        "Type": "fake-product-type@1.0",
                        "Identifier": "fake-entity-id",
                    },
                    "DetailsDocument": mock.ANY,
                },
            ],
            Intent="APPLY",
        )
        mock_wait_for_changeset.assert_called_once_with("fake-change-set-id")

        _, asserted_kwargs = mock_start_change_set.call_args
        details_json = asserted_kwargs["ChangeSet"][0]["DetailsDocument"]
        assert isinstance(details_json, dict)
        assert isinstance(details_json["DeliveryOptions"], list)
        assert isinstance(details_json["DeliveryOptions"][0], dict)
        assert "Id" not in details_json["DeliveryOptions"][0]

    @mock.patch("cloudpub.aws.AWSProductService.wait_for_changeset")
    def test_publish_overwrite(
        self,
        mock_wait_for_changeset: mock.MagicMock,
        mock_describe_entity: mock.MagicMock,
        aws_service: AWSProductService,
        version_metadata_obj: AWSVersionMetadata,
        mock_start_change_set: mock.MagicMock,
        fake_entity_summary: Dict[str, Any],
    ) -> None:
        details_json = {
            "Versions": [
                {
                    "Id": "1",
                    "VersionTitle": "Test-Version-Title",
                    "CreationDate": "fake-date",
                    "DeliveryOptions": [
                        {"Id": "fake-id1", "Visibility": "Public"},
                        {"Id": "fake-id2", "Visibility": "Public"},
                    ],
                },
                {
                    "Id": "2",
                    "VersionTitle": "Fake-Version2",
                    "CreationDate": "fake-date2",
                    "DeliveryOptions": [
                        {"Id": "fake-id1", "Visibility": "Public"},
                        {"Id": "fake-id2", "Visibility": "Public"},
                    ],
                },
            ]
        }
        fake_entity_summary["DetailsDocument"] = details_json
        mock_describe_entity.return_value = fake_entity_summary
        mock_start_change_set.return_value = {"ChangeSetId": "fake-change-set-id"}

        version_metadata_obj.overwrite = True
        aws_service.publish(version_metadata_obj)

        mock_describe_entity.assert_called_once_with(
            Catalog="AWSMarketplace", EntityId='fake-entity-id'
        )
        mock_start_change_set.assert_called_once_with(
            Catalog="AWSMarketplace",
            ChangeSet=[
                {
                    "ChangeType": "UpdateDeliveryOptions",
                    "Entity": {
                        "Type": "fake-product-type@1.0",
                        "Identifier": "fake-entity-id",
                    },
                    "DetailsDocument": mock.ANY,
                },
            ],
            Intent="APPLY",
        )
        mock_wait_for_changeset.assert_called_once_with("fake-change-set-id")

        _, asserted_kwargs = mock_start_change_set.call_args
        details_json = asserted_kwargs["ChangeSet"][0]["DetailsDocument"]
        assert isinstance(details_json, dict)
        assert isinstance(details_json["DeliveryOptions"], list)
        assert isinstance(details_json["DeliveryOptions"][0], dict)
        assert details_json["DeliveryOptions"][0]["Id"] == "fake-id1"

    @mock.patch("cloudpub.aws.AWSProductService.wait_for_changeset")
    def test_publish_keepdraft(
        self,
        mock_wait_for_changeset: mock.MagicMock,
        aws_service: AWSProductService,
        version_metadata_obj: AWSVersionMetadata,
        mock_start_change_set: mock.MagicMock,
    ) -> None:
        mock_start_change_set.return_value = {"ChangeSetId": "fake-change-set-id"}

        version_metadata_obj.keepdraft = True
        aws_service.publish(version_metadata_obj)

        mock_start_change_set.assert_called_once_with(
            Catalog="AWSMarketplace",
            ChangeSet=[
                {
                    "ChangeType": "AddDeliveryOptions",
                    "Entity": {
                        "Type": "fake-product-type@1.0",
                        "Identifier": "fake-entity-id",
                    },
                    "DetailsDocument": mock.ANY,
                },
            ],
            Intent="VALIDATE",
        )
        mock_wait_for_changeset.assert_called_once_with("fake-change-set-id")

        _, asserted_kwargs = mock_start_change_set.call_args
        details_json = asserted_kwargs["ChangeSet"][0]["DetailsDocument"]
        assert isinstance(details_json, dict)
        assert isinstance(details_json["DeliveryOptions"], list)
        assert isinstance(details_json["DeliveryOptions"][0], dict)
        assert "Id" not in details_json["DeliveryOptions"][0]

    @mock.patch("cloudpub.aws.AWSProductService.get_product_versions")
    @mock.patch("cloudpub.aws.AWSProductService.set_restrict_versions")
    @mock.patch("cloudpub.aws.AWSProductService.wait_for_changeset")
    def test_restrict_minor_versions(
        self,
        mock_wait_for_changeset: mock.MagicMock,
        mock_set_restrict_versions: mock.MagicMock,
        get_product_versions: mock.MagicMock,
        aws_service: AWSProductService,
    ) -> None:
        mock_version_ids = {
            '6.9 20220513-0': {
                "delivery_options": [
                    DeliveryOption.from_json({"id": 'fake-6.9 ', "visibility": "Public"})
                ],
                "created_date": "2022-01-24T12:41:25.503Z",
                "ami_ids": ["ami-fake-id-6-9"],
            },
            '7.9 20220513-0': {
                "delivery_options": [
                    DeliveryOption.from_json({"id": 'fake-7.9 ', "visibility": "Public"})
                ],
                "created_date": "2022-01-24T12:41:25.503Z",
                "ami_ids": ["ami-fake-id-newest-7"],
            },
            '7.8 20220513-0': {
                "delivery_options": [
                    DeliveryOption.from_json({"id": 'fake-7.8', "visibility": "Public"})
                ],
                "created_date": "2022-01-24T12:41:25.503Z",
                "ami_ids": ["ami-fake-id-2"],
            },
            '8.9 20220513-0': {
                "delivery_options": [
                    DeliveryOption.from_json({"id": 'fake-8.9', "visibility": "Public"})
                ],
                "created_date": "2022-01-24T12:41:25.503Z",
                "ami_ids": ["ami-fake-id-3"],
            },
            '8.8 20220513-0': {
                "delivery_options": [
                    DeliveryOption.from_json({"id": 'fake-8.8', "visibility": "Public"})
                ],
                "created_date": "2022-01-24T12:41:25.503Z",
                "ami_ids": ["ami-fake-id-4"],
            },
            '8.10 20220513-0': {
                "delivery_options": [
                    DeliveryOption.from_json({"id": 'fake-8.10', "visibility": "Public"})
                ],
                "created_date": "2022-01-24T12:41:25.503Z",
                "ami_ids": ["ami-fake-id-newest-8"],
            },
            '9.0 20220513-0': {
                "delivery_options": [
                    DeliveryOption.from_json({"id": 'fake-9.0.0', "visibility": "Public"})
                ],
                "created_date": "2024-01-24T12:41:25.503Z",
                "ami_ids": ["ami-fake-id-5"],
            },
            '9.0 20220613': {
                "delivery_options": [
                    DeliveryOption.from_json({"id": 'fake-9.0.1', "visibility": "Public"})
                ],
                "created_date": "2023-02-24T12:41:25.503Z",
                "ami_ids": ["ami-fake-id-6"],
            },
            '9.0 20220713': {
                "delivery_options": [
                    DeliveryOption.from_json({"id": 'fake-9.0.2', "visibility": "Public"})
                ],
                "created_date": "2022-03-24T12:41:25.503Z",
                "ami_ids": ["ami-fake-id-7"],
            },
            '9.0 20220813': {
                "delivery_options": [
                    DeliveryOption.from_json({"id": 'fake-9.0.3', "visibility": "Public"})
                ],
                "created_date": "2021-04-24T12:41:25.503Z",
                "ami_ids": ["ami-fake-id-8"],
            },
            '9.0 20220916': {
                "delivery_options": [
                    DeliveryOption.from_json({"id": 'fake-9.0.4', "visibility": "Public"})
                ],
                "created_date": "2020-05-24T12:41:25.503Z",
                "ami_ids": ["ami-fake-id-9"],
            },
            '9.1 20220915': {
                "delivery_options": [
                    DeliveryOption.from_json({"id": 'fake-9.1.3', "visibility": "Restricted"})
                ],
                "created_date": "2025-03-24T12:41:25.503Z",
                "ami_ids": ["ami-fake-id-10"],
            },
            '9.1 20220913': {
                "delivery_options": [
                    DeliveryOption.from_json({"id": 'fake-9.1.1', "visibility": "Public"})
                ],
                "created_date": "2024-03-24T12:41:25.503Z",
                "ami_ids": ["ami-fake-id-newest-9"],
            },
            '9.1 20220513': {
                "delivery_options": [
                    DeliveryOption.from_json({"id": 'fake-9.1.2', "visibility": "Public"})
                ],
                "created_date": "2023-03-24T12:41:25.503Z",
                "ami_ids": ["ami-fake-id-11"],
            },
            'BadVersion': {
                "delivery_options": [
                    DeliveryOption.from_json({"id": 'fake-id1-6', "visibility": "Public"})
                ],
                "created_date": "2022-01-24T12:41:25.503Z",
                "ami_ids": ["ami-fake-id-12"],
            },
        }

        not_restricted_versions = [
            'ami-fake-id-newest-9',
            'ami-fake-id-newest-8',
            'ami-fake-id-newest-7',
        ]

        get_product_versions.return_value = mock_version_ids
        mock_set_restrict_versions.return_value = "fake-change-set-id1"

        restricted_vers = aws_service.restrict_versions("fake-entity", "fake-entity-type", 3, 1)

        get_product_versions.assert_called_once_with("fake-entity")
        mock_set_restrict_versions.assert_called_once_with(
            'fake-entity',
            'fake-entity-type',
            [
                'fake-6.9 ',
                'fake-7.8',
                'fake-8.9',
                'fake-8.8',
                'fake-9.0.0',
                'fake-9.0.1',
                'fake-9.0.2',
                'fake-9.0.3',
                'fake-9.0.4',
                'fake-9.1.2',
            ],
        )
        mock_wait_for_changeset.assert_called_once_with("fake-change-set-id1")

        assert restricted_vers == [
            'ami-fake-id-6-9',
            'ami-fake-id-2',
            'ami-fake-id-3',
            'ami-fake-id-4',
            'ami-fake-id-5',
            'ami-fake-id-6',
            'ami-fake-id-7',
            'ami-fake-id-8',
            'ami-fake-id-9',
            'ami-fake-id-11',
        ]

        assert not_restricted_versions not in restricted_vers

    @mock.patch("cloudpub.aws.AWSProductService.get_product_versions")
    @mock.patch("cloudpub.aws.AWSProductService.set_restrict_versions")
    @mock.patch("cloudpub.aws.AWSProductService.wait_for_changeset")
    def test_restrict_minor_versions_no_match(
        self,
        mock_wait_for_changeset: mock.MagicMock,
        mock_set_restrict_versions: mock.MagicMock,
        get_product_versions: mock.MagicMock,
        aws_service: AWSProductService,
    ) -> None:
        mock_version_ids = {
            'BadVersion': {
                "delivery_options": [{"id": 'fake-id1-6', "visibility": "Public"}],
                "created_date": "2022-01-24T12:41:25.503Z",
            },
        }
        get_product_versions.return_value = mock_version_ids
        mock_set_restrict_versions.return_value = "fake-change-set-id1"

        restrcited_vers = aws_service.restrict_versions("fake-entity", "fake-entity-type")

        get_product_versions.assert_called_once_with("fake-entity")
        mock_set_restrict_versions.assert_not_called()
        mock_wait_for_changeset.assert_not_called()

        assert restrcited_vers == []

    def test_get_product_active_changesets(
        self,
        mock_list_change_sets: mock.MagicMock,
        aws_service: AWSProductService,
        list_changeset_response: Dict[str, Any],
    ) -> None:
        mock_list_change_sets.return_value = list_changeset_response
        change_sets = aws_service.get_product_active_changesets("fake-entity")

        filter_list = [
            {"Name": "EntityId", "ValueList": ["fake-entity"]},
            {"Name": "Status", "ValueList": ["APPLYING", "PREPARING"]},
        ]

        mock_list_change_sets.assert_called_once_with(
            Catalog="AWSMarketplace", FilterList=filter_list
        )

        assert len(change_sets) == 1
        assert change_sets[0].id == "2de11mwkeagfwj07225x1h5a5"
        assert change_sets[0].entity_id_list[0] == "d87bcebf-9cf4-47f5-9b5b-5470d4490f3d"
        assert change_sets[0].status == "APPLYING"

    @mock.patch("cloudpub.aws.AWSProductService.get_product_active_changesets")
    @mock.patch("cloudpub.aws.AWSProductService.wait_for_changeset")
    def test_wait_product_active_changesets(
        self,
        mock_wait_for_changeset: mock.MagicMock,
        mock_product_active_changesets: mock.MagicMock,
        aws_service: AWSProductService,
        list_changeset_obj: ListChangeSetsResponse,
    ) -> None:
        aws_service.wait_for_changeset_attempts = 2
        mock_product_active_changesets.side_effect = [list_changeset_obj.change_set_list, []]
        aws_service.wait_active_changesets("fake-entity")

        mock_product_active_changesets.assert_has_calls(
            [mock.call("fake-entity"), mock.call("fake-entity")]
        )
        mock_wait_for_changeset.assert_called_once_with("2de11mwkeagfwj07225x1h5a5")

    @mock.patch("cloudpub.aws.AWSProductService.get_product_active_changesets")
    @mock.patch("cloudpub.aws.AWSProductService.wait_for_changeset")
    def test_wait_product_no_active_changesets(
        self,
        mock_wait_for_changeset: mock.MagicMock,
        mock_product_active_changesets: mock.MagicMock,
        aws_service: AWSProductService,
    ) -> None:
        mock_product_active_changesets.return_value = []
        aws_service.wait_active_changesets("fake-entity")

        mock_product_active_changesets.assert_called_once_with("fake-entity")
        mock_wait_for_changeset.assert_not_called()

    @mock.patch("cloudpub.aws.AWSProductService.get_product_active_changesets")
    @mock.patch("cloudpub.aws.AWSProductService.wait_for_changeset")
    def test_wait_product_active_changesets_timeout(
        self,
        mock_wait_for_changeset: mock.MagicMock,
        mock_product_active_changesets: mock.MagicMock,
        aws_service: AWSProductService,
        list_changeset_obj: ListChangeSetsResponse,
    ) -> None:
        aws_service.wait_for_changeset_attempts = 1
        mock_product_active_changesets.return_value = list_changeset_obj.change_set_list
        with pytest.raises(Timeout, match="Timed out waiting for fake-entity to be unlocked"):
            aws_service.wait_active_changesets("fake-entity")
