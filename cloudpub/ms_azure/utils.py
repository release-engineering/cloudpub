# SPDX-License-Identifier: GPL-3.0-or-later
import logging
from operator import attrgetter
from typing import Any, Dict, List, Optional, Tuple

from deepdiff import DeepDiff

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
            check_base_sas_only (bool, optional):
                Indicates to skip checking SAS parameters when set as ``True``.
                Default to ``False``
            **kwargs
                Arguments for :class:`~cloudpub.common.PublishingMetadata`.
        """
        self.disk_version = disk_version
        self.sku_id = sku_id or kwargs.get("destination", "").split("/")[-1]
        self.generation = generation
        self.support_legacy = support_legacy
        self.recommended_sizes = recommended_sizes or []
        self.legacy_sku_id = kwargs.pop("legacy_sku_id", None)
        self.check_base_sas_only = kwargs.pop("check_base_sas_only", False)

        if generation == "V1" or not support_legacy:
            self.legacy_sku_id = None
        else:
            if not self.legacy_sku_id and sku_id:
                self.legacy_sku_id = f"{sku_id}-gen1"
        super(AzurePublishingMetadata, self).__init__(**kwargs)
        self.__validate()
        # Adjust the x86_64 architecture string for Azure
        arch = self.__convert_arch(self.architecture)
        self.architecture = arch

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "architecture":
            arch = self.__convert_arch(value)
            value = arch
        return super().__setattr__(name, value)

    @staticmethod
    def __convert_arch(arch: str) -> str:
        converter = {
            "x86_64": "x64",
            "aarch64": "arm64",
        }
        return converter.get(arch, "") or arch

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
        "V2": f"{architecture}Gen2",
    }
    if architecture == "x64":
        gen_map.update({"V1": f"{architecture}Gen1"})
    return gen_map.get(generation, "")


def is_sas_eq(sas1: str, sas2: str, base_only=False) -> bool:
    """
    Compare 2 SAS URI and determine where they're equivalent.

    Equivalent SAS URIs have the same URL with the parameters differing only for:

    - st: start date for SAS URI
    - se: expiration date for SAS URI
    - sv: signed version for SAS URI
    - sig: Unique signature of the SAS URI

    This comparison is necessary as each time a SAS URI is generated it returns a different value.

    Args:
        sas1 (str):
            The left SAS to compare the equivalency
        sas2 (str):
            The right SAS to compare the equivalency
        base_only (bool):
            When True it will only compare the base SAS and not its arguments. Defaults to False.

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

    if not base_only:
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


def is_sas_present(tech_config: VMIPlanTechConfig, sas_uri: str, base_only: bool = False) -> bool:
    """
    Check whether the given SAS URI is already present in the disk_version.

    Args:
        tech_config (VMIPlanTechConfig)
            The plan's technical configuraion to seek the SAS_URI.
        sas_uri (str)
            The SAS URI to check whether it's present or not in disk version.
        base_only (bool):
            When True it will only compare the base SAS and not its arguments. Defaults to False.
    Returns:
        bool: True when the SAS is present in the plan, False otherwise.
    """
    for disk_version in tech_config.disk_versions:
        for img in disk_version.vm_images:
            if is_sas_eq(img.source.os_disk.uri, sas_uri, base_only):
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


def is_legacy_gen_supported(metadata: AzurePublishingMetadata) -> bool:
    """Return True when the legagy V1 SKU is supported, False otherwise.

    Args:
        metadata: The incoming publishing metadata.
    Returns:
        bool: True when V1 is supported, False otherwise.
    """
    return metadata.architecture == "x64" and metadata.support_legacy


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
        if is_legacy_gen_supported(metadata):  # and in this case a V1 as well
            gen1_new = VMImageDefinition.from_json(json_gen1)
            return [gen2_new, gen1_new]
        return [gen2_new]
    else:
        # It's expected to be a Gen1 only, let's get rid of Gen2
        return [VMImageDefinition.from_json(json_gen1)]


def _all_skus_present(old_skus: List[VMISku], disk_versions: List[DiskVersion]) -> bool:
    image_types = set()
    for sku in old_skus:
        image_types.add(sku.image_type)

    for dv in disk_versions:
        for img in dv.vm_images:
            if img.image_type not in image_types:
                return False
    return True


def _build_skus(
    disk_versions: List[DiskVersion],
    default_gen: str,
    alt_gen: str,
    plan_name: str,
    security_type: Optional[List[str]] = None,
) -> List[VMISku]:
    def get_skuid(arch):
        if arch == "x64":
            return plan_name
        return f"{plan_name}-{arch.lower()}"

    def get_safe_security_type(image_type):
        # Arches which aren't x86Gen2 (like ARM64) doesn't work well with security type
        if image_type != "x64Gen2":
            return None
        return security_type

    sku_mapping: Dict[str, str] = {}
    # Update the SKUs for each image in DiskVersions if needed
    for disk_version in disk_versions:
        # Each disk version may have multiple images (Gen1 / Gen2)
        for vmid in disk_version.vm_images:
            # We'll name the main generation SKU as "{plan_name}" and
            # the alternate generation SKU as "{plan-name}-genX"
            arch = vmid.image_type.split("Gen")[0]
            new_img_type = get_image_type_mapping(arch, default_gen)
            new_img_alt_type = get_image_type_mapping(arch, alt_gen)

            # we just want to add SKU whenever it's not set
            skuid = get_skuid(arch)
            if vmid.image_type == new_img_type:
                sku_mapping.setdefault(new_img_type, skuid)
            elif vmid.image_type == new_img_alt_type:
                sku_mapping.setdefault(new_img_alt_type, f"{skuid}-gen{alt_gen[1:]}")

    # Return the expected SKUs list
    res = [
        VMISku.from_json({"image_type": k, "id": v, "security_type": get_safe_security_type(k)})
        for k, v in sku_mapping.items()
    ]
    return sorted(res, key=attrgetter("id"))


def _get_security_type(old_skus: List[VMISku]) -> Optional[List[str]]:
    # The security type may exist only for x64 Gen2, so it iterates over all gens to find it
    # Get the security type for all gens
    for osku in old_skus:
        if osku.security_type is not None:
            return osku.security_type
    return None


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
            The main generation for publishing when there are no old_skus
        plan-name (str)
            The destination plan name.
        old_skus (list, optional)
            A list of the existing SKUs to extract the security_type value
            when set.
    Returns:
        The updated list with VMISkus.
    """
    if not old_skus:
        alt_gen = "V2" if generation == "V1" else "V1"
        return _build_skus(
            disk_versions, default_gen=generation, alt_gen=alt_gen, plan_name=plan_name
        )

    # If we have SKUs for each image we don't need to update them as they're already
    # properly set.
    if _all_skus_present(old_skus, disk_versions):
        return old_skus

    # Update SKUs to create the alternate gen.
    security_type = _get_security_type(old_skus)

    # The alternate plan for x64 name ends with the suffix "-genX" and we can't change that once
    # the offer is live, otherwise it will raise "BadRequest" with the message:
    # "The property 'PlanId' is locked by a previous submission".
    osku = old_skus[0]

    # Default Gen2 cases
    if osku.image_type.endswith("Gen1") and osku.id.endswith("gen1"):
        default_gen = "V2"
        alt_gen = "V1"
    elif osku.image_type.endswith("Gen2") and not osku.id.endswith("gen2"):
        default_gen = "V2"
        alt_gen = "V1"

    # Default Gen1 cases
    elif osku.image_type.endswith("Gen1") and not osku.id.endswith("gen1"):
        default_gen = "V1"
        alt_gen = "V2"
    elif osku.image_type.endswith("Gen2") and osku.id.endswith("gen2"):
        default_gen = "V1"
        alt_gen = "V2"

    return _build_skus(
        disk_versions,
        default_gen=default_gen,
        alt_gen=alt_gen,
        plan_name=plan_name,
        security_type=security_type,
    )


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
    if is_legacy_gen_supported(metadata):
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


def seek_disk_version(
    tech_config: VMIPlanTechConfig, version_number: Optional[str] = None
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


def vm_images_by_generation(
    disk_version: DiskVersion, architecture: str
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


def create_vm_image_definitions(
    metadata: AzurePublishingMetadata, source: VMImageSource
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
    if is_legacy_gen_supported(metadata):
        vm_images.append(
            VMImageDefinition(
                image_type=get_image_type_mapping(metadata.architecture, "V1"),
                source=source.to_json(),
            )
        )
    log.debug("VMImageDefinitions created for \"%s\": %s", metadata.destination, vm_images)
    return vm_images


def set_new_sas_disk_version(
    disk_version: DiskVersion, metadata: AzurePublishingMetadata, source: VMImageSource
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
        img, img_legacy = vm_images_by_generation(disk_version, metadata.architecture)

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
            "The DiskVersion \"%s\" does not contain inner images." % disk_version.version_number
        )
        log.debug(
            "Setting the new image \"%s\" on DiskVersion \"%s\"."
            % (metadata.image_path, disk_version.version_number)
        )
        disk_version.vm_images = create_vm_image_definitions(metadata, source)

    return disk_version


def logdiff(diff: DeepDiff) -> None:
    """Log the offer diff if it exists."""
    if diff:
        log.warning(f"Found the following offer diff before publishing:\n{diff.pretty()}")
