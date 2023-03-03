# SPDX-License-Identifier: GPL-3.0-or-later
import json
import logging
import time
from copy import deepcopy
from typing import Any, Dict, List

from boto3.session import Session

from cloudpub.common import BaseService, PublishingMetadata
from cloudpub.error import InvalidStateError, NotFoundError, Timeout
from cloudpub.models.aws import VersionMapping

log = logging.getLogger(__name__)


class AWSVersionMetadata(PublishingMetadata):
    """A collection of metadata necessary for publishing a AMI into a product."""

    def __init__(self, version_mapping: VersionMapping, marketplace_entity_type: str, **kwargs):
        """
        Create a new AWS Version Metadata object.

        Args:
            version_mapping (VersionMapping)
                A mapping of all the information to add a new version
            marketplace_entity_type (str)
                Product type of the AWS product
                Example: AmiProduct
        """
        self.marketplace_entity_type = marketplace_entity_type
        self.version_mapping = version_mapping

        super(AWSVersionMetadata, self).__init__(**kwargs)


class AWSProductService(BaseService[AWSVersionMetadata]):
    """Create a new service provider for AWS using Boto3."""

    # Boto3 docs
    # https://boto3.amazonaws.com/v1/documentation/api/latest/guide/quickstart.html

    def __init__(
        self,
        access_id: str,
        secret_key: str,
        region: str = "us-east-1",
    ) -> None:
        """
        AWS cloud provider service.

        Args:
            access_id (str)
                AWS account access ID
            secret_key (str)
                AWS account secret access key
            region (str, optional)
                AWS region for compute operations
                This defaults to 'us-east-1'
        """
        self.session = Session(
            aws_access_key_id=access_id,
            aws_secret_access_key=secret_key,
            region_name=region,
        )

        self.marketplace = self.session.client("marketplace-catalog")

        super(AWSProductService, self).__init__()

    def get_product_by_id(self, entity_id: str) -> Dict[str, Any]:
        """
        Get a product detail by it's id.

        Args:
            entity_id (str)
                Entity id to get details from. If not set will default to
                class setting for EntityId.
        Returns:
            List[Dict[str, Any]]: A dict of details for a product
        Raises:
            NotFoundError when the product is not found.
        """
        rsp = self.marketplace.describe_entity(Catalog="AWSMarketplace", EntityId=entity_id)
        details_dict = rsp.get("Details")

        if not details_dict:
            log.debug(f"The response was: {rsp}")
            self._raise_error(NotFoundError, f"No such product with EntityId: \"{entity_id}\"")

        details = json.loads(details_dict)

        return details

    def get_product_by_name(
        self, marketplace_entity_type: str, product_name: str
    ) -> Dict[str, Any]:
        """
        Get a product detail by it's name.

        Args:
            marketplace_entity_type (str)
                Product type of the AWS product
                Example: AmiProduct
            product_name (str)
                Name of a product
        Returns:
            str: A dict of details for the first response of a product
        Raises:
            NotFoundError when the product is not found.
        """
        filter_list = [{"Name": "Name", "ValueList": [product_name]}]

        entity_rsp = self.marketplace.list_entities(
            Catalog="AWSMarketplace",
            EntityType=marketplace_entity_type,
            FilterList=filter_list,
        )

        if len(entity_rsp["EntitySummaryList"]) == 0 and isinstance(
            entity_rsp["EntitySummaryList"], list
        ):
            log.debug(f"The response was: {entity_rsp}")
            self._raise_error(NotFoundError, f"No such product with name \"{product_name}\"")

        if len(entity_rsp["EntitySummaryList"]) > 1:
            log.debug(f"The response was: {entity_rsp}")
            self._raise_error(InvalidStateError, f"Multiple responses found for \"{product_name}\"")

        # We should only get one response based on filtering
        if "EntityId" in entity_rsp["EntitySummaryList"][0]:
            return self.get_product_by_id(entity_rsp["EntitySummaryList"][0]["EntityId"])

        self._raise_error(NotFoundError, f"No such product with name \"{product_name}\"")

    def get_product_version_details(self, entity_id: str, version_id: str) -> List[Dict[str, Any]]:
        """
        Get a product detail by it's name.

        Args:
            entity_id (str)
                The Id of the entity to edit
            version_id (str)
                The version id of a product to get the details of
        Returns:
            List[Dict[str, Any]]: A dict of details for the first response of a product
        Raises:
            NotFoundError when the product is not found.
        """
        details = self.get_product_by_id(entity_id)

        if "Versions" not in details.keys() or not isinstance(details["Versions"], list):
            log.debug(f"The details from the response are: {details}")
            self._raise_error(NotFoundError, "This product has no versions")

        for version in details["Versions"]:
            for delivery_option in version["DeliveryOptions"]:
                if delivery_option["Id"] == version_id:
                    return version

        self._raise_error(NotFoundError, f"No such version with id \"{version_id}\"")

    def get_product_version_ids(self, entity_id: str) -> List[Dict[str, Any]]:
        """
        Get the ids of all the versions of a product. Product is searched by it's id.

        Args:
            entity_id (str)
                The Id of the entity to edit
        Returns:
            List[Dict[str, Any]]: A list of version ids
        Raises:
            NotFoundError when the product is not found.
        """
        details = self.get_product_by_id(entity_id)

        if "Versions" not in details.keys() or not isinstance(details["Versions"], list):
            log.debug(f"The details from the response are: {details}")
            self._raise_error(NotFoundError, "This product has no versions")

        version_ids: List[Dict[str, Any]] = []

        for v in details["Versions"]:
            delivery_ids = []
            for delivery_option in v["DeliveryOptions"]:
                delivery_ids.append(delivery_option["Id"])
            version = {v["VersionTitle"]: delivery_ids}
            version_ids.append(version)

        return version_ids

    def get_product_version_by_name(self, entity_id: str, version_name: str) -> Dict[str, Any]:
        """
        Get a version detail by it's name.

        Args:
            entity_id (str)
                The Id of the entity to edit
            version_name (str)
                A version title to get details of
        Returns:
            Dict[str, Any]: The delivery options of a version
        Raises:
            NotFoundError when the product is not found.
        """
        details = self.get_product_by_id(entity_id)

        if "Versions" not in details.keys() or not isinstance(details["Versions"], list):
            log.debug(f"The details from the response are: {details}")
            self._raise_error(NotFoundError, "This product has no versions")

        for version in details["Versions"]:
            if version["VersionTitle"] == version_name:
                # ATM we're not batching Delivery options so
                # the first one should be the one we want.
                return version["DeliveryOptions"][0]

        self._raise_error(NotFoundError, f"No such version with name \"{version_name}\"")

    def set_restrict_versions(
        self, entity_id: str, marketplace_entity_type: str, delivery_option_ids: List[str]
    ) -> str:
        """
        Restrict version(s) of a product by their id.

        Args:
            entity_id (str)
                The Id of the entity to edit
            marketplace_entity_type (str)
                Product type of the AWS product
                Example: AmiProduct
            delivery_option_ids (List)
                A list of strs of delivery options to restrict. Normally version Ids.
        Returns:
            str: A change set id
        """
        change_details = {"DeliveryOptionIds": delivery_option_ids}

        rsp = self.marketplace.start_change_set(
            Catalog="AWSMarketplace",
            ChangeSet=[
                {
                    "ChangeType": "RestrictDeliveryOptions",
                    "Entity": {
                        "Type": marketplace_entity_type + "@1.0",
                        "Identifier": entity_id,
                    },
                    "Details": json.dumps(change_details),
                },
            ],
        )

        log.debug(f"The response from the restrict version was: {rsp}")

        return rsp["ChangeSetId"]

    def cancel_change_set(self, change_set_id: str) -> str:
        """
        Cancel the publish of a new version in progress.

        Args:
            change_set_id (str)
                A change set id to cancel
        Returns:
            str: A change set id
        """
        rsp = self.marketplace.cancel_change_set(
            Catalog="AWSMarketplace", ChangeSetId=change_set_id
        )

        log.debug(f"The response from cancelling a changeset was: {rsp}")

        return rsp["ChangeSetId"]

    def check_publish_status(self, change_set_id: str) -> str:
        """
        Check the status of a change set.

        Args:
            change_set_id (str)
                A change set id to check the status of
        Returns:
            str: Status of the publish
        Raises:
            InvalidStateError if the job failed
        """
        rsp = self.marketplace.describe_change_set(
            Catalog="AWSMarketplace", ChangeSetId=change_set_id
        )

        status = rsp["Status"]

        log.info("Publishing status is %s.", status)

        if status.lower() == "failed":
            failure_code = rsp["FailureCode"]
            # ATM we're not batching changesets so
            # the first one should be the one we want.
            failure_list = rsp["ChangeSet"][0]["ErrorDetailList"]
            log.debug(f"The response from the status was: {rsp}")
            error_message = (
                f"Changeset {change_set_id} failed with code {failure_code}: \n {failure_list}"
            )
            self._raise_error(InvalidStateError, error_message)

        return rsp["Status"]

    def wait_for_publish_task(
        self, change_set_id: str, attempts: int = 480, interval: int = 4
    ) -> None:
        """
        Wait until ChangeSet is complete.

        Args:
            change_set_id (str)
                Id for the change set
            attempts (int, optional)
                Max number of times to poll
                Defaults to 480
            interval (int, optional)
                Seconds between polling
                Defaults to 4
        Raises:
            Timeout when the status doesn't change to either
            'Succeeded' or 'Failed' within the set retry time.
        """
        # Future addition: use get_waiter() to wait for change set to complete
        queries = 0
        status = ""
        while status.lower() != "succeeded":
            queries += 1
            if queries > attempts:
                self._raise_error(Timeout, f"Timed out waiting for {change_set_id} to finish")

            time.sleep(interval)

            status = self.check_publish_status(change_set_id)

    def start_image_scan(self, ami_id: str) -> None:
        """
        Start scan for an image (To be added in future release).

        Args:
            ami_id (str)
                The ami id to start the scan on
        Returns:
            str: An id to check status of scan
        """
        # to be added in the future
        self._raise_error(NotImplementedError, "To be added at a future date")

    def check_image_scan(self, ami_id: str) -> None:
        """
        Check to see if an image has been scanned (To be added in future release).

        Args:
            ami_id (str)
                The ami id to start the scan on
        Returns:
            Bool: True/False of if an image has been scanned
        """
        self._raise_error(NotImplementedError, "To be added at a future date")

    def publish(self, metadata: AWSVersionMetadata) -> None:
        """
        Add new version to an existing product.

        Args:
            new_version_details (VersionMapping): A model of the version mapping
        """
        if metadata.keepdraft:
            return None

        if metadata.overwrite:
            # Make a copy of the original Version Mapping to avoid overwriting settings
            json_mapping = deepcopy(metadata.version_mapping)
            org_version_details = self.get_product_version_by_name(
                metadata.destination, metadata.version_mapping.version.version_title
            )
            # ATM we're not batching Delivery options so
            # the first one should be the one we want.
            json_mapping.delivery_options[0].id = org_version_details["Id"]
            change_set = [
                {
                    "ChangeType": "UpdateDeliveryOptions",
                    "Entity": {
                        "Type": f"{metadata.marketplace_entity_type}@1.0",
                        "Identifier": metadata.destination,
                    },
                    # AWS accepts 'Details' as a JSON string.
                    # So we convert it here.
                    "Details": json.dumps(json_mapping.to_json()),
                },
            ]
        else:
            change_set = [
                {
                    "ChangeType": "AddDeliveryOptions",
                    "Entity": {
                        "Type": f"{metadata.marketplace_entity_type}@1.0",
                        "Identifier": metadata.destination,
                    },
                    # AWS accepts 'Details' as a JSON string.
                    # So we convert it here.
                    "Details": json.dumps(metadata.version_mapping.to_json()),
                },
            ]

        rsp = self.marketplace.start_change_set(
            Catalog="AWSMarketplace",
            ChangeSet=change_set,
        )

        log.debug(f"The response from publishing was: {rsp}")

        self.wait_for_publish_task(rsp["ChangeSetId"])
