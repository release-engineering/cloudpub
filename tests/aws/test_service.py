import json
from unittest import mock

import pytest

from cloudpub.aws.service import AWSProductService, AWSVersionMetadata
from cloudpub.error import InvalidStateError, NotFoundError, Timeout
from cloudpub.models.aws import VersionMapping


class TestAWSVersionMetadata:
    def test_load_data(self, version_mapping_obj: VersionMapping):
        aws_version_metadata = AWSVersionMetadata(
            image_path="path/to/dir",
            architecture="x86",
            destination="NA",
            version_mapping=version_mapping_obj,
            entity_id="fake-entity-id",
            product_type="fake-product-type",
        )

        assert aws_version_metadata.version_mapping == version_mapping_obj

    def test_to_json_version_mapping(self, version_metadata_obj: AWSVersionMetadata) -> None:
        version_mapping_json = version_metadata_obj.version_mapping.to_json()
        assert version_mapping_json["Version"]["VersionTitle"] == "Test-Version-Title"


class TestAWSProductService:
    def test_get_product_by_id(
        self, mock_describe_entity: mock.MagicMock, aws_service: AWSProductService
    ) -> None:
        details_json = json.dumps({"Versions": []})
        mock_describe_entity.return_value = {"Details": details_json}
        product_details = aws_service.get_product_by_id("fake-entity-id")

        mock_describe_entity.assert_called_once_with(
            Catalog="AWSMarketplace", EntityId='fake-entity-id'
        )
        assert product_details is not None
        assert product_details["Versions"] == []

    def test_get_product_by_id_missing_details(
        self, mock_describe_entity: mock.MagicMock, aws_service: AWSProductService
    ) -> None:
        mock_describe_entity.return_value = {}
        with pytest.raises(
            NotFoundError, match="No such product with EntityId: \"fake-entity-id\""
        ):
            _ = aws_service.get_product_by_id("fake-entity-id")

    def test_get_product_by_product_name(
        self,
        mock_list_entities: mock.MagicMock,
        mock_describe_entity: mock.MagicMock,
        aws_service: AWSProductService,
    ) -> None:
        mock_list_entities.return_value = {"EntitySummaryList": [{"EntityId": "35235325234234"}]}
        details_json = json.dumps({"Versions": []})
        mock_describe_entity.return_value = {"Details": details_json}
        product_details = aws_service.get_product_by_name("fake-product-type", "fake-product")

        filter_list = [{"Name": "Name", "ValueList": ["fake-product"]}]
        mock_list_entities.assert_called_once_with(
            Catalog="AWSMarketplace", EntityType="fake-product-type", FilterList=filter_list
        )
        mock_describe_entity.assert_called_once_with(
            Catalog="AWSMarketplace", EntityId='35235325234234'
        )
        assert product_details is not None
        assert isinstance(product_details["Versions"], list)
        assert product_details["Versions"] == []

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
    ) -> None:
        mock_list_entities.return_value = {
            "EntitySummaryList": [{"EntityId": "35235325234234"}, {"EntityId": "1234213412341234"}]
        }
        details_json = json.dumps({"Versions": []})
        mock_describe_entity.return_value = {"Details": details_json}
        with pytest.raises(
            InvalidStateError, match="Multiple responses found for \"fake-product\""
        ):
            _ = aws_service.get_product_by_name("fake-product-type", "fake-product")

    def test_get_product_version_details(
        self, mock_describe_entity: mock.MagicMock, aws_service: AWSProductService
    ) -> None:
        details_json = json.dumps(
            {
                "Versions": [
                    {
                        "VersionTitle": "Fake-Version",
                        "DeliveryOptions": [
                            {"Id": "some-version-id"},
                            {"Id": "fake-id2"},
                        ],
                    },
                ]
            }
        )
        mock_describe_entity.return_value = {"Details": details_json}
        version_details = aws_service.get_product_version_details(
            "fake-entity-id", "some-version-id"
        )

        mock_describe_entity.assert_called_once_with(
            Catalog="AWSMarketplace", EntityId='fake-entity-id'
        )
        assert isinstance(version_details, dict)
        assert version_details["VersionTitle"] == "Fake-Version"

    def test_get_product_version_details_no_version(
        self, mock_describe_entity: mock.MagicMock, aws_service: AWSProductService
    ) -> None:
        details_json = json.dumps({})
        mock_describe_entity.return_value = {"Details": details_json}
        with pytest.raises(NotFoundError, match="This product has no versions"):
            _ = aws_service.get_product_version_details("fake-entity-id", "some-version-id")

    def test_get_product_version_details_no_match(
        self, mock_describe_entity: mock.MagicMock, aws_service: AWSProductService
    ) -> None:
        details_json = json.dumps(
            {
                "Versions": [
                    {
                        "VersionTitle": "Fake-Version",
                        "DeliveryOptions": [
                            {"Id": "fake-id1"},
                            {"Id": "fake-id2"},
                        ],
                    },
                ]
            }
        )
        mock_describe_entity.return_value = {"Details": details_json}
        with pytest.raises(NotFoundError, match="No such version with id \"some-version-id\""):
            _ = aws_service.get_product_version_details("fake-entity-id", "some-version-id")

    def test_get_product_version_ids(
        self, mock_describe_entity: mock.MagicMock, aws_service: AWSProductService
    ) -> None:
        details_json = json.dumps(
            {
                "Versions": [
                    {
                        "VersionTitle": "Fake-Version",
                        "DeliveryOptions": [
                            {"Id": "fake-id1"},
                            {"Id": "fake-id2"},
                        ],
                    },
                    {
                        "VersionTitle": "Fake-Version2",
                        "DeliveryOptions": [
                            {"Id": "fake-id1"},
                            {"Id": "fake-id2"},
                        ],
                    },
                ]
            }
        )
        mock_describe_entity.return_value = {"Details": details_json}
        version_details = aws_service.get_product_version_ids("fake-entity-id")

        version1 = version_details[0]
        version2 = version_details[1]

        mock_describe_entity.assert_called_once_with(
            Catalog="AWSMarketplace", EntityId='fake-entity-id'
        )
        assert version1["Fake-Version"][0] == "fake-id1"
        assert version1["Fake-Version"][1] == "fake-id2"
        assert version2["Fake-Version2"][0] == "fake-id1"
        assert version2["Fake-Version2"][1] == "fake-id2"

    def test_get_product_version_ids_no_version(
        self, mock_describe_entity: mock.MagicMock, aws_service: AWSProductService
    ) -> None:
        details_json = json.dumps({})
        mock_describe_entity.return_value = {"Details": details_json}
        with pytest.raises(NotFoundError, match="This product has no versions"):
            _ = aws_service.get_product_version_ids("fake-entity-id")

    def test_get_product_version_by_name(
        self, mock_describe_entity: mock.MagicMock, aws_service: AWSProductService
    ) -> None:
        details_json = json.dumps(
            {
                "Versions": [
                    {
                        "VersionTitle": "Fake-Version",
                        "DeliveryOptions": [
                            {"Id": "fake-id1"},
                            {"Id": "fake-id2"},
                        ],
                    },
                    {
                        "VersionTitle": "Fake-Version2",
                        "DeliveryOptions": [
                            {"Id": "fake-id1"},
                            {"Id": "fake-id2"},
                        ],
                    },
                ]
            }
        )
        mock_describe_entity.return_value = {"Details": details_json}
        version_details = aws_service.get_product_version_by_name("fake-entity-id", "Fake-Version")

        mock_describe_entity.assert_called_once_with(
            Catalog="AWSMarketplace", EntityId='fake-entity-id'
        )
        assert version_details[0]["Id"] == "fake-id1"
        assert version_details[1]["Id"] == "fake-id2"

    def test_get_product_version_by_name_no_version(
        self, mock_describe_entity: mock.MagicMock, aws_service: AWSProductService
    ) -> None:
        details_json = json.dumps({})
        mock_describe_entity.return_value = {"Details": details_json}
        with pytest.raises(NotFoundError, match="This product has no versions"):
            _ = aws_service.get_product_version_by_name("fake-product-type", "Fake-Version")

    def test_get_product_version_by_name_no_match(
        self, mock_describe_entity: mock.MagicMock, aws_service: AWSProductService
    ) -> None:
        details_json = json.dumps(
            {
                "Versions": [
                    {
                        "VersionTitle": "Fake-Version1",
                        "DeliveryOptions": [
                            {"Id": "fake-id1"},
                            {"Id": "fake-id2"},
                        ],
                    },
                    {
                        "VersionTitle": "Fake-Version2",
                        "DeliveryOptions": [
                            {"Id": "fake-id1"},
                            {"Id": "fake-id2"},
                        ],
                    },
                ]
            }
        )
        mock_describe_entity.return_value = {"Details": details_json}
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
        ret = {"Status": "Succeeded", "FailureCode": "", "ErrorDetailList": []}
        mock_describe_change_set.return_value = ret
        status = aws_service.check_publish_status("fake-change-set-id")
        assert status == "Succeeded"

    def test_check_publish_status_failed(
        self, mock_describe_change_set: mock.MagicMock, aws_service: AWSProductService
    ) -> None:
        failure_list = [
            {
                "Multiple": "fake",
                "failures": "happened",
            }
        ]
        ret = {"Status": "Failed", "FailureCode": "fake-code", "ErrorDetailList": failure_list}
        mock_describe_change_set.return_value = ret
        with pytest.raises(InvalidStateError):
            _ = aws_service.check_publish_status("fake-change-set-id")

    def test_wait_for_publish_task(
        self, mock_describe_change_set: mock.MagicMock, aws_service: AWSProductService
    ) -> None:
        ret = {"Status": "Succeeded", "FailureCode": "", "ErrorDetailList": []}
        mock_describe_change_set.return_value = ret
        aws_service.wait_for_publish_task("fake-change-set-id", 1, 0)

    def test_wait_for_publish_task_timeout(
        self, mock_describe_change_set: mock.MagicMock, aws_service: AWSProductService
    ) -> None:
        ret = {"Status": "Blah", "FailureCode": "", "ErrorDetailList": []}
        mock_describe_change_set.return_value = ret
        with pytest.raises(Timeout, match="Timed out waiting for fake-change-set-id to finish"):
            aws_service.wait_for_publish_task("fake-change-set-id", 1, 0)

    def test_start_image_scan(self, aws_service: AWSProductService) -> None:
        # future test for image scan
        with pytest.raises(NotImplementedError, match="To be added at a future date"):
            aws_service.start_image_scan("ami_id")

    def test_check_image_scan(self, aws_service: AWSProductService) -> None:
        # future test for image scan
        with pytest.raises(NotImplementedError, match="To be added at a future date"):
            aws_service.check_image_scan("ami_id")

    @mock.patch("cloudpub.aws.AWSProductService.wait_for_publish_task")
    def test_publish(
        self,
        mock_wait_for_publish_task: mock.MagicMock,
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
                    "Details": version_metadata_obj.version_mapping.to_json(),
                },
            ],
        )
        mock_wait_for_publish_task.assert_called_once_with("fake-change-set-id")

    @mock.patch("cloudpub.aws.AWSProductService.wait_for_publish_task")
    def test_publish_overwrite(
        self,
        mock_wait_for_publish_task: mock.MagicMock,
        aws_service: AWSProductService,
        version_metadata_obj: AWSVersionMetadata,
        mock_start_change_set: mock.MagicMock,
    ) -> None:
        mock_start_change_set.return_value = {"ChangeSetId": "fake-change-set-id"}

        version_metadata_obj.overwrite = True
        aws_service.publish(version_metadata_obj)

        mock_start_change_set.assert_called_once_with(
            Catalog="AWSMarketplace",
            ChangeSet=[
                {
                    "ChangeType": "UpdateDeliveryOptions",
                    "Entity": {
                        "Type": "fake-product-type@1.0",
                        "Identifier": "fake-entity-id",
                    },
                    "Details": version_metadata_obj.version_mapping.to_json(),
                },
            ],
        )
        mock_wait_for_publish_task.assert_called_once_with("fake-change-set-id")

    @mock.patch("cloudpub.aws.AWSProductService.wait_for_publish_task")
    def test_publish_keepdraft(
        self,
        mock_wait_for_publish_task: mock.MagicMock,
        aws_service: AWSProductService,
        version_metadata_obj: AWSVersionMetadata,
        mock_start_change_set: mock.MagicMock,
    ) -> None:
        mock_start_change_set.return_value = {"ChangeSetId": "fake-change-set-id"}

        version_metadata_obj.keepdraft = True
        aws_service.publish(version_metadata_obj)

        mock_start_change_set.assert_not_called()
        mock_wait_for_publish_task.assert_not_called()
