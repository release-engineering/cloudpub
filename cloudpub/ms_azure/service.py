# SPDX-License-Identifier: GPL-3.0-or-later
import json
import logging
import os
from enum import IntEnum
from typing import Any, Dict, Iterator, List, Optional, Tuple, Union, cast

from deepdiff import DeepDiff
from requests import HTTPError
from tenacity import retry
from tenacity.retry import retry_if_result
from tenacity.stop import stop_after_attempt, stop_after_delay
from tenacity.wait import wait_chain, wait_fixed

from cloudpub.common import BaseService
from cloudpub.error import InvalidStateError, NotFoundError
from cloudpub.models.ms_azure import (
    RESOURCE_MAPING,
    AzureResource,
    ConfigureStatus,
    CustomerLeads,
    DiskVersion,
    Listing,
    ListingAsset,
    ListingTrailer,
    OSDiskURI,
    PlanListing,
    PlanSummary,
    PriceAndAvailabilityOffer,
    PriceAndAvailabilityPlan,
    Product,
    ProductProperty,
    ProductReseller,
    ProductSubmission,
    ProductSummary,
    TestDrive,
    VMImageSource,
    VMIPlanTechConfig,
)
from cloudpub.ms_azure.session import PartnerPortalSession
from cloudpub.ms_azure.utils import (
    AzurePublishingMetadata,
    TechnicalConfigLookUpData,
    create_disk_version_from_scratch,
    is_azure_job_not_complete,
    is_sas_present,
    logdiff,
    seek_disk_version,
    set_new_sas_disk_version,
    update_skus,
)
from cloudpub.utils import get_url_params

log = logging.getLogger(__name__)


AZURE_PRODUCT_RESOURCES = Union[
    CustomerLeads,
    Listing,
    ListingAsset,
    ListingTrailer,
    PlanListing,
    PlanSummary,
    PriceAndAvailabilityOffer,
    PriceAndAvailabilityPlan,
    ProductProperty,
    ProductReseller,
    ProductSubmission,
    ProductSummary,
    TestDrive,
    VMIPlanTechConfig,
]


class SasFoundStatus(IntEnum):
    """Represent the submission target level of SAS found in a given product."""

    missing = 0
    draft = 1
    preview = 2
    live = 3


class AzureService(BaseService[AzurePublishingMetadata]):
    """Service provider for Microsoft Azure using the Product Ingestion API."""

    # Product ingestion API Docs:
    # https://learn.microsoft.com/en-us/azure/marketplace/product-ingestion-api

    AZURE_API_VERSION = os.environ.get("AZURE_API_VERSION", "2022-07-01")
    AZURE_SCHEMA_VERSION = os.environ.get("AZURE_SCHEMA_VERSION", "2022-07-01")
    CONFIGURE_SCHEMA = "https://schema.mp.microsoft.com/schema/configure/{AZURE_API_VERSION}"
    DIFF_EXCLUDES = [r"root\['resources'\]\[[0-9]+\]\['url'\]"]

    def __init__(self, credentials: Dict[str, str]):
        """
        Create a new AuzureService object.

        Args:
            credentials (dict)
                Dictionary with Azure credentials to authenticate on Product Ingestion API.
        """
        self.session = PartnerPortalSession.make_graph_api_session(
            auth_keys=credentials, schema_version=self.AZURE_SCHEMA_VERSION
        )
        self._products: List[ProductSummary] = []

    def _configure(self, data: Dict[str, Any]) -> ConfigureStatus:
        """
        Submit a `configure` request to create or modify an Azure resource.

        Args:
            data (dict)
                The configure request data to send to the Product Ingestion API.
        Returns:
            The job ID to track its status alongside the initial status.
        """
        if log.isEnabledFor(logging.DEBUG):
            log.debug(
                "Received the following data to create/modify: %s", json.dumps(data, indent=2)
            )
        resp = self.session.post(path="configure", json=data)
        self._raise_for_status(response=resp)
        rsp_data = resp.json()
        log.debug("Create/modify request response: %s", rsp_data)
        parsed_resp = ConfigureStatus.from_json(rsp_data)
        return parsed_resp

    def _query_job_details(self, job_id: str) -> ConfigureStatus:
        """
        Get a `configure` job status.

        Args:
            job_id (str)
                The job ID from a `configure` request.
        Returns:
            The updated job status.
        """
        log.debug("Query job details for \"%s\"", job_id)
        resp = self.session.get(path=f"configure/{job_id}/status")

        # We don't want to fail if there's a server error thus we make a fake
        # response for it so the query job details will be retried.
        if resp.status_code >= 500:
            log.warning(
                (
                    "Got HTTP %s from server when querying job %s status."
                    " Considering the job_status as \"pending\".",
                ),
                resp.status_code,
                job_id,
            )
            return ConfigureStatus.from_json(
                {
                    "job_id": job_id,
                    "job_status": "pending",
                }
            )

        self._raise_for_status(response=resp)
        parsed_resp = ConfigureStatus.from_json(resp.json())
        log.debug("Query Job details response: %s", parsed_resp)
        return parsed_resp

    @retry(
        retry=retry_if_result(predicate=is_azure_job_not_complete),
        wait=wait_chain(
            *[wait_fixed(wait=60)]  # First wait for 1 minute  # noqa: W503
            + [wait_fixed(wait=10 * 60)]  # Then wait for 10 minutes  # noqa: W503
            + [wait_fixed(wait=30 * 60)]  # Finally wait each 30 minutes  # noqa: W503
        ),
        stop=stop_after_delay(max_delay=60 * 60 * 24 * 7),  # Give up after retrying for 7 days
    )
    def _wait_for_job_completion(self, job_id: str) -> ConfigureStatus:
        """
        Wait until the specified job ID is complete.

        By using the retry we repeat this action  until the `jobStatus` will be `completed`.
        The `jobStatus` values may be: `notStarted`, `running` or `completed`

        When it is `completed` we will get the `jobResult`.
        The `JobResult` values may be: `pending`, `succeeded` or `failed`.

        Args:
            job_id (str)
                The job id to get the details for.
        Returns:
            The job details in case of success
        Raises:
            InvalidStateError if the job failed
        """
        job_details = self._query_job_details(job_id=job_id)
        if job_details.job_result == "failed":
            error_message = f"Job {job_id} failed: \n{job_details.errors}"
            self._raise_error(InvalidStateError, error_message)
        elif job_details.job_result == "succeeded":
            log.debug("Job %s succeeded", job_id)
        return job_details

    def configure(self, resources: List[AzureResource]) -> ConfigureStatus:
        """
        Create or update a resource and wait until it's done.

        Args:
            resources (List[AzureResource]):
                The list of resources to create/modify in Azure.
        Returns:
            dict: The result of job execution
        """
        data = {
            "$schema": self.CONFIGURE_SCHEMA.format(AZURE_API_VERSION=self.AZURE_API_VERSION),
            "resources": [x.to_json() for x in resources],
        }
        if log.isEnabledFor(logging.DEBUG):
            log.debug("Data to configure: %s", json.dumps(data, indent=2))
        res = self._configure(data=data)
        return self._wait_for_job_completion(job_id=res.job_id)

    @property
    def products(self) -> Iterator[ProductSummary]:
        """Iterate over all products from Azure Marketplace."""
        has_next = True
        params: Dict[str, str] = {}

        while has_next:
            log.info("Requesting the products list.")
            resp = self.session.get(path="/product", params=params)
            data = self._assert_dict(resp)

            values = data.get("value", [])
            if not isinstance(values, list):
                err = f"Expected response.values to contain a list, got {type(values)}."
                self._raise_error(ValueError, err)

            # Yield the values
            for v in values:
                yield ProductSummary.from_json(v)

            # Get the nextLink parameters or cease the loop
            params = get_url_params(data.get("@nextLink", ""))
            if not params:
                has_next = False

    def list_products(self) -> List[ProductSummary]:
        """
        Return a list with the summary of products registerd in Azure.

        Returns:
            list: A list with ProductSummary for all products in Azure.
        """
        log.info("Listing the products on Azure server.")
        if not self._products:
            self._products = [p for p in self.products]
        return self._products

    def get_productid(self, product_name: str) -> str:
        """Retrieve the desired product ID for the requested product name.

        Args:
            product_name (str): the product's name to retrieve its product ID.
        Returns:
            The requested product ID when found.
        Raises NotFoundError when the product was not found.
        """
        for product in self.list_products():
            if product.identity.name == product_name:
                return product.id
        raise NotFoundError(f"No such product with name {product_name}")

    def get_product(self, product_id: str, target: str) -> Product:
        """
        Return the requested Product by its ID.

        It will return the product with the latest publishing status, trying to
        fetch it in the following order: "preview" -> "draft" -> "live". The first
        status to fech must be "preview" in order to indepotently detect an existing
        publishing which could be missing to go live.

        Args:
            product_durable_id (str)
                The product UUID
            target (str)
                The submission target to retrieve the product from.
        Returns:
            Product: the requested product
        """
        log.info("Requesting the product ID \"%s\" with state \"%s\".", product_id, target)
        try:
            resp = self.session.get(
                path=f"/resource-tree/product/{product_id}", params={"targetType": target}
            )
            data = self._assert_dict(resp)
            return Product.from_json(data)
        except (ValueError, HTTPError):
            log.debug("Couldn't find the product \"%s\" with state \"%s\"", product_id, target)
        self._raise_error(NotFoundError, f"No such product with id \"{product_id}\"")

    def get_product_by_name(self, product_name: str, target: str) -> Product:
        """
        Return the requested Product by its name from Legacy CPP API.

        Args:
            product_name (str)
                The product name according to Legacy CPP API.
            target (str, optional)
                The submission target to retrieve the product from.
        Returns:
            Product: the requested product when found
        Raises:
            NotFoundError when the product is not found.
        """
        for product in self.products:
            if product.identity.name == product_name:
                log.debug("Product alias \"%s\" has the ID \"%s\"", product_name, product.id)
                return self.get_product(product.id, target=target)
        self._raise_error(NotFoundError, f"No such product with name \"{product_name}\"")

    def get_submissions(self, product_id: str) -> List[ProductSubmission]:
        """
        Return a list of submissions for the given Product id.

        Args:
            product_id (str): The Product id to retrieve the submissions.

        Returns:
            List[ProductSubmission]: List of all submissions for the given Product.
        """
        log.debug("Requesting the submissions for product \"%s\".", product_id)
        resp = self.session.get(path=f"/submission/{product_id}")
        data = self._assert_dict(resp)
        return [ProductSubmission.from_json(x) for x in data.get("value", [])]

    def get_submission_state(self, product_id, state="preview") -> Optional[ProductSubmission]:
        """
        Retrieve a particular submission with the given state from the given Product id.

        Args:
            product_id (_type_): The product id to request the submissions.
            state (str, optional): The state to filter the submission. Defaults to "preview".

        Returns:
            Optional[ProductSubmission]: The requested submission when found.
        """
        log.info("Looking up for submission in state \"%s\" for \"%s\"", state, product_id)
        submissions = self.get_submissions(product_id)
        for sub in submissions:
            if sub.target.targetType == state:
                return sub
        return None

    def filter_product_resources(
        self, product: Product, resource: str
    ) -> List[AZURE_PRODUCT_RESOURCES]:
        """
        Return a subset of Product resources with the corresponding type.

        Args:
            product (Product)
                The product to retrieve the resources from.
            resource (str):
                The resource type
        Returns:
            list: The subset of resources by the given type
        """
        if resource not in RESOURCE_MAPING:
            err = f"Invalid resource type \"{resource}\". Expected {RESOURCE_MAPING.keys()}"
            self._raise_error(ValueError, err)

        log.debug("Filtering the resource \"%s\" for product ID \"%s\"", resource, product.id)
        res = []
        for r in product.resources:
            if isinstance(r, RESOURCE_MAPING[resource]):
                res.append(r)
        log.debug("Filtered resources \"%s\" for product ID \"%s\": %s", resource, product.id, res)
        return cast(List[AZURE_PRODUCT_RESOURCES], res)

    def get_plan_by_name(self, product: Product, plan_name: str) -> PlanSummary:
        """
        Return the respective plan by searching for its name.

        Args:
            product (Product)
                The product to retrieve the plans from.
            plan_name (str):
                The plan name to filter
        Returns:
            PlanSummary: The respective plan summary when found
        """
        resources = cast(
            List[PlanSummary], self.filter_product_resources(product=product, resource="plan")
        )

        for p in resources:
            if p.identity.name == plan_name:
                log.debug("Plan alias \"%s\" has the ID \"%s\"", plan_name, p.id)
                return p
        self._raise_error(NotFoundError, f"No such plan with name \"{plan_name}\"")

    def get_product_plan_by_name(
        self,
        product_name: str,
        plan_name: str,
        target: str,
    ) -> Tuple[Product, PlanSummary]:
        """Return a tuple with the desired Product and Plan after iterating over all targets.

        Args:
            product_name (str): The name of the product to search for
            plan_name (str): The name of the plan to search for
            target (str)
                The submission target to retrieve the product/plan from.
        Returns:
            Tuple[Product, PlanSummary]: The Product and PlanSummary when fonud
        Raises:
            NotFoundError whenever no information was found in the respective submission target.
        """
        try:
            product = self.get_product_by_name(product_name, target=target)
            plan = self.get_plan_by_name(product, plan_name)
            return product, plan
        except NotFoundError:
            self._raise_error(
                NotFoundError, f"No such plan with name \"{plan_name} for {product_name}\""
            )

    def diff_offer(self, product: Product, target: str) -> DeepDiff:
        """Compute the difference between the provided product and the one in the remote.

        Args:
            product (Product)
                The local product to diff with the remote one.
            target (str)
                The submission target to retrieve the product from.
        Returns:
            DeepDiff: The diff data.
        """
        remote = self.get_product(product.id, target=target)
        return DeepDiff(remote.to_json(), product.to_json(), exclude_regex_paths=self.DIFF_EXCLUDES)

    def submit_to_status(
        self, product_id: str, status: str, resources: Optional[List[AzureResource]] = None
    ) -> ConfigureStatus:
        """
        Send a submission request to Microsoft with a new Product status.

        Args:
            product_id (str)
                The product ID to submit the new status.
            status (str)
                The new status: 'preview' or 'live'
            resources (optional(list(AzureRerouce)))
                Additional resources for modular push.
        Returns:
            The response from configure request.
        """
        log.info("Submitting the status of \"%s\" to \"%s\"", product_id, status)
        # We need to get the previous state of the given one to request the submission
        prev_state_mapping = {
            "preview": "draft",
            "live": "preview",
        }
        prev_state = prev_state_mapping.get(status, "draft")

        # Now we call the submission with the previous state to get its ID when available
        submission = self.get_submission_state(product_id=product_id, state=prev_state)
        if not submission:
            raise RuntimeError(
                f"Could not find the submission state \"{prev_state}\" for product \"{product_id}\""
            )

        # Update the status with the expected one
        submission.target.targetType = status
        cfg_res: List[AzureResource] = [submission]
        if resources:
            log.info("Performing a modular push to \"%s\" for \"%s\"", status, product_id)
            cfg_res = resources + cfg_res
        log.debug("Set the status \"%s\" to submission.", status)
        return self.configure(resources=cfg_res)

    @retry(
        wait=wait_fixed(300),
        stop=stop_after_delay(max_delay=60 * 60 * 24 * 7),  # Give up after retrying for 7 days,
        reraise=True,
    )
    def ensure_can_publish(self, product_id: str) -> None:
        """
        Ensure the offer is not already being published.

        It will wait for up to 7 days retrying to make sure it's possible to publish before
        giving up and raising.

        Args:
            product_id (str)
                The product ID to check the offer's publishing status
        Raises:
            RuntimeError: whenever a publishing is already in progress.
        """
        log.info("Ensuring no other publishing jobs are in progress for \"%s\"", product_id)
        submission_targets = ["preview", "live"]

        for target in submission_targets:
            sub = self.get_submission_state(product_id, state=target)
            if sub and sub.status and sub.status == "running":
                raise RuntimeError(f"The offer {product_id} is already being published to {target}")

    def get_plan_tech_config(self, product: Product, plan: PlanSummary) -> VMIPlanTechConfig:
        """
        Return the VMIPlanTechConfig resource for the given product/plan.

        Args:
            product
                The product with all resources to retrieve the technical confuguration.
            plan
                The plan match the technical configuration.
        Returns:
            The technical configuration for the requested product/plan.
        """
        log.debug("Retrieving the plan \"%s\" technical configuration.", plan.id)
        tconfigs = cast(
            List[VMIPlanTechConfig],
            [
                tcfg
                for tcfg in self.filter_product_resources(
                    product=product, resource="virtual-machine-plan-technical-configuration"
                )
                if tcfg.plan_id == plan.id  # type: ignore
            ],
        )
        return tconfigs[0]  # It should have only one VMIPlanTechConfig per plan.

    def get_modular_resources_to_publish(
        self, product: Product, tech_config: VMIPlanTechConfig
    ) -> List[AzureResource]:
        """Return the required resources for a modular publishing.

        According to Microsoft docs:
        "For a modular publish, all resources are required except for the product level details
        (for example, listing, availability, packages, reseller) as applicable to your
        product type."

        Args:
            product (Product): The original product to filter the resources from
            tech_config (VMIPlanTechConfig): The updated tech config to publish

        Returns:
            List[AzureResource]: _description_
        """
        # The following resources shouldn't be required:
        # -> customer-leads
        # -> test-drive
        # -> property
        # -> *listing*
        # -> reseller
        # -> price-and-availability-*
        # NOTE: The "submission" resource will be already added by the "submit_to_status" method
        #
        # With that it needs only the related "product" and "plan" resources alongisde the
        # updated tech_config
        product_id = tech_config.product_id
        plan_id = tech_config.plan_id
        prod_res = cast(
            List[ProductSummary],
            [
                prd
                for prd in self.filter_product_resources(product=product, resource="product")
                if prd.id == product_id
            ],
        )[0]
        plan_res = cast(
            List[PlanSummary],
            [
                pln
                for pln in self.filter_product_resources(product=product, resource="plan")
                if pln.id == plan_id
            ],
        )[0]
        return [prod_res, plan_res, tech_config]

    def compute_targets(self, product_id: str) -> List[str]:
        """List all the possible publishing targets order to seek data from Azure.

        It also returns the ordered list of targets with the following precedence:
        ``live`` -> ``preview`` -> ``draft``

        Args:
            product_id (str)
                The product_id to retrieve all existing submission targets.

        Returns:
            List[Str]: The ordered list with targets to lookup.
        """
        all_targets = ["live", "preview", "draft"]
        computed_targets = []

        # We cannot simply return all targets above because the existing product might
        # lack one of them. So now we need to filter out unexisting targets.
        product_submissions = self.get_submissions(product_id)
        product_targets = [s.target.targetType for s in product_submissions]
        for t in all_targets:
            if t in product_targets:
                computed_targets.append(t)
        return computed_targets

    def _is_submission_in_preview(self, current: ProductSubmission) -> bool:
        """Return True if the latest submission state is "preview", False otherwise.

           The product is considered to be in preview if the targetType is "preview" and the
           submission id is not the same from the "live" target.

           See also: https://learn.microsoft.com/en-us/partner-center/marketplace/product-ingestion-api#querying-your-submissions
        Args:
            current (ProductSubmission): the submission from the get_product

        Returns:
            bool: True if the latest submission is "preview", False otherwise
        """  # noqa: E501
        if current.target.targetType != "preview":
            return False

        # We need to check whether there's a live state with the same ID as current
        live = self.get_submission_state(current.product_id, "live")
        if live:
            return current.id != live.id  # If they're the same then state == live
        return True  # when no live it means it's in preview

    @retry(
        wait=wait_fixed(wait=60),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def _publish_preview(
        self, product: Product, product_name: str, resources: Optional[List[AzureResource]] = None
    ) -> None:
        """
        Submit the product to 'preview' after going through Azure Marketplace Validatoin.

        This is required to execute the validation pipeline on Azure side.

        Args:
            product
                The product with changes to publish to preview
            product_name
                The product name to display in logs.
            resources:
                Additional resources for modular push.
        """
        res = self.submit_to_status(product_id=product.id, status='preview', resources=resources)

        if res.job_result != 'succeeded' or not self.get_submission_state(
            product.id, state="preview"
        ):
            errors = "\n".join(res.errors)
            failure_msg = (
                f"Failed to submit the product {product_name} ({product.id}) to preview. "
                f"Status: {res.job_result} Errors: {errors}"
            )
            raise RuntimeError(failure_msg)

    @retry(
        wait=wait_fixed(wait=60),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def _publish_live(self, product: Product, product_name: str) -> None:
        """
        Submit the product to 'live' after going through Azure Marketplace Validation.

        Args:
            product
                The product with changes to publish live
            product_name
                The product name to display in logs.
        """
        # Note: the offer can only go `live` after successfully being changed to `preview`
        # which takes up to 4 days.
        res = self.submit_to_status(product_id=product.id, status='live')

        if res.job_result != 'succeeded' or not self.get_submission_state(product.id, state="live"):
            errors = "\n".join(res.errors)
            failure_msg = (
                f"Failed to submit the product {product_name} ({product.id}) to live. "
                f"Status: {res.job_result} Errors: {errors}"
            )
            raise RuntimeError(failure_msg)

    def _overwrite_disk_version(
        self,
        metadata: AzurePublishingMetadata,
        product_name: str,
        plan_name: str,
        source: VMImageSource,
        target: str,
    ) -> TechnicalConfigLookUpData:
        """Private method to overwrite the technical config with a new DiskVersion.

        Args:
            metadata (AzurePublishingMetadata): the incoming publishing metadata
            product_name (str): the product (offer) name
            plan_name (str): the plan name
            source (VMImageSource): the source VMI to create and overwrite the new DiskVersion
            target (str): the submission target.

        Returns:
            TechnicalConfigLookUpData: The overwritten tech_config for the product/plan
        """
        product, plan = self.get_product_plan_by_name(product_name, plan_name, target)
        log.warning(
            "Overwriting the plan \"%s\" on \"%s\" with the given image: \"%s\".",
            plan_name,
            target,
            metadata.image_path,
        )
        tech_config = self.get_plan_tech_config(product, plan)
        disk_version = create_disk_version_from_scratch(metadata, source)
        tech_config.disk_versions = [disk_version]
        return {
            "metadata": metadata,
            "tech_config": tech_config,
            "sas_found": False,
            "product": product,
            "plan": plan,
            "target": target,
        }

    def _look_up_sas_on_technical_config(
        self, metadata: AzurePublishingMetadata, product_name: str, plan_name: str, target: str
    ) -> TechnicalConfigLookUpData:
        """Private method to lookup for the TechnicalConfig of a given target.

        Args:
            metadata (AzurePublishingMetadata): the incoming publishing metadata.
            product_name (str): the product (offer) name
            plan_name (str): the plan name
            target (str): the submission target to look up the TechnicalConfig object

        Returns:
            TechnicalConfigLookUpData: The data retrieved for the given submission target.
        """
        product, plan = self.get_product_plan_by_name(product_name, plan_name, target)
        log.info(
            "Retrieving the technical config for \"%s\" on \"%s\".",
            metadata.destination,
            target,
        )
        tech_config = self.get_plan_tech_config(product, plan)
        sas_found = False

        if is_sas_present(tech_config, metadata.image_path, metadata.check_base_sas_only):
            log.info(
                "The destination \"%s\" on \"%s\" already contains the SAS URI: \"%s\".",
                metadata.destination,
                target,
                metadata.image_path,
            )
            sas_found = True
        return {
            "metadata": metadata,
            "tech_config": tech_config,
            "sas_found": sas_found,
            "product": product,
            "plan": plan,
            "target": target,
        }

    def _create_or_update_disk_version(
        self,
        tech_config_lookup: TechnicalConfigLookUpData,
        source: VMImageSource,
        disk_version: Optional[DiskVersion],
    ) -> DiskVersion:
        """Private method to create/update the DiskVersion of a given TechnicalConfig object.

        Args:
            tech_config_lookup (TechnicalConfigLookUpData): the incoming data to process
            source (VMImageSource): the new VMI source to attach
            disk_version (Optional[DiskVersion]): the disk version if it exists (for updates).

        Returns:
            DiskVersion: The updated DiskVersion
        """
        metadata = tech_config_lookup["metadata"]
        target = tech_config_lookup["target"]
        tech_config = tech_config_lookup["tech_config"]

        # Check the images of the selected DiskVersion if it exists
        if disk_version:
            log.info(
                "DiskVersion \"%s\" exists in \"%s\" on \"%s\" for the image \"%s\".",
                disk_version.version_number,
                metadata.destination,
                target,
                metadata.image_path,
            )
            # Update the disk version with the new SAS
            disk_version = set_new_sas_disk_version(disk_version, metadata, source)
            return disk_version
        # The disk version doesn't exist, we need to create one from scratch
        log.info("The DiskVersion doesn't exist, creating one from scratch.")
        disk_version = create_disk_version_from_scratch(metadata, source)
        tech_config.disk_versions.append(disk_version)
        return disk_version

    def publish(self, metadata: AzurePublishingMetadata) -> None:
        """
        Associate a VM image with a given product listing (destination) and publish it if required.

        Args:
            metadata (AzurePublishingMetadata): metadata for the VHD image publishing.
        """
        # 1. Resolve the destination Product and Plan
        #
        # The given destination from StArMap has the following format:
        #   "product-name/plan-name"
        product_name = metadata.destination.split("/")[0]
        plan_name = metadata.destination.split("/")[-1]
        product_id = self.get_productid(product_name)
        sas_in_target = SasFoundStatus.missing
        log.info(
            "Preparing to associate the image \"%s\" with the plan \"%s\" from product \"%s\"",
            metadata.image_path,
            plan_name,
            product_name,
        )

        # 2. Prepare the Disk Version
        log.info("Creating the VMImageResource with SAS for image: \"%s\"", metadata.image_path)
        sas = OSDiskURI(uri=metadata.image_path)
        source = VMImageSource(source_type="sasUri", os_disk=sas.to_json(), data_disks=[])

        # 3. Set the new Disk Version into the product/plan if required
        #
        # Note: If `overwrite` is True it means we can set this VM image as the only one in the
        # plan's technical config and discard all other VM images which may've been present.
        if metadata.overwrite is True:
            target = "draft"  # It's expected to exist for whenever product.
            res = self._overwrite_disk_version(metadata, product_name, plan_name, source, target)
            tech_config = res["tech_config"]
        else:
            # Otherwise we need to check whether SAS isn't already present
            # in any of the targets "preview", "live" or "draft" and if not attach and publish it.
            for target in self.compute_targets(product_id):
                res = self._look_up_sas_on_technical_config(
                    metadata, product_name, plan_name, target
                )
                tech_config = res["tech_config"]
                # We don't want to seek for SAS anymore as it was already found
                if res["sas_found"]:
                    sas_in_target = SasFoundStatus[target]
                    break
            else:
                # At this point there's no SAS URI in any target so we can safely add it

                # Here we can have the metadata.disk_version set or empty.
                # When set we want to get the existing disk_version which matches its value.
                log.info(
                    "Scanning the disk versions from \"%s\" on \"%s\" for the image \"%s\"",
                    metadata.destination,
                    target,
                    metadata.image_path,
                )
                dv = seek_disk_version(tech_config, metadata.disk_version)
                self._create_or_update_disk_version(res, source, dv)

        # 4. With the updated disk_version we should adjust the SKUs and submit the changes
        if sas_in_target == SasFoundStatus.missing:
            log.info("Updating SKUs for \"%s\" on \"%s\".", metadata.destination, target)
            tech_config.skus = update_skus(
                disk_versions=tech_config.disk_versions,
                generation=metadata.generation,
                plan_name=plan_name,
                old_skus=tech_config.skus,
            )
            log.info(
                "Updating the technical configuration for \"%s\" on \"%s\".",
                metadata.destination,
                target,
            )
            self.configure(resources=[tech_config])

        # 5. Proceed to publishing if it was requested.
        # Note: The publishing will only occur if it made changes in disk_version.
        if not metadata.keepdraft:
            product = res["product"]
            # Get the submission state
            submission: ProductSubmission = cast(
                List[ProductSubmission],
                self.filter_product_resources(product=product, resource="submission"),
            )[0]

            # We should only publish if there are new changes OR
            # the existing offer was already in preview
            if sas_in_target <= SasFoundStatus.draft or self._is_submission_in_preview(submission):
                log.info(
                    "Publishing the new changes for \"%s\" on plan \"%s\"", product_name, plan_name
                )
                logdiff(self.diff_offer(product, target))
                self.ensure_can_publish(product.id)

                # According to the documentation we only need to pass the
                # required resources for modular publish on "preview"
                # https://learn.microsoft.com/en-us/partner-center/marketplace-offers/product-ingestion-api#method-2-publish-specific-draft-resources-also-known-as-modular-publish  # noqa: E501
                modular_resources = None
                if metadata.modular_push:
                    modular_resources = self.get_modular_resources_to_publish(product, tech_config)
                if sas_in_target < SasFoundStatus.preview:
                    self._publish_preview(product, product_name, resources=modular_resources)
                if sas_in_target < SasFoundStatus.live:
                    self._publish_live(product, product_name)

        log.info(
            "Finished publishing the image \"%s\" to \"%s\"",
            metadata.image_path,
            metadata.destination,
        )
