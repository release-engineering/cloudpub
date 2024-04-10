import json
from copy import deepcopy
from typing import Any, Dict
from unittest import mock

import pytest

from cloudpub.aws import AWSProductService, AWSVersionMetadata
from cloudpub.error import InvalidStateError, NotFoundError, Timeout
from cloudpub.models.aws import DeliveryOption, ProductVersionsResponse, VersionMapping


@pytest.fixture
def fake_entity_summary() -> Dict[str, str]:
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
        describe_entity_response["Details"] = json.dumps({"Versions": []})
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
        fake_entity_summary: Dict[str, str],
    ) -> None:
        fake_entity_summary["EntityId"] = "35235325234234"
        mock_list_entities.return_value = {"EntitySummaryList": [fake_entity_summary]}
        describe_entity_response["Details"] = json.dumps({"Versions": []})
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
        fake_entity_summary: Dict[str, str],
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
        fake_entity_summary: Dict[str, str],
        delivery_option: Dict[str, str],
    ) -> None:
        do1 = delivery_option
        do2 = deepcopy(delivery_option)
        do1["Id"] = "some-version-id"
        do2["Id"] = "fake-id2"
        details_json = json.dumps(
            {
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
        )
        fake_entity_summary["Details"] = details_json
        mock_describe_entity.return_value = fake_entity_summary
        version_details = aws_service.get_product_version_details(
            "fake-entity-id", "some-version-id"
        )

        mock_describe_entity.assert_called_once_with(
            Catalog="AWSMarketplace", EntityId='fake-entity-id'
        )
        assert isinstance(version_details, ProductVersionsResponse)
        assert version_details.version_title == "Fake-Version"

    def test_get_product_version_details_no_version(
        self,
        mock_describe_entity: mock.MagicMock,
        aws_service: AWSProductService,
        fake_entity_summary: Dict[str, str],
    ) -> None:
        details_json = json.dumps({})
        fake_entity_summary["Details"] = details_json
        mock_describe_entity.return_value = fake_entity_summary
        with pytest.raises(NotFoundError, match="This product has no versions"):
            _ = aws_service.get_product_version_details("fake-entity-id", "some-version-id")

    def test_get_product_version_details_no_match(
        self,
        mock_describe_entity: mock.MagicMock,
        aws_service: AWSProductService,
        fake_entity_summary: Dict[str, str],
    ) -> None:
        details_json = json.dumps(
            {
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
        )
        fake_entity_summary["Details"] = details_json
        mock_describe_entity.return_value = fake_entity_summary
        with pytest.raises(NotFoundError, match="No such version with id \"some-version-id\""):
            _ = aws_service.get_product_version_details("fake-entity-id", "some-version-id")

    def test_get_product_versions(
        self,
        mock_describe_entity: mock.MagicMock,
        aws_service: AWSProductService,
        fake_entity_summary: Dict[str, str],
    ) -> None:
        details_json = json.dumps(
            {
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
        )
        fake_entity_summary["Details"] = details_json
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
        fake_entity_summary: Dict[str, str],
    ) -> None:
        details_json = json.dumps({})
        fake_entity_summary["Details"] = details_json
        mock_describe_entity.return_value = fake_entity_summary
        with pytest.raises(NotFoundError, match="This product has no versions"):
            _ = aws_service.get_product_versions("fake-entity-id")

    def test_get_product_version_by_name(
        self,
        mock_describe_entity: mock.MagicMock,
        aws_service: AWSProductService,
        fake_entity_summary: Dict[str, str],
    ) -> None:
        details_json = json.dumps(
            {
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
        )
        fake_entity_summary["Details"] = details_json
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
        fake_entity_summary: Dict[str, str],
    ) -> None:
        details_json = json.dumps({})
        fake_entity_summary["Details"] = details_json
        mock_describe_entity.return_value = fake_entity_summary
        with pytest.raises(NotFoundError, match="This product has no versions"):
            _ = aws_service.get_product_version_by_name("fake-product-type", "Fake-Version")

    def test_get_product_version_by_name_no_match(
        self,
        mock_describe_entity: mock.MagicMock,
        aws_service: AWSProductService,
        fake_entity_summary: Dict[str, str],
    ) -> None:
        details_json = json.dumps(
            {
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
        )
        fake_entity_summary["Details"] = details_json
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
    ) -> None:
        mock_start_change_set.return_value = {"ChangeSetId": "fake-change-set-id"}

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
        fake_entity_summary: Dict[str, str],
    ) -> None:
        details_json = json.dumps(
            {
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
        )
        fake_entity_summary["Details"] = details_json
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
            '9.0 20220513-0': {
                "delivery_options": [
                    DeliveryOption.from_json({"id": 'fake-id1', "visibility": "Restricted"})
                ],
                "created_date": "2022-01-24T12:41:25.503Z",
                "ami_ids": ["ami-fake-id-1"],
            },
            '9.0 20220613': {
                "delivery_options": [
                    DeliveryOption.from_json({"id": 'fake-id2', "visibility": "Public"})
                ],
                "created_date": "2022-02-24T12:41:25.503Z",
                "ami_ids": ["ami-fake-id-2"],
            },
            '9.0 20220713': {
                "delivery_options": [
                    DeliveryOption.from_json({"id": 'fake-id3', "visibility": "Limited"})
                ],
                "created_date": "2022-03-24T12:41:25.503Z",
                "ami_ids": ["ami-fake-id-3"],
            },
            '9.0 20220813': {
                "delivery_options": [
                    DeliveryOption.from_json({"id": 'fake-id4', "visibility": "Restricted"})
                ],
                "created_date": "2022-04-24T12:41:25.503Z",
                "ami_ids": ["ami-fake-id-4"],
            },
            '9.0 20220913': {
                "delivery_options": [
                    DeliveryOption.from_json({"id": 'fake-id5', "visibility": "Public"})
                ],
                "created_date": "2022-05-24T12:41:25.503Z",
                "ami_ids": ["ami-fake-id-5"],
            },
            'OpenShift Container Platform 9.0': {
                "delivery_options": [
                    DeliveryOption.from_json({"id": 'fake-id6', "visibility": "Public"})
                ],
                "created_date": "2022-01-24T12:41:25.503Z",
                "ami_ids": ["ami-fake-id-6"],
            },
            '9.1 20220913': {
                "delivery_options": [
                    DeliveryOption.from_json({"id": 'fake-id1-2', "visibility": "Public"})
                ],
                "created_date": "2022-03-24T12:41:25.503Z",
                "ami_ids": ["ami-fake-id-7"],
            },
            '9.1 20220513': {
                "delivery_options": [
                    DeliveryOption.from_json({"id": 'fake-id1-3', "visibility": "Public"})
                ],
                "created_date": "2022-03-24T12:41:25.503Z",
                "ami_ids": ["ami-fake-id-8"],
            },
            'BadVersion': {
                "delivery_options": [
                    DeliveryOption.from_json({"id": 'fake-id1-6', "visibility": "Public"})
                ],
                "created_date": "2022-01-24T12:41:25.503Z",
                "ami_ids": ["ami-fake-id-9"],
            },
        }
        get_product_versions.return_value = mock_version_ids
        mock_set_restrict_versions.return_value = "fake-change-set-id1"

        restricted_vers = aws_service.restrict_minor_versions(
            "fake-entity", "fake-entity-type", "9.0"
        )

        get_product_versions.assert_called_once_with("fake-entity")
        mock_set_restrict_versions.assert_called_once_with(
            'fake-entity', 'fake-entity-type', ['fake-id2', 'fake-id6']
        )
        mock_wait_for_changeset.assert_called_once_with("fake-change-set-id1")

        assert restricted_vers == ['ami-fake-id-2', 'ami-fake-id-6']

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

        restrcited_vers = aws_service.restrict_minor_versions(
            "fake-entity", "fake-entity-type", "9.0"
        )

        get_product_versions.assert_called_once_with("fake-entity")
        mock_set_restrict_versions.assert_not_called()
        mock_wait_for_changeset.assert_not_called()

        assert restrcited_vers == []
