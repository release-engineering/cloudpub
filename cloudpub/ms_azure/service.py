# SPDX-License-Identifier: GPL-3.0-or-later
import logging
import os
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
        log.debug("Received the following data to create/modify: %s" % data)
        resp = self.session.post(path="configure", json=data)
        self._raise_for_status(response=resp)
        parsed_resp = ConfigureStatus.from_json(resp.json())
        log.debug("Create/modify request response: %s", parsed_resp)
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
        log.debug(f"Query job details for \"{job_id}\"")
        resp = self.session.get(path=f"configure/{job_id}/status")

        # We don't want to fail if there's a server error thus we make a fake
        # response for it so the query job details will be retried.
        if resp.status_code >= 500:
            log.warning(
                (
                    f"Got HTTP {resp.status_code} from server when querying job {job_id} status."
                    " Considering the job_status as \"pending\"."
                )
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
            log.debug(f"Job {job_id} succeeded")
        return job_details

    def configure(self, resource: AzureResource) -> ConfigureStatus:
        """
        Create or update a resource and wait until it's done.

        Args:
            resource (AzureResource):
                The resource to create/modify in Azure.
        Returns:
            dict: The result of job execution
        """
        data = {
            "$schema": self.CONFIGURE_SCHEMA.format(AZURE_API_VERSION=self.AZURE_API_VERSION),
            "resources": [resource.to_json()],
        }
        log.debug("Data to configure: %s", data)
        res = self._configure(data=data)
        return self._wait_for_job_completion(job_id=res.job_id)

    @property
    def products(self) -> Iterator[ProductSummary]:
        """Iterate over all products from Azure Marketplace."""
        has_next = True
        params: Dict[str, str] = {}

        while has_next:
            log.debug("Requesting the products list.")
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
        if not self._products:
            self._products = [p for p in self.products]
        return self._products

    def get_product(self, product_id: str, first_target: str = "preview") -> Product:
        """
        Return the requested Product by its ID.

        It will return the product with the latest publishing status, trying to
        fetch it in the following order: "preview" -> "draft" -> "live". The first
        status to fech must be "preview" in order to indepotently detect an existing
        publishing which could be missing to go live.

        Args:
            product_durable_id (str)
                The product UUID
            first_target (str, optional)
                The first target to lookup into. Defaults to ``preview``.
        Returns:
            Product: the requested product
        """
        targets = [first_target]
        for tgt in ["preview", "draft", "live"]:
            if tgt not in targets:
                targets.append(tgt)

        for t in targets:
            log.debug("Requesting the product ID \"%s\" with state \"%s\".", product_id, t)
            try:
                resp = self.session.get(
                    path=f"/resource-tree/product/{product_id}", params={"targetType": t}
                )
                data = self._assert_dict(resp)
                return Product.from_json(data)
            except (ValueError, HTTPError):
                log.debug("Couldn't find the product \"%s\" with state \"%s\"", product_id, t)
        self._raise_error(NotFoundError, f"No such product with id \"{product_id}\"")

    def get_product_by_name(self, product_name: str, first_target: str = "preview") -> Product:
        """
        Return the requested Product by its name from Legacy CPP API.

        Args:
            product_name (str)
                The product name according to Legacy CPP API.
            first_target (str, optional)
                The first target to lookup into. Defaults to ``preview``.
        Returns:
            Product: the requested product when found
        Raises:
            NotFoundError when the product is not found.
        """
        for product in self.products:
            if product.identity.name == product_name:
                log.debug("Product alias \"%s\" has the ID \"%s\"", product_name, product.id)
                return self.get_product(product.id, first_target=first_target)
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
        self, product_name: str, plan_name: str
    ) -> Tuple[Product, PlanSummary]:
        """Return a tuple with the desired Product and Plan after iterating over all targets.

        Args:
            product_name (str): The name of the product to search for
            plan_name (str): The name of the plan to search for

        Returns:
            Tuple[Product, PlanSummary]: The Product and PlanSummary when fonud
        Raises:
            NotFoundError whenever all targets are exhausted and no information was found
        """
        targets = ["preview", "draft", "live"]

        for tgt in targets:
            try:
                product = self.get_product_by_name(product_name, first_target=tgt)
                plan = self.get_plan_by_name(product, plan_name)
                return product, plan
            except NotFoundError:
                continue
        self._raise_error(
            NotFoundError, f"No such plan with name \"{plan_name} for {product_name}\""
        )

    def diff_offer(self, product: Product, first_target="preview") -> DeepDiff:
        """Compute the difference between the provided product and the one in the remote.

        Args:
            product (Product)
                The local product to diff with the remote one.
            first_target (str)
                The first target to lookup into. Defaults to ``preview``.
        Returns:
            DeepDiff: The diff data.
        """
        remote = self.get_product(product.id, first_target=first_target)
        return DeepDiff(remote.to_json(), product.to_json(), exclude_regex_paths=self.DIFF_EXCLUDES)

    def submit_to_status(self, product_id: str, status: str) -> ConfigureStatus:
        """
        Send a submission request to Microsoft with a new Product status.

        Args:
            product_id (str)
                The product ID to submit the new status.
            status (str)
                The new status: 'preview' or 'live'
        Returns:
            The response from configure request.
        """
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
        log.debug("Set the status \"%s\" to submission.", status)

        return self.configure(resource=submission)

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
    def _publish_preview(self, product: Product, product_name: str) -> None:
        """
        Submit the product to 'preview'  if it's not already in this state.

        This is required to execute the validation pipeline on Azure side.

        Args:
            product
                The product with changes to publish live
            product_name
                The product name to display in logs.
        """
        # We just want to set the ProductSubmission to 'preview' if it's not in this status.
        #
        # The `preview` stage runs the Azure pipeline which takes up to 4 days.
        # Meanwhile the `submit_for_status` will be blocked querying the `job_status`until
        # all the Azure verification pipeline finishes.
        submission: ProductSubmission = cast(
            List[ProductSubmission],
            self.filter_product_resources(product=product, resource="submission"),
        )[0]
        if not self._is_submission_in_preview(submission):
            log.info(
                "Submitting the product \"%s (%s)\" to \"preview\"." % (product_name, product.id)
            )
            res = self.submit_to_status(product_id=product.id, status='preview')

            if res.job_result != 'succeeded' or not self.get_submission_state(
                product.id, state="preview"
            ):
                errors = "\n".join(res.errors)
                failure_msg = (
                    f"Failed to submit the product {product.id} to preview. "
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
        log.info("Submitting the product \"%s (%s)\" to \"live\"." % (product_name, product.id))
        res = self.submit_to_status(product_id=product.id, status='live')

        if res.job_result != 'succeeded' or not self.get_submission_state(product.id, state="live"):
            errors = "\n".join(res.errors)
            failure_msg = (
                f"Failed to submit the product {product.id} to live. "
                f"Status: {res.job_result} Errors: {errors}"
            )
            raise RuntimeError(failure_msg)

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
        product, plan = self.get_product_plan_by_name(product_name, plan_name)
        log.info(
            "Preparing to associate the image with the plan \"%s\" from product \"%s\""
            % (product_name, plan_name)
        )

        # 2. Retrieve the VM Technical configuration for the given plan
        log.debug("Retrieving the technical config for \"%s\"." % metadata.destination)
        tech_config = self.get_plan_tech_config(product, plan)

        # 3. Prepare the Disk Version
        log.debug("Creating the VMImageResource with SAS: \"%s\"" % metadata.image_path)
        sas = OSDiskURI(uri=metadata.image_path)
        source = VMImageSource(source_type="sasUri", os_disk=sas.to_json(), data_disks=[])

        # Note: If `overwrite` is True it means we can set this VM image as the only one in the
        # plan's technical config and discard all other VM images which may've been present.
        disk_version = None  # just to make mypy happy
        if metadata.overwrite is True:
            log.warning("Overwriting the plan %s with the given image.", plan_name)
            disk_version = create_disk_version_from_scratch(metadata, source)
            tech_config.disk_versions = [disk_version]

        # We just want to append a new image if the SAS is not already present.
        elif not is_sas_present(tech_config, metadata.image_path):
            # Here we can have the metadata.disk_version set or empty.
            # When set we want to get the existing disk_version which matches its value.
            log.debug("Scanning the disk versions from %s" % metadata.destination)
            disk_version = seek_disk_version(tech_config, metadata.disk_version)

            # Check the images of the selected DiskVersion if it exists
            if disk_version:
                log.debug(
                    "DiskVersion \"%s\" exists in \"%s\"."
                    % (disk_version.version_number, metadata.destination)
                )
                disk_version = set_new_sas_disk_version(disk_version, metadata, source)

            else:  # The disk version doesn't exist, we need to create one from scratch
                log.debug("The DiskVersion doesn't exist, creating one from scratch.")
                disk_version = create_disk_version_from_scratch(metadata, source)
                tech_config.disk_versions.append(disk_version)
        else:
            log.debug(
                "The destination \"%s\" already contains the SAS URI: \"%s\""
                % (metadata.destination, metadata.image_path)
            )

        # 4. With the updated disk_version we should adjust the SKUs and submit the changes
        if disk_version:
            log.debug("Updating SKUs for \"%s\"." % metadata.destination)
            tech_config.skus = update_skus(
                disk_versions=tech_config.disk_versions,
                generation=metadata.generation,
                plan_name=plan_name,
                old_skus=tech_config.skus,
            )
            log.debug("Updating the technical configuration for \"%s\"." % metadata.destination)
            self.configure(resource=tech_config)

        # 5. Proceed to publishing if it was requested.
        if not metadata.keepdraft:
            logdiff(self.diff_offer(product))
            self.ensure_can_publish(product.id)

            self._publish_preview(product, product_name)
            self._publish_live(product, product_name)
