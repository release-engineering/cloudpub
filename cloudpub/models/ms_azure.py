# SPDX-License-Identifier: GPL-3.0-or-later
import logging
from typing import Any, Dict, List, Optional

from attrs import Attribute, define, field
from attrs.setters import NO_OP
from attrs.validators import deep_iterable, instance_of

from cloudpub.models.common import AttrsJSONDecodeMixin

log = logging.getLogger(__name__)


@define
class AzureResource(AttrsJSONDecodeMixin):
    """The base class for all Azure Resources."""

    schema: str = field(validator=instance_of(str), metadata={"alias": "$schema"})
    """
    The `resource schema`_ for Graph API.

    .. _resource schema: https://learn.microsoft.com/en-us/azure/marketplace/product-ingestion-api#resource-api-reference
    """  # noqa E501

    durable_id: str = field(validator=instance_of(str), metadata={"alias": "id"})
    """
    The resource `durable ID`_.

    .. _durable ID: https://learn.microsoft.com/en-us/azure/marketplace/product-ingestion-api#method-2-durable-id
    """  # noqa E501

    @property
    def id(self):
        """
        Resolve the resource ID from its `durable ID`_.

        .. _durable ID: https://learn.microsoft.com/en-us/azure/marketplace/product-ingestion-api#method-2-durable-id
        """  # noqa E501
        # durable ID format example:
        #   product/62c171e9-a2e1-45ab-9af0-d17e769da954
        # what do we want:
        #   62c171e9-a2e1-45ab-9af0-d17e769da954
        return self.durable_id.split("/")[-1]

    @property
    def resource(self):
        """
        Resource name from its `durable ID`_.

        .. _durable ID: https://learn.microsoft.com/en-us/azure/marketplace/product-ingestion-api#method-2-durable-id
        """  # noqa E501
        return self.durable_id.split("/")[0]


@define
class AzureProductLinkedResource(AzureResource):
    """Represent a Resource linked to a product."""

    product_durable_id: str = field(validator=instance_of(str), metadata={"alias": "product"})
    """
    The product `durable ID`_.

    .. _durable ID: https://learn.microsoft.com/en-us/azure/marketplace/product-ingestion-api#method-2-durable-id
    """  # noqa E501

    @property
    def product_id(self):
        """
        Resolve the product ID from its `durable ID`_.

        .. _durable ID: https://learn.microsoft.com/en-us/azure/marketplace/product-ingestion-api#method-2-durable-id
        """  # noqa E501
        # durable ID format example:
        #   product/62c171e9-a2e1-45ab-9af0-d17e769da954
        # what do we want:
        #   62c171e9-a2e1-45ab-9af0-d17e769da954
        return self.product_durable_id.split("/")[-1]


@define
class AzurePlanLinkedResource(AzureProductLinkedResource):
    """Represent a resource linked to a plan."""

    plan_durable_id: str = field(validator=instance_of(str), metadata={"alias": "plan"})
    """
    The plan `durable ID`_.

    .. _durable ID: https://learn.microsoft.com/en-us/azure/marketplace/product-ingestion-api#method-2-durable-id
    """  # noqa E501

    @property
    def plan_id(self):
        """
        Resolve the plan ID from its `durable ID`_.

        .. _durable ID: https://learn.microsoft.com/en-us/azure/marketplace/product-ingestion-api#method-2-durable-id
        """  # noqa E501
        # durable ID format example:
        #   plan/62c171e9-a2e1-45ab-9af0-d17e769da954
        # what do we want:
        #   62c171e9-a2e1-45ab-9af0-d17e769da954
        return self.plan_durable_id.split("/")[-1]


@define
class Identity(AttrsJSONDecodeMixin):
    """Represent the resource identity (name)."""

    name: str = field(metadata={"alias": "externalId"})
    """
    The resource ID from the `legacy CPP API`_.

    .. _legacy CPP API: https://learn.microsoft.com/en-us/azure/marketplace/cloud-partner-portal-api-overview
    """  # noqa E501


@define
class ProductSummary(AzureResource):
    """
    Represent a product summary.

    `Schema definition for ProductSummary <https://product-ingestion.azureedge.net/schema/product/2022-03-01-preview2>`_
    """  # noqa E501

    identity: Identity = field(converter=Identity.from_json, on_setattr=NO_OP)  # type: ignore
    """
    The :class:`~cloudpub.models.ms_azure.Identity` representing the `offerId`
    from the `legacy CPP API`_.

    .. _legacy CPP API: https://learn.microsoft.com/en-us/azure/marketplace/cloud-partner-portal-api-overview
    """  # noqa E501

    type: str = field(validator=instance_of(str))
    """The resource type. It's expected to be ``azureVirtualMachine``."""

    alias: str
    """The product name to display in the Marketplace for customers."""


@define
class CustomerLeads(AzureProductLinkedResource):
    """
    Represent the customer leads section.

    `Schema definition for CustomerLeads <https://product-ingestion.azureedge.net/schema/customer-leads/2022-03-01-preview2>`_
    """  # noqa E501

    destination: str = field(validator=instance_of(str), metadata={"alias": "leadDestination"})
    """The lead destination for the product."""


@define
class TestDrive(AzureProductLinkedResource):
    """
    Represent the test drive section.

    `Schema definition for TestDrive <https://product-ingestion.azureedge.net/schema/test-drive/2022-03-01-preview2>`_
    """  # noqa E501

    # FIXME: Expecting `enabled == False`
    # At the moment I have no idea if there are
    # other attributes when `enabled == True`
    enabled: bool
    """Whether the TestDrive is enabled or not."""


@define
class PlanSummary(AzureProductLinkedResource):
    """
    Represent a plan summary.

    `Schema definition for PlanSummary <https://product-ingestion.azureedge.net/schema/plan/2022-03-01-preview2>`_
    """  # noqa E501

    identity: Identity = field(converter=Identity.from_json, on_setattr=NO_OP)  # type: ignore
    """
    The :class:`~cloudpub.models.ms_azure.Identity`  representing the `planId`
    from the `legacy CPP API`_.

    .. _legacy CPP API: https://learn.microsoft.com/en-us/azure/marketplace/cloud-partner-portal-api-overview
    """  # noqa E501

    alias: str
    """The plan name to display in the Marketplace for customers."""

    regions: List[str] = field(
        validator=deep_iterable(
            member_validator=instance_of(str),
            iterable_validator=instance_of(list),
        ),
        metadata={"alias": "azureRegions"},
    )
    """The regions where this plan is available."""


@define
class ProductProperty(AzureProductLinkedResource):
    """
    Represent a product property.

    `Schema definition for ProductProperty <https://product-ingestion.azureedge.net/schema/property/2022-03-01-preview2>`_
    """  # noqa E501

    kind: str
    """Expected to be ``azureVM``"""

    terms_of_use: Optional[str] = field(metadata={"alias": "termsOfUse"})
    """The product terms of use."""

    terms_conditions: Optional[str] = field(metadata={"alias": "termsConditions"})
    """The product terms and conditions."""

    categories: Dict[str, Any]  # FIXME: We don't need to process this yet so let it be like this
    """
    The Azure `categories`_ for the product.

    It supports the max of 2 categories.

    .. _categories: https://azure.microsoft.com/en-us/products/category
    """


@define
class Contact(AttrsJSONDecodeMixin):
    """Represent a single contact."""

    name: str
    """The contact name."""

    email: str
    """The contact e-mail."""

    phone: str
    """The contact phone."""


@define
class Listing(AzureProductLinkedResource):
    """
    Represent a product listing.

    `Schema definition for Listing <https://product-ingestion.azureedge.net/schema/listing/2022-03-01-preview2>`_
    """  # noqa E501

    kind: str
    """Expected to be ``azure``."""

    title: str
    """Listing title to display in the Marketplace for customers."""

    description: str
    """Listing description to display in the Marketplace for customers."""

    search_summary: str = field(metadata={"alias": "searchResultSummary"})
    """Summary to appear in the Marketplace search."""

    short_description: str = field(metadata={"alias": "shortDescription"})
    """Short description to display in the Marketplace for customers."""

    privacy_policy: str = field(metadata={"alias": "privacyPolicyLink"})
    """The privacy policy link for the product."""

    cspmm: str = field(metadata={"alias": "cloudSolutionProviderMarketingMaterials"})
    """
    The `CSP`_ marketing materials for the product.

    .. _CSP: https://learn.microsoft.com/en-us/azure/marketplace/cloud-solution-providers
    """

    support_contact: Contact = field(
        metadata={"alias": "supportContact"},
        converter=Contact.from_json,  # type: ignore
        on_setattr=NO_OP,
    )
    """The :class:`~cloudpub.models.ms_azure.Contact` for customer support."""

    engineering_contact: Contact = field(
        metadata={"alias": "engineeringContact"},
        converter=Contact.from_json,  # type: ignore
        on_setattr=NO_OP,
    )
    """The :class:`~cloudpub.models.ms_azure.Contact` for engineering support."""

    language: str = field(metadata={"alias": "languageId"})
    """The language ID for the listing."""


@define
class ListingAsset(AzureProductLinkedResource):
    """
    Represent an asset listing.

    `Schema definition for ListingAsset <https://product-ingestion.azureedge.net/schema/listing-asset/2022-03-01-preview2>`_
    """  # noqa E501

    kind: str
    """Expected to be ``azure``."""

    listing_durable_id: str = field(metadata={"alias": "listing"})
    """
    The listing-asset `durable ID`_.

    .. _durable ID: https://learn.microsoft.com/en-us/azure/marketplace/product-ingestion-api#method-2-durable-id
    """  # noqa E501

    type: str
    """
    The type of asset.

    Expected value (one of):

    * ``azureLogoSmall``
    * ``azureLogoMedium``
    * ``azureLogoLarge``
    * ``azureLogoWide``
    * ``azureLogoScreenshot``
    * ``azureLogoHero``
    * ``pdfDocument``
    """

    language: str = field(metadata={"alias": "languageId"})
    """Language ID for the asset."""

    description: str
    """The asset description."""

    display_order: int = field(metadata={"alias": "displayOrder"})
    """An integer with minimum of `0`."""

    file_name: str = field(metadata={"alias": "fileName"})
    """The asset file name."""

    friendly_name: str = field(metadata={"alias": "friendlyName"})
    """The asset alias."""

    url: str
    """The asset public URL."""

    @property
    def listing_id(self):
        """
        Resolve the listing ID from its `durable ID`_.

        .. _durable ID: https://learn.microsoft.com/en-us/azure/marketplace/product-ingestion-api#method-2-durable-id
        """  # noqa E501
        # durable ID format example:
        #   product/62c171e9-a2e1-45ab-9af0-d17e769da954
        # what do we want:
        #   62c171e9-a2e1-45ab-9af0-d17e769da954
        return self.product_durable_id.split("/")[-1]


@define
class Audience(AttrsJSONDecodeMixin):
    """Represent an audience."""

    type: str
    """
    The audience type.

    Expected value (one of):

    * ``none``
    * ``subscription``
    * ``ea``
    * ``msdn``
    * ``tenant``
    """

    id: str
    """The audience ID."""

    label: str
    """Optional label for the audience."""


@define
class ProductReseller(AzureProductLinkedResource):
    """
    Represent a reseller offer resource.

    `Schema definition for ProductReseller <https://product-ingestion.azureedge.net/schema/reseller/2022-03-01-preview2>`_
    """  # noqa E501

    reseller_channel_state: str = field(
        validator=instance_of(str), metadata={"alias": "resellerChannelState"}
    )
    """
    The reseller channel state.

    Expected value (one of):

    * ``notSet``
    * ``none``
    * ``some``
    * ``all``
    * ``terminated``
    """

    audiences: List[Audience] = field(
        converter=lambda x: [Audience(a) for a in x], on_setattr=NO_OP  # type: ignore
    )
    """List of :class:`~cloudpub.models.ms_azure.Audience` for the reseller offer."""


@define
class PublishTarget(AttrsJSONDecodeMixin):
    """Represent the publishing status of an :class:`~cloudpub.models.ms_azure.AzureResource`."""

    targetType: str = field(validator=instance_of(str))
    """
    The publishing status.

    Expected value (one of):

    * ``draft``
    * ``preview``
    * ``live``
    """

    @targetType.validator
    def _validate_target_type(instance, attribute: Attribute, value: Any):
        expected = ["draft", "preview", "live"]
        if value not in expected:
            raise ValueError(
                f"Got an unexpected value for \"{attribute.name}\": \"{value}\"\n"
                f"Expected: \"{expected}\"."
            )


@define
class ProductSubmission(AzureProductLinkedResource):
    """
    Represent the product submission state.

    `Schema definition for ProductSubmission <https://product-ingestion.azureedge.net/schema/submission/2022-03-01-preview2>`_
    """  # noqa E501

    target: PublishTarget = field(
        converter=PublishTarget.from_json, on_setattr=NO_OP  # type: ignore
    )
    """The product's :class:`~cloudpub.models.ms_azure.PublishTarget`."""

    lifecycle_state: str = field(validator=instance_of(str), metadata={"alias": "lifecycleState"})
    """
    The product publishing lifecycle state.

    Expected value (one of):

    * ``generallyAvailable``
    * ``deprecated``
    """


@define
class PlanListing(AzurePlanLinkedResource):
    """
    Represent a plan listing.

    `Schema definition for PlanListing <https://product-ingestion.azureedge.net/schema/plan-listing/2022-03-01-preview2>`_
    """  # noqa E501

    kind: str
    """Expected to be ``azureVM-plan``."""

    name: str = field(validator=instance_of(str))
    """Plan name to display in the marketplace."""

    description: str = field(validator=instance_of(str))
    """Description of the plan."""

    summary: str = field(validator=instance_of(str))
    """Summary of the plan."""

    language: str = field(validator=instance_of(str), metadata={"alias": "languageId"})
    """Language ID for the plan."""


@define
class CorePricing(AttrsJSONDecodeMixin):
    """Represent a price per core."""

    prince_input_option: str = field(metadata={"alias": "priceInputOption"})
    """
    The pricing model when the customer is using the resource.

    Expected value (one of):

    * ``free``
    * ``flat``
    * ``perCore``
    * ``perCoreSize``
    * ``perMarketAndCoreSize``
    """

    price: float = field(metadata={"hide_unset": True})
    """A float representing the flat price."""

    price_per_core: float = field(metadata={"alias": "pricePerCore", "hide_unset": True})
    """A float representing the price per core."""

    price_per_core_size: float = field(metadata={"alias": "pricePerCoreSize", "hide_unset": True})
    """A float representing the price per core size."""


@define
class Pricing(AttrsJSONDecodeMixin):
    """Represent the pricing."""

    license_model: str = field(metadata={"alias": "licenseModel"})
    """
    The license model for pricing.

    Expected value (one of):

    * ``byol``
    * ``payAsYouGo``
    """

    core_pricing: CorePricing = field(
        metadata={"alias": "corePricing"},
        converter=CorePricing.from_json,  # type: ignore
        on_setattr=NO_OP,
    )
    """The related :class:`~cloudpub.models.ms_azure.CorePricing`."""


@define
class PriceAndAvailabilityPlan(AzurePlanLinkedResource):
    """
    Represent the price and availability of a plan.

    `Schema definition for PriceAndAvailabilityPlan <https://product-ingestion.azureedge.net/schema/price-and-availability-plan/2022-03-01-preview2>`_
    """  # noqa E501

    visibility: str
    """
    The the plan visibility on marketplace.

    Expected value (one of):

    * ``visible``
    * ``hidden``
    """

    markets: List[str]
    """
    The countries which the plan is available.

    It expects the lowercase country code (e.g.: ``us``).
    """

    pricing: Pricing = field(converter=Pricing.from_json, on_setattr=NO_OP)  # type: ignore
    """The plan's :class:`~cloudpub.models.ms_azure.Pricing`."""

    trial: Optional[str]
    """
    When  set it allows customers to have a free trial of the plan during a period of:

    * One month; or
    * Three months; or
    * Six months
    """

    software_reservation: List[Dict[str, Any]] = field(metadata={"alias": "softwareReservation"})
    """
    When set it allows a pricing discount for customers doing a reservation for one or three years.
    """

    audience: str
    """
    It informs whether the plan is public or private.

    Expected value (one of):

    * ``public``
    * ``private``
    """

    private_audiences: List[Audience] = field(
        metadata={"alias": "privateAudiences"},
        converter=lambda x: [Audience.from_json(a) for a in x],
        on_setattr=NO_OP,
    )
    """
    The list of authorized :class:`~cloudpub.models.ms_azure.Audience`
    to consume the plan when it's marked as ``private``.
    """


@define
class PriceAndAvailabilityOffer(AzureProductLinkedResource):
    """
    Represent the price and availability of an offer.

    `Schema definition for PriceAndAvailabilityOffer <https://product-ingestion.azureedge.net/schema/price-and-availability-offer/2022-03-01-preview2>`_
    """  # noqa E501

    preview_audiences: List[Audience] = field(
        metadata={"alias": "previewAudiences"},
        converter=lambda x: [Audience.from_json(a) for a in x],
        on_setattr=NO_OP,
    )
    """
    The list of authorized :class:`~cloudpub.models.ms_azure.Audience`
    to preview the offer before publishing it to ``live``.
    """


@define
class OSDetails(AttrsJSONDecodeMixin):
    """Represent an operating system details."""

    family: str
    """
    The operating system family.

    It expects either ``linux`` or ``windows``.
    """

    friendly_name: str = field(metadata={"alias": "friendlyName"})
    """The friendly name for the operating system."""

    os_type: str = field(metadata={"alias": "type"})
    """The OS version or distribution name."""


@define
class VMIProperties(AttrsJSONDecodeMixin):
    """Represent the properties of a Virtual Machine Image."""

    supportsExtensions: bool = field(default=True, metadata={"hide_unset": True})
    """
    Boolean indicating the extensions support. `See the docs`_ for more details.

    .. _See the docs: https://learn.microsoft.com/en-us/azure/marketplace/azure-vm-plan-technical-configuration#properties
    """  # noqa E501

    supportsBackup: bool = field(default=False, metadata={"hide_unset": True})
    """
    Boolean indicating the backup support. `See the docs`_ for more details.

    .. _See the docs: https://learn.microsoft.com/en-us/azure/marketplace/azure-vm-plan-technical-configuration#properties
    """  # noqa E501

    supportsAcceleratedNetworking: bool = field(default=False, metadata={"hide_unset": True})
    """
    Boolean indicating the accelerated network support. `See the docs`_ for more details.

    .. _See the docs: https://learn.microsoft.com/en-us/azure/marketplace/azure-vm-plan-technical-configuration#properties
    """  # noqa E501

    isNetworkVirtualAppliance: bool = field(default=False, metadata={"hide_unset": True})
    """
    Boolean indicating the network virtual appliance support. `See the docs`_ for more details.

    .. _See the docs: https://learn.microsoft.com/en-us/azure/marketplace/azure-vm-plan-technical-configuration#properties
    """  # noqa E501

    supportsNVMe: bool = field(default=False, metadata={"hide_unset": True})
    """
    Boolean indicating the NVMe support. `See the docs`_ for more details.

    .. _See the docs: https://learn.microsoft.com/en-us/azure/marketplace/azure-vm-plan-technical-configuration#properties
    """  # noqa E501

    supportsCloudInit: bool = field(default=False, metadata={"hide_unset": True})
    """
    Boolean indicating the cloud-init configuration support. `See the docs`_ for more details.

    .. _See the docs: https://learn.microsoft.com/en-us/azure/marketplace/azure-vm-plan-technical-configuration#properties
    """  # noqa E501

    supportsAadLogin: bool = field(default=False, metadata={"hide_unset": True})
    """
    Boolean indicating the AAD login support. `See the docs`_ for more details.

    .. _See the docs: https://learn.microsoft.com/en-us/azure/marketplace/azure-vm-plan-technical-configuration#properties
    """  # noqa E501

    supportsHibernation: bool = field(default=False, metadata={"hide_unset": True})
    """
    Boolean indicating the hibernation support. `See the docs`_ for more details.

    .. _See the docs: https://learn.microsoft.com/en-us/azure/marketplace/azure-vm-plan-technical-configuration#properties
    """  # noqa E501

    supportsRemoteConnection: bool = field(default=True, metadata={"hide_unset": True})
    """
    Boolean indicating the RDP/SSH support. `See the docs`_ for more details.

    .. _See the docs: https://learn.microsoft.com/en-us/azure/marketplace/azure-vm-plan-technical-configuration#properties
    """  # noqa E501

    requiresCustomArmTemplate: bool = field(default=False, metadata={"hide_unset": True})
    """
    Boolean indicating the image requires to use a custom ARM template for deployment.
    `See the docs`_ for more details.

    .. _See the docs: https://learn.microsoft.com/en-us/azure/marketplace/azure-vm-plan-technical-configuration#properties
    """  # noqa E501


@define
class VMISku(AttrsJSONDecodeMixin):
    """Represent the SKU for a Virtual Machine Image."""

    id: str = field(validator=instance_of(str), metadata={"alias": "skuId"})
    """The SKU ID. Expects ``{plan_name}`` or ``{plan_name}-gen1``."""

    image_type: str = field(validator=instance_of(str), metadata={"alias": "imageType"})
    """The image type. Expects ``{arch}Gen2`` or ``{arch}Gen1``"""


@define
class OSDiskURI(AttrsJSONDecodeMixin):
    """Represent an Operating System Disk URI."""

    uri: str = field(validator=instance_of(str))
    """The full SAS URI for the Virtual Machine Image."""


@define
class VMImageSource(AttrsJSONDecodeMixin):
    """Represent a Virtual Machine Image Source."""

    source_type: str = field(validator=instance_of(str), metadata={"alias": "sourceType"})
    """
    The virtual machine image source type.

    Expected value (one of):

    * ``sasUri``
    * ``sharedImageGallery``
    """

    os_disk: OSDiskURI = field(
        metadata={"alias": "osDisk"},
        converter=OSDiskURI.from_json,  # type: ignore
        on_setattr=NO_OP,
    )
    """The :class:`~cloudpub.models.ms_azure.OSDiskURI` with the OS disk URI."""

    data_disks: List[Any] = field(metadata={"alias": "dataDisks"})  # TODO: Implement DataDisk model
    """The list of data disks to mount within the OS."""

    @source_type.validator
    def _validate_source_type(instance, attribute: Attribute, value: Any):
        if not value == "sasUri":
            raise ValueError(
                f"Got an unexpected value for \"{attribute.name}\": \"{value}\"\n"
                "Expected: \"sasUri\"."
            )


@define
class VMImageDefinition(AttrsJSONDecodeMixin):
    """Represent a Virtual Machine Image Definition."""

    image_type: str = field(validator=instance_of(str), metadata={"alias": "imageType"})
    """
    The image type. Expects ``{arch}Gen1`` or ``{arch}Gen2``.

    For more details of VHD Generation `check the docs`_.

    .. _check the docs: https://learn.microsoft.com/en-us/previous-versions/windows/it-pro/windows-server-2012-r2-and-2012/dn282285(v=ws.11)
    """  # noqa E501

    source: VMImageSource = field(
        converter=VMImageSource.from_json, on_setattr=NO_OP  # type: ignore
    )
    """The :class:`~cloudpub.models.ms_azure.VMImageSource` with the image."""


@define
class DiskVersion(AttrsJSONDecodeMixin):
    """Represent a Disk Version."""

    version_number: str = field(metadata={"alias": "versionNumber"})
    """
    The Disk version number.

    It expects a string with format ``{int}.{int}.{int}``.
    """

    vm_images: List[VMImageDefinition] = field(
        metadata={"alias": "vmImages"},
        converter=lambda x: [VMImageDefinition.from_json(a) for a in x],
        on_setattr=NO_OP,
    )
    """The list of :class:`~cloudpub.models.ms_azure.VMImageDefinition` for this disk version."""

    lifecycle_state: str = field(metadata={"alias": "lifecycleState"})
    """
    The disk lifeclycle state.

    Expected value (one of):

    * ``generallyAvailable``
    * ``deprecated``
    * ``deleted``
    """


@define
class VMIPlanTechConfig(AzurePlanLinkedResource):
    """
    Represent the VM technical configuration of a Plan.

    `Schema definition for VMIPlanTechConfig <https://product-ingestion.azureedge.net/schema/virtual-machine-plan-technical-configuration/2022-03-01-preview2>`_
    """  # noqa E501

    operating_system: OSDetails = field(
        metadata={"alias": "operatingSystem"},
        converter=OSDetails.from_json,  # type: ignore
        on_setattr=NO_OP,
    )
    """The plan's :class:`~cloudpub.models.ms_azure.OSDetails`."""

    recommended_vm_sizes: List[str] = field(metadata={"alias": "recommendedVmSizes"})
    """
    The list of recommended Azure Virtual Machine sizes for the OS.

    The maximum lengh of this list is 6.
    """

    open_ports: List[str] = field(metadata={"alias": "openPorts"})
    """The list of OS exposed ports when booting the VM."""

    vm_properties: VMIProperties = field(
        metadata={"alias": "vmProperties"},
        converter=VMIProperties.from_json,  # type: ignore
        on_setattr=NO_OP,
    )
    """The plan's :class:`~cloudpub.models.ms_azure.VMIProperties`."""

    skus: List[VMISku] = field(
        converter=lambda x: [VMISku.from_json(a) for a in x], on_setattr=NO_OP
    )
    """The list of available :class:`~cloudpub.models.ms_azure.VMISku` in the plan."""

    disk_versions: List[DiskVersion] = field(
        metadata={"alias": "vmImageVersions"},
        converter=lambda x: [DiskVersion.from_json(a) for a in x],
        on_setattr=NO_OP,
    )
    """The list of available :class:`~cloudpub.models.ms_azure.DiskVersion` in the plan."""


RESOURCE_MAPING = {
    "product": ProductSummary,
    "customer-leads": CustomerLeads,
    "test-drive": TestDrive,
    "plan": PlanSummary,
    "property": ProductProperty,
    "plan-listing": PlanListing,
    "listing": Listing,
    "listing-asset": ListingAsset,
    "price-and-availability-offer": PriceAndAvailabilityOffer,
    "price-and-availability-plan": PriceAndAvailabilityPlan,
    "virtual-machine-plan-technical-configuration": VMIPlanTechConfig,
    "reseller": ProductReseller,
    "submission": ProductSubmission,
}


@define
class Product(AttrsJSONDecodeMixin):
    """
    Represent the entire product from resource-tree.

    `Schema definition <https://product-ingestion.azureedge.net/schema/resource-tree/2022-03-01-preview2>`_
    """  # noqa E501

    schema: str = field(validator=instance_of(str), metadata={"alias": "$schema"})
    """The top level product schema (root)."""

    root_id: str = field(validator=instance_of(str), metadata={"alias": "root"})
    """The resource durable ID."""

    target: PublishTarget = field(
        converter=PublishTarget.from_json,  # type: ignore
        on_setattr=NO_OP,
    )
    """The :class:`~cloudpub.models.ms_azure.PublishTarget` with product's publishing state."""

    resources: List[AzureResource]  # Now its on us to resolve the ambiguity between AzureResources
    """The list of :class:`~cloudpub.models.ms_azure.AzureResource` associated with the product."""

    @property
    def id(self):
        """Resolve the product ID from its durable ID."""
        # durable ID format example:
        #   product/62c171e9-a2e1-45ab-9af0-d17e769da954
        # what do we want:
        #   62c171e9-a2e1-45ab-9af0-d17e769da954
        return self.root_id.split("/")[-1]

    @property
    def resource(self):
        """Resource name from its durable ID."""
        return self.root_id.split("/")[0]

    @classmethod
    def _preprocess_json(cls, json: Dict[str, Any]) -> Dict[str, Any]:
        """
        Resolve the resources ambiguity from JSON according to its proper type.

        Args:
            json (dict)
                The incoming json to parse.
        Returns:
            dict: The transformed json with the resolved resources.
        """
        # Create a list of resources resolved by its proper type
        res = []
        for resource in json.pop("resources", []):
            res_name = resource["id"].split("/")[0]
            klass = RESOURCE_MAPING[res_name]
            res.append(klass.from_json(resource))  # type: ignore

        json["resources"] = res
        return json

    def to_json(self):
        """
        Convert a Product instance into a dictionary.

        Returns:
            dict: The JSON from Product instance.
        """
        return {
            "$schema": self.schema,
            "root": self.root_id,
            "target": self.target.to_json(),
            "resources": [x.to_json() for x in self.resources],
        }
