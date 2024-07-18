# SPDX-License-Identifier: GPL-3.0-or-later
import json
import logging
from copy import deepcopy
from typing import Dict, List, Optional

from boto3.session import Session
from tenacity import RetryError, Retrying
from tenacity.retry import retry_if_result
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_fixed

from cloudpub.aws.utils import (
    create_version_tree,
    get_restricted_major_versions,
    get_restricted_minor_versions,
    get_restricted_patch_versions,
    pprint_debug_logging,
)
from cloudpub.common import BaseService, PublishingMetadata
from cloudpub.error import InvalidStateError, NotFoundError, Timeout
from cloudpub.models.aws import (
    ChangeSetResponse,
    DeliveryOption,
    DescribeChangeSetReponse,
    DescribeEntityResponse,
    GroupedVersions,
    ListChangeSet,
    ListChangeSetsResponse,
    ListEntitiesResponse,
    ProductDetailResponse,
    ProductVersionsResponse,
    ProductVersionsVirtualizationSource,
    VersionMapping,
)

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
        attempts: int = 288,
        interval: int = 600,
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
            attempts (int, optional)
                Max number of times to poll
                while waiting for changeset
                Defaults to 288
            interval (int, optional)
                Seconds between polling
                while waiting for changeset
                Defaults to 600
        """
        self.session = Session(
            aws_access_key_id=access_id,
            aws_secret_access_key=secret_key,
            region_name=region,
        )

        self.marketplace = self.session.client("marketplace-catalog")
        self.wait_for_changeset_attempts = attempts
        self.wait_for_changeset_interval = interval

        super(AWSProductService, self).__init__()

    def _check_product_versions(self, details: ProductDetailResponse) -> None:
        if not details.versions:
            pprint_debug_logging(log, details.to_json(), "The details from the response are: ")
            self._raise_error(NotFoundError, "This product has no versions")

    def get_product_by_id(self, entity_id: str) -> ProductDetailResponse:
        """
        Get a product detail by it's id.

        Args:
            entity_id (str)
                Entity id to get details from. If not set will default to
                class setting for EntityId.
        Returns:
            ProductDetailResponse: The details for a product
        Raises:
            NotFoundError when the product is not found.
        """
        rsp = DescribeEntityResponse.from_json(
            self.marketplace.describe_entity(Catalog="AWSMarketplace", EntityId=entity_id)
        )

        if not rsp.details_document:
            pprint_debug_logging(log, rsp)
            self._raise_error(NotFoundError, f"No such product with EntityId: \"{entity_id}\"")

        return rsp.details_document

    def get_product_by_name(
        self, marketplace_entity_type: str, product_name: str
    ) -> ProductDetailResponse:
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
            InvalidStateError when more than one product is found.
        """
        filter_list = [{"Name": "Name", "ValueList": [product_name]}]

        entity_rsp = ListEntitiesResponse.from_json(
            self.marketplace.list_entities(
                Catalog="AWSMarketplace",
                EntityType=marketplace_entity_type,
                FilterList=filter_list,
            )
        )

        if len(entity_rsp.entity_summary_list) == 0:
            pprint_debug_logging(log, entity_rsp)
            self._raise_error(NotFoundError, f"No such product with name \"{product_name}\"")

        elif len(entity_rsp.entity_summary_list) > 1:
            pprint_debug_logging(log, entity_rsp)
            self._raise_error(InvalidStateError, f"Multiple responses found for \"{product_name}\"")

        # We should only get one response based on filtering
        elif hasattr(entity_rsp.entity_summary_list[0], "entity_id"):
            return self.get_product_by_id(entity_rsp.entity_summary_list[0].entity_id)

        self._raise_error(NotFoundError, f"No such product with name \"{product_name}\"")

    def get_product_version_details(
        self, entity_id: str, version_id: str
    ) -> ProductVersionsResponse:
        """
        Get a product detail by it's name.

        Args:
            entity_id (str)
                The Id of the entity to get version details from
            version_id (str)
                The version id of a product to get the details of
        Returns:
            ProductVersionsResponse: The details for the first response of a product
        Raises:
            NotFoundError when the product is not found.
        """
        details = self.get_product_by_id(entity_id)
        self._check_product_versions(details)

        for version in details.versions:
            for delivery_option in version.delivery_options:
                if delivery_option.id == version_id:
                    return version

        self._raise_error(NotFoundError, f"No such version with id \"{version_id}\"")

    def get_product_versions(self, entity_id: str) -> Dict[str, GroupedVersions]:
        """
        Get the titles, ids, and date created of all the versions of a product.

        Args:
            entity_id (str)
                The Id of the entity to get versions from
        Returns:
            Dict[str, GroupedVersions]: A dictionary of versions
        Raises:
            NotFoundError when the product is not found.
        """
        details = self.get_product_by_id(entity_id)
        self._check_product_versions(details)

        version_ids: Dict[str, GroupedVersions] = {}

        for v in details.versions:
            delivery_options_list = []
            ami_id_list = []
            for delivery_option in v.delivery_options:
                delivery_options_list.append(delivery_option)
            for source in v.sources:
                if isinstance(source, ProductVersionsVirtualizationSource):
                    ami_id_list.append(source.image)
            delivery_options: GroupedVersions = {
                "delivery_options": delivery_options_list,
                "created_date": v.creation_date,  # type: ignore
                "ami_ids": ami_id_list,
            }
            version_ids[v.version_title] = delivery_options  # type: ignore
        return version_ids

    def get_product_version_by_name(self, entity_id: str, version_name: str) -> DeliveryOption:
        """
        Get a version detail by it's name.

        Args:
            entity_id (str)
                The Id of the entity to get version by name from
            version_name (str)
                A version title to get details of
        Returns:
            DeliveryOption: The delivery options of a version
        Raises:
            NotFoundError when the product is not found.
        """
        details = self.get_product_by_id(entity_id)
        self._check_product_versions(details)

        for version in details.versions:
            if version.version_title == version_name:
                # ATM we're not batching Delivery options so
                # the first one should be the one we want.
                return version.delivery_options[0]

        self._raise_error(NotFoundError, f"No such version with name \"{version_name}\"")

    def get_product_active_changesets(self, entity_id: str) -> List[ListChangeSet]:
        """
        Get the active changesets for a product.

        Args:
            entity_id (str)
                The Id of the entity to get active changesets from
        Returns:
            str: A change set id
        """
        filter_list = [
            {"Name": "EntityId", "ValueList": [entity_id]},
            {"Name": "Status", "ValueList": ["APPLYING", "PREPARING"]},
        ]

        changeset_list = ListChangeSetsResponse.from_json(
            self.marketplace.list_change_sets(Catalog="AWSMarketplace", FilterList=filter_list)
        )
        return changeset_list.change_set_list

    def wait_active_changesets(self, entity_id: str) -> None:
        """
        Get the first active changeset, if there is one, and wait for it to finish.

        Args:
            entity_id (str)
                The Id of the entity to wait for active changesets
        """

        def changeset_not_complete(change_set_list: List[ListChangeSet]) -> bool:
            if change_set_list:
                self.wait_for_changeset(change_set_list[0].id)
                return True
            else:
                return False

        r = Retrying(
            stop=stop_after_attempt(self.wait_for_changeset_attempts),
            retry=retry_if_result(changeset_not_complete),
        )

        try:
            r(self.get_product_active_changesets, entity_id)
        except RetryError:
            self._raise_error(Timeout, f"Timed out waiting for {entity_id} to be unlocked")

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

        rsp: ChangeSetResponse = self.marketplace.start_change_set(
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

        pprint_debug_logging(log, rsp, "The response from the restrict version was: ")

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
        rsp: ChangeSetResponse = self.marketplace.cancel_change_set(
            Catalog="AWSMarketplace", ChangeSetId=change_set_id
        )

        pprint_debug_logging(log, rsp, "The response from cancelling a changeset was: ")

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
        rsp = DescribeChangeSetReponse.from_json(
            self.marketplace.describe_change_set(
                Catalog="AWSMarketplace", ChangeSetId=change_set_id
            )
        )

        status = rsp.status

        log.info("Current change status is %s.", status.lower())

        if status.lower() == "failed":
            failure_code = rsp.failure_code
            # ATM we're not batching changesets so
            # the first one should be the one we want.
            failure_list = rsp.change_set[0].error_details
            pprint_debug_logging(log, rsp, "The response from the status was: ")
            error_message = (
                f"Changeset {change_set_id} failed with code {failure_code}: \n {failure_list}"
            )
            self._raise_error(InvalidStateError, error_message)

        return rsp.status

    def wait_for_changeset(self, change_set_id: str) -> None:
        """
        Wait until ChangeSet is complete.

        Args:
            change_set_id (str)
                Id for the change set to wait on
        Raises:
            Timeout when the status doesn't change to either
            'Succeeded' or 'Failed' within the set retry time.
        """

        def changeset_not_complete(status: str) -> bool:
            if status.lower() == "succeeded":
                return False
            else:
                return True

        r = Retrying(
            wait=wait_fixed(self.wait_for_changeset_interval),
            stop=stop_after_attempt(self.wait_for_changeset_attempts),
            retry=retry_if_result(changeset_not_complete),
        )

        try:
            r(self.check_publish_status, change_set_id)
        except RetryError:
            self._raise_error(Timeout, f"Timed out waiting for {change_set_id} to finish")

    def restrict_versions(
        self,
        entity_id: str,
        marketplace_entity_type: str,
        restrict_major: Optional[int] = None,
        restrict_minor: Optional[int] = 1,
    ) -> List[str]:
        """
        Restrict the old versions of a release.

        Args:
            entity_id (str)
                The entity id to modifiy.
            marketplace_entity_type (str)
                Product type of the AWS product
                Example: AmiProduct
            restrict_major (optional int)
                How many major versions are allowed
                Example: 3
            restrict_minor (optional int)
                how many minor versions are allowed
                Example: 3
        Returns:
            List[str]: List of AMI ids of restricted versions
        """
        versions = self.get_product_versions(entity_id)
        version_tree = create_version_tree(versions)

        restrict_delivery_ids = []
        restrict_ami_ids = []

        if restrict_major and len(version_tree) > restrict_major:
            major_delivery_ids, major_ami_ids, version_tree = get_restricted_major_versions(
                version_tree, restrict_major
            )
            restrict_delivery_ids.extend(major_delivery_ids)
            restrict_ami_ids.extend(major_ami_ids)

        if restrict_minor:
            minor_delivery_ids, minor_ami_ids, version_tree = get_restricted_minor_versions(
                version_tree, restrict_minor
            )
            restrict_delivery_ids.extend(minor_delivery_ids)
            restrict_ami_ids.extend(minor_ami_ids)

        patch_delivery_ids, patch_ami_ids = get_restricted_patch_versions(version_tree)
        restrict_delivery_ids.extend(patch_delivery_ids)
        restrict_ami_ids.extend(patch_ami_ids)

        if restrict_delivery_ids:
            log.debug(f"Restricting these minor version(s) with id(s): {restrict_delivery_ids}")
            change_id = self.set_restrict_versions(
                entity_id, marketplace_entity_type, restrict_delivery_ids
            )
            self.wait_for_changeset(change_id)

        return restrict_ami_ids

    def publish(self, metadata: AWSVersionMetadata) -> None:
        """
        Add new version to an existing product.

        Args:
            new_version_details (VersionMapping): A model of the version mapping
        """
        change_set = {
            "ChangeType": "AddDeliveryOptions",
            "Entity": {
                "Type": f"{metadata.marketplace_entity_type}@1.0",
                "Identifier": metadata.destination,
            },
            # AWS accepts 'Details' as a JSON string.
            # So we convert it here.
            "DetailsDocument": metadata.version_mapping.to_json(),
        }

        if metadata.overwrite:
            # Make a copy of the original Version Mapping to avoid overwriting settings
            json_mapping = deepcopy(metadata.version_mapping)
            org_version_details = self.get_product_version_by_name(
                metadata.destination, metadata.version_mapping.version.version_title
            )
            # ATM we're not batching Delivery options so
            # the first one should be the one we want.
            json_mapping.delivery_options[0].id = org_version_details.id

            change_set["ChangeType"] = "UpdateDeliveryOptions"
            change_set["DetailsDocument"] = json_mapping.to_json()

        if metadata.keepdraft:
            log.info("Sending draft version to %s.", metadata.marketplace_entity_type)
            rsp: ChangeSetResponse = self.marketplace.start_change_set(
                Catalog="AWSMarketplace", ChangeSet=[change_set], Intent="VALIDATE"
            )
        else:
            log.info("Publishing new version in %s.", metadata.marketplace_entity_type)
            rsp = self.marketplace.start_change_set(
                Catalog="AWSMarketplace", ChangeSet=[change_set], Intent="APPLY"
            )
        pprint_debug_logging(log, rsp, "The response from publishing was: ")

        self.wait_for_changeset(rsp["ChangeSetId"])
