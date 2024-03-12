# SPDX-License-Identifier: GPL-3.0-or-later
import logging
from operator import attrgetter
from typing import Dict, List, Optional

from cloudpub.common import PublishingMetadata  # Cannot circular import AzurePublishingMetadata
from cloudpub.models.ms_azure import (
    ConfigureStatus,
    DiskVersion,
    VMImageDefinition,
    VMImageSource,
    VMIPlanTechConfig,
    VMISku,
)
from cloudpub.utils import get_url_params

log = logging.getLogger(__name__)


class AzurePublishingMetadata(PublishingMetadata):
    """A collection of metadata necessary for publishing a VHD Image into a product."""

    # Note: This class must be defined here as it would cause circular import with `service.py` on
    # typing annotation for functions in this module.

    def __init__(
        self,
        disk_version: str,
        sku_id: Optional[str] = None,
        generation: str = "V2",
        support_legacy: bool = False,
        recommended_sizes: Optional[List[str]] = None,
        **kwargs,
    ) -> None:
        """
        Create a new AzurePublishingMetadata object.

        Args:
            disk_version (str)
                The disk version in the format ``{int}.{int}.{int}``
            sku_id (str, optional):
                The SKU ID to associate this image with. Defaults to the plan name.
            generation (str, optional):
                The VM image generation. Defaults to ``V2``
            support_legacy(bool, optional):
                If the ``V2`` VM image also supports ``V1`` (legacy generation)
            recommended_sizes (list, optional)
                The recommended sizes for the virtual machine.
            legacy_sku_id (str, optional):
                Only required when ``support_legacy == True``. The SKU ID for Gen1.
                Defaults to ``{sku_id}-gen1``
            **kwargs
                Arguments for :class:`~cloudpub.common.PublishingMetadata`.
        """
        self.disk_version = disk_version
        self.sku_id = sku_id or kwargs.get("destination", "").split("/")[-1]
        self.generation = generation
        self.support_legacy = support_legacy
        self.recommended_sizes = recommended_sizes or []
        self.legacy_sku_id = kwargs.pop("legacy_sku_id", None)

        if generation == "V1" or not support_legacy:
            self.legacy_sku_id = None
        else:
            if not self.legacy_sku_id and sku_id:
                self.legacy_sku_id = f"{sku_id}-gen1"
        super(AzurePublishingMetadata, self).__init__(**kwargs)
        self.__validate()
        # Adjust the x86_64 architecture string for Azure
        self.architecture = "x64" if self.architecture == "x86_64" else self.architecture

    def __validate(self):
        mandatory = [
            "disk_version",
            "generation",
        ]
        for param in mandatory:
            if not getattr(self, param, None):
                raise ValueError(f"The parameter \"{param}\" must not be None.")

        if self.generation != "V1" and self.generation != "V2":
            raise ValueError(
                f"Invalid generation \"{self.generation}\". Expected: \"V1\" or \"V2\"."
            )
        if not self.image_path.startswith("https://"):
            raise ValueError(f"Invalid SAS URI \"{self.image_path}\". Expected: http/https URL.")


def get_image_type_mapping(architecture: str, generation: str) -> str:
    """Return the image type required by VMImageDefinition."""
    gen_map = {
        "V1": f"{architecture}Gen1",
        "V2": f"{architecture}Gen2",
    }
    return gen_map.get(generation, "")


def is_sas_eq(sas1: str, sas2: str) -> bool:
    """
    Compare 2 SAS URI and determine where they're equivalent.

    Equivalent SAS URIs have the same URL with the parameters differing only for:

    - st: start date for SAS URI
    - se: expiration date for SAS URI
    - sv: signed version for SAS URI
    - sig: Unique signature of the SAS URI

    This comparison is necessary as each time a SAS URI is generated it returns a different value.

    Args:
        sas1:
            The left SAS to compare the equivalency
        sas2:
            The right SAS to compare the equivalency

    Returns:
        True when both SAS URIs are equivalent, False otherwise.
    """
    base_sas1 = sas1.split("?")[0]
    base_sas2 = sas2.split("?")[0]
    unique_keys = ['st', 'se', 'sv', 'sig']

    params_sas1 = {k: v for k, v in get_url_params(sas1).items() if k not in unique_keys}
    params_sas2 = {k: v for k, v in get_url_params(sas2).items() if k not in unique_keys}

    # Base URL differs
    if base_sas1 != base_sas2:
        log.debug("Got different base SAS: %s - Expected: %s" % (base_sas1, base_sas2))
        return False

    # Parameters lengh differs
    if len(params_sas1) != len(params_sas2):
        log.debug(
            "Got different lengh of SAS parameters: len(%s) - Expected len(%s)"
            % (params_sas1, params_sas2)
        )
        return False

    # Parameters values differs
    for k, v in params_sas1.items():
        if v != params_sas2.get(k, None):
            log.debug("The SAS parameter %s doesn't match %s." % (v, params_sas2.get(k, None)))
            return False

    # Equivalent SAS
    return True


def is_sas_present(tech_config: VMIPlanTechConfig, sas_uri: str) -> bool:
    """
    Check whether the given SAS URI is already present in the disk_version.

    Args:
        tech_config (VMIPlanTechConfig)
            The plan's technical configuraion to seek the SAS_URI.
        sas_uri (str)
            The SAS URI to check whether it's present or not in disk version.
    Returns:
        bool: True when the SAS is present in the plan, False otherwise.
    """
    for disk_version in tech_config.disk_versions:
        for img in disk_version.vm_images:
            if is_sas_eq(img.source.os_disk.uri, sas_uri):
                return True
    return False


def is_azure_job_not_complete(job_details: ConfigureStatus) -> bool:
    """
    Check if the job status from a `configure` request is not completed.

    Args:
        job_details (dict)
            The job details status.
    Returns:
        bool: False if job completed, True otherwise
    """
    log.debug(f"Checking if the job \"{job_details.job_id}\" is still running")
    log.debug(f"job {job_details.job_id} is in {job_details.job_status} state")
    if job_details.job_status != "completed":
        return True
    return False


def prepare_vm_images(
    metadata: AzurePublishingMetadata,
    gen1: Optional[VMImageDefinition],
    gen2: Optional[VMImageDefinition],
    source: VMImageSource,
) -> List[VMImageDefinition]:
    """
    Update the vm_images list with the proper SAS based in existing generation(s).

    Args:
        metadata (AzurePublishingMetadata)
            The VHD publishing metadata.
        gen1 (VMImageDefinition, optional)
            The VMImageDefinition for Gen1 VHD.
            If not set the argument `gen2` must be set.
        gen2 (VMImageDefinition, optional)
            The VMImageDefinition for Gen2 VHD.
            If not set the argument `gen1` must be set.
        source (VMImageSource):
            The VMImageSource with the updated SAS URI.
    Returns:
        list: A new list containing the expected VMImageDefinition(s)
    """
    if not gen1 and not gen2:
        msg = "At least one argument of \"gen1\" or \"gen2\" must be set."
        log.error(msg)
        raise ValueError(msg)

    raw_source = source.to_json()
    json_gen1 = {
        "imageType": get_image_type_mapping(metadata.architecture, "V1"),
        "source": raw_source,
    }
    json_gen2 = {
        "imageType": get_image_type_mapping(metadata.architecture, "V2"),
        "source": raw_source,
    }

    if metadata.generation == "V2":
        # In this case we need to set a V2 SAS URI
        gen2_new = VMImageDefinition.from_json(json_gen2)
        if metadata.support_legacy:  # and in this case a V1 as well
            gen1_new = VMImageDefinition.from_json(json_gen1)
            return [gen2_new, gen1_new]
        return [gen2_new]
    else:
        # It's expected to be a Gen1 only, let's get rid of Gen2
        return [VMImageDefinition.from_json(json_gen1)]


def update_skus(
    disk_versions: List[DiskVersion],
    generation: str,
    plan_name: str,
    old_skus: Optional[List[VMISku]] = None,
) -> List[VMISku]:
    """
    Return the expected VMISku list based on given DiskVersion.

    Args:
        disk_versions (list)
            List of existing DiskVersion in the technical config
        generation (str)
            The main generation for publishing
        plan-name (str)
            The destination plan name.
        old_skus (list, optional)
            A list of the existing SKUs to extract the security_type value
            when set.
    Returns:
        The updated list with VMISkus.
    """
    sku_mapping: Dict[str, str] = {}
    # All SKUs must have the same security_type thus picking the first one is OK
    security_type = old_skus[0].security_type if old_skus else None

    # Update the SKUs for each image in DiskVersions
    for disk_version in disk_versions:
        # Each disk version may have multiple images (Gen1 / Gen2)
        for vmid in disk_version.vm_images:
            # We'll name the main generation SKU as "{plan_name}" and
            # the alternate generation SKU as "{plan-name}-genX"
            alt_gen = 2 if generation == "V1" else 1
            arch = vmid.image_type.split("Gen")[0]
            new_img_type = get_image_type_mapping(arch, generation)
            new_img_alt_type = get_image_type_mapping(arch, f"V{alt_gen}")

            # we just want to add SKU whenever it's not set
            if vmid.image_type == new_img_type:
                sku_mapping.setdefault(new_img_type, plan_name)
            elif vmid.image_type == new_img_alt_type:
                sku_mapping.setdefault(new_img_alt_type, f"{plan_name}-gen{alt_gen}")

    # Return the expected SKUs list
    res = [
        VMISku.from_json({"image_type": k, "id": v, "security_type": security_type})
        for k, v in sku_mapping.items()
    ]
    return sorted(res, key=attrgetter("id"))


def create_disk_version_from_scratch(
    metadata: AzurePublishingMetadata, source=VMImageSource
) -> DiskVersion:
    """
    Create a new DiskVersion with the required data for publishing.

    Args:
        metadata (AzurePublishingMetadata)
            The VHD publishing metadata.
        source (VMImageSource):
            The VMImageSource with the updated SAS URI.
    """
    vm_images = [
        {
            "imageType": get_image_type_mapping(metadata.architecture, metadata.generation),
            "source": source.to_json(),
        }
    ]
    if metadata.support_legacy:
        vm_images.append(
            {
                "imageType": get_image_type_mapping(metadata.architecture, "V1"),
                "source": source.to_json(),
            }
        )
    json = {
        "versionNumber": metadata.disk_version,
        "vmImages": vm_images,
        "lifecycleState": "generallyAvailable",
    }
    return DiskVersion.from_json(json)
