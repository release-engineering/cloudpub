# SPDX-License-Identifier: GPL-3.0-or-later
import logging
import os
from typing import Any, Dict, Iterator, List, Optional, Tuple, Union, cast

from tenacity import retry
from tenacity.retry import retry_if_result
from tenacity.stop import stop_after_delay
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
    VMImageDefinition,
    VMImageSource,
    VMIPlanTechConfig,
)
from cloudpub.ms_azure.session import PartnerPortalSession
from cloudpub.ms_azure.utils import (
    AzurePublishingMetadata,
    create_disk_version_from_scratch,
    get_image_type_mapping,
    is_azure_job_not_complete,
    is_sas_present,
    prepare_vm_images,
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
    AZURE_SCHEMA_VERSION = os.environ.get("AZURE_SCHEMA_VERSION", "2022-03-01-preview3")
    CONFIGURE_SCHEMA = "https://schema.mp.microsoft.com/schema/configure/{AZURE_API_VERSION}"

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
        self._raise_for_status(response=resp)
        parsed_resp = ConfigureStatus.from_json(resp.json())
        log.debug("Query Job details response: %s", parsed_resp)
        return parsed_resp

    @retry(
        retry=retry_if_result(predicate=is_azure_job_not_complete),
        wait=wait_chain(
            *[wait_fixed(wait=60)]  # First wait for 1 minute  # noqa: W503
            + [wait_fixed(wait=30 * 60)]  # Then wait for 30 minutes  # noqa: W503
            + [wait_fixed(wait=60 * 60)]  # And then wait for 1h  # noqa: W503
            + [wait_fixed(wait=60 * 60 * 12)]  # Finally wait each 12h  # noqa: W503
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

    def get_product(self, product_id: str) -> Product:
        """
        Return the requested Product by its ID.

        Args:
            product_durable_id (str)
                The product UUID
        Returns:
            Product: the requested product
        """
        log.debug("Requesting the product ID \"%s\".", product_id)
        resp = self.session.get(path=f"/resource-tree/product/{product_id}")
        data = self._assert_dict(resp)
        return Product.from_json(data)

    def get_product_by_name(self, product_name: str) -> Product:
        """
        Return the requested Product by its name from Legacy CPP API.

        Args:
            product_name (str)
                The product name according to Legacy CPP API.
        Returns:
            Product: the requested product when found
        Raises:
            NotFoundError when the product is not found.
        """
        for product in self.products:
            if product.identity.name == product_name:
                log.debug("Product alias \"%s\" has the ID \"%s\"", product_name, product.id)
                return self.get_product(product.id)
        self._raise_error(NotFoundError, f"No such product with name \"{product_name}\"")

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
        p = self.get_product(product_id=product_id)

        submission: ProductSubmission = cast(
            List[ProductSubmission], self.filter_product_resources(product=p, resource="submission")
        )[0]

        # status is expected to be 'preview' or 'live'
        submission.target.targetType = status

        return self.configure(resource=submission)

    def _get_plan_tech_config(self, product: Product, plan: PlanSummary) -> VMIPlanTechConfig:
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

    def _seek_disk_version(
        self, tech_config: VMIPlanTechConfig, version_number: Optional[str] = None
    ) -> Optional[DiskVersion]:
        """
        Return the requested DiskVersion when it exists.

        Args:
            tech_config
                The technical configuration to seek the disk versions.
            version_number
                The expected version number to retrieve. When absent the max value will be returned
                if there are existing disk versions.
        Returns:
            The expected disk version when found.
        """
        log.debug(
            "Seeking the DiskVersion with version number \"%s\" for plan \"%s\"",
            version_number,
            tech_config.plan_id,
        )

        for dv in tech_config.disk_versions:
            if version_number and dv.version_number == version_number:  # Metadata set
                log.debug("Found the DiskVersion \"%s\" for plan \"%s\"", dv, tech_config.plan_id)
                return dv

        log.debug("Disk Version %s was not found.", version_number)
        return None

    def _vm_images_by_generation(
        self, disk_version: DiskVersion, architecture: str
    ) -> Tuple[Optional[VMImageDefinition], ...]:
        """
        Return a tuple containing the Gen1 and Gen2 VHD images in this order.

        If one of the images doesn't exist it will return None in the expected tuple position.

        Args:
            disk_version
                The disk version to retrieve the VMImageDefinitions from
            architecture
                The expected architecture for the VMImageDefinition.
        Returns:
            Gen1 and Gen2 VMImageDefinitions when they exist.
        """
        log.debug("Sorting the VMImageDefinition by generation.")
        # Here we have 3 possibilities:
        # 1. vm_images => "Gen1" only
        # 2. vm_images => "Gen2" only
        # 3. vm_images => "Gen1" and "Gen2"

        # So let's get the first image whatever it is
        img = disk_version.vm_images.pop(0)

        # If first `img` is Gen2 we set the other one as `img_legacy`
        if img.image_type == get_image_type_mapping(architecture, "V2"):
            img_legacy = disk_version.vm_images.pop(0) if len(disk_version.vm_images) > 0 else None

        else:  # Otherwise we set it as `img_legacy` and get the gen2
            img_legacy = img
            img = (
                disk_version.vm_images.pop(0)  # type: ignore
                if len(disk_version.vm_images) > 0
                else None
            )
        log.debug("Image for current generation: %s", img)
        log.debug("Image for legacy generation: %s", img_legacy)
        return img, img_legacy

    def _create_vm_images(
        self, metadata: AzurePublishingMetadata, source: VMImageSource
    ) -> List[VMImageDefinition]:
        """
        Create a list of VMImageDefinition from scratch using the incoming source and metadata.

        Args:
            metadata
                The publishing metadata to create the VMImageDefinition objects.
            source
                The VMImageDefinition to use as source.
        Returns:
            A list with the new VMImageDefinitions.
        """
        log.debug("Creating VMImageDefinitions for \"%s\"", metadata.destination)
        vm_images = []

        vm_images.append(
            VMImageDefinition(
                image_type=get_image_type_mapping(metadata.architecture, metadata.generation),
                source=source.to_json(),
            )
        )
        if metadata.support_legacy:  # Only True when metadata.generation == V2
            vm_images.append(
                VMImageDefinition(
                    image_type=get_image_type_mapping(metadata.architecture, "V1"),
                    source=source.to_json(),
                )
            )
        log.debug("VMImageDefinitions created for \"%s\": %s", metadata.destination, vm_images)
        return vm_images

    def _set_new_sas_disk_version(
        self, disk_version: DiskVersion, metadata: AzurePublishingMetadata, source: VMImageSource
    ) -> DiskVersion:
        """
        Change the SAS URI of an existing Disk Version.

        Args:
            disk_version:
                The disk version to change the image with the new SAS URI.
            metadata:
                The publishing metadata to retrieve additional information
            source:
                The VMImageSource with the new SAS URI
        Returns:
            The changed disk version with the given source.
        """
        # If we already have a VMImageDefinition let's use it
        if disk_version.vm_images:
            log.debug("The DiskVersion \"%s\" contains inner images." % disk_version.version_number)
            img, img_legacy = self._vm_images_by_generation(disk_version, metadata.architecture)

            # Now we replace the SAS URI for the vm_images
            log.debug(
                "Adjusting the VMImages from existing DiskVersion \"%s\""
                "to fit the new image with SAS \"%s\"."
                % (disk_version.version_number, metadata.image_path)
            )
            disk_version.vm_images = prepare_vm_images(
                metadata=metadata,
                gen1=img_legacy,
                gen2=img,
                source=source,
            )

        # If no VMImages, we need to create them from scratch
        else:
            log.debug(
                "The DiskVersion \"%s\" does not contain inner images."
                % disk_version.version_number
            )
            log.debug(
                "Setting the new image \"%s\" on DiskVersion \"%s\"."
                % (metadata.image_path, disk_version.version_number)
            )
            disk_version.vm_images = self._create_vm_images(metadata, source)

        return disk_version

    def _publish_live(self, product: Product, product_name: str) -> None:
        """
        Submit the product to 'live' after going through Azure Marketplace Validation.

        This method will first send the product to `preview` if it's not already in this state to
        execute the validation pipeline (on Azure side) and then submit it to `live`.

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
        if submission.target.targetType != 'preview':
            log.info(
                "Submitting the product \"%s (%s)\" to \"preview\"." % (product_name, product.id)
            )
            self.submit_to_status(product_id=product.id, status='preview')

        # Note: the offer can only go `live` after successfully being changed to `preview`
        # which takes up to 4 days.
        log.info("Submitting the product \"%s (%s)\" to \"live\"." % (product_name, product.id))
        self.submit_to_status(product_id=product.id, status='live')

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
        product = self.get_product_by_name(product_name=product_name)
        plan = self.get_plan_by_name(product=product, plan_name=plan_name)
        log.info(
            "Preparing to associate the image with the plan \"%s\" from product \"%s\""
            % (product_name, plan_name)
        )

        # 2. Retrieve the VM Technical configuration for the given plan
        log.debug("Retrieving the technical config for \"%s\"." % metadata.destination)
        tech_config = self._get_plan_tech_config(product, plan)

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
            disk_version = self._seek_disk_version(tech_config, metadata.disk_version)

            # Check the images of the selected DiskVersion if it exists
            if disk_version:
                log.debug(
                    "DiskVersion \"%s\" exists in \"%s\"."
                    % (disk_version.version_number, metadata.destination)
                )
                disk_version = self._set_new_sas_disk_version(disk_version, metadata, source)

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
            )
            # Filter out disk versions marked as deprecated since Microsoft get unhappy when
            # sending them back on configure request.
            log.debug("Filtering out possible deprecated disk versions")
            tech_config.disk_versions = [
                dv for dv in tech_config.disk_versions if dv.lifecycle_state != "deprecated"
            ]
            log.debug("Updating the technical configuration for \"%s\"." % metadata.destination)
            self.configure(resource=tech_config)

        # 5. Proceed to publishing if it was requested.
        if not metadata.keepdraft:
            self._publish_live(product, product_name)
