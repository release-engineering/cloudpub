# SPDX-License-Identifier: GPL-3.0-or-later
import logging
import sys
from typing import Any, Dict, List, Optional

if sys.version_info >= (3, 8):
    from typing import Literal  # pragma: no cover
else:
    from typing_extensions import Literal  # pragma: no cover

from attrs import Attribute, define, field
from attrs.setters import NO_OP
from attrs.validators import deep_iterable, instance_of, optional

from cloudpub.models.common import AttrsJSONDecodeMixin

MASKED_SECRET: str = "*********"
MS_SCHEMA = "$schema"

log = logging.getLogger(__name__)


def _mask_secret(value: str) -> str:
    """Replace a possible secret string with ``*********``."""
    if value and value != MASKED_SECRET:
        value = MASKED_SECRET
    return value


@define
class ConfigureStatus(AttrsJSONDecodeMixin):
    """Represent a response from a :meth:`~AzureService.configure` request."""

    job_id: str = field(metadata={"alias": "jobId"})
    """The configure Job ID."""

    job_status: str = field(metadata={"alias": "jobStatus"})
    """
    The status of the configure job.

    Expected value (one of):

    * ``notStarted``
    * ``running``
    * ``completed``
    """

    job_result: str = field(metadata={"alias": "jobResult"})
    """
    The result of the configure job when finished.

    Expected value (one of):

    * ``pending``
    * ``succeeded``
    * ``failed``
    * ``cancelled``
    """

    job_start: str = field(metadata={"alias": "jobStart"})
    """The date when the configure job started."""

    job_end: Optional[str] = field(metadata={"alias": "jobEnd", "hide_unset": True})
    """The date when the configure job finished."""

    resource_uri: Optional[str] = field(metadata={"alias": "resourceUri", "hide_unset": True})
    """The resource URI related to the configure job."""

    errors: List[str]
    """List of errors when the ``job_result`` is ``failed``."""


@define
class AzureResource(AttrsJSONDecodeMixin):
    """The base class for all Azure Resources."""

    schema: str = field(validator=instance_of(str), metadata={"alias": MS_SCHEMA})
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
class DeprecationAlternative(AttrsJSONDecodeMixin):
    """
    Define an alternative product or plan for a deprecated one.

    It's part of :class:`~cloudpub.models.ms_azure.DeprecationSchedule`.
    """

    product_durable_id: Optional[str] = field(
        validator=optional(instance_of(str)), metadata={"alias": "product", "hide_unset": True}
    )
    """
    The deprecated product `durable ID`_.

    .. _durable ID: https://learn.microsoft.com/en-us/azure/marketplace/product-ingestion-api#method-2-durable-id
    """  # noqa E501

    plan_durable_id: Optional[str] = field(
        validator=optional(instance_of(str)), metadata={"alias": "plan", "hide_unset": True}
    )
    """
    The deprecated plan `durable ID`_.

    .. _durable ID: https://learn.microsoft.com/en-us/azure/marketplace/product-ingestion-api#method-2-durable-id
    """  # noqa E501

    @property
    def plan_id(self) -> Optional[str]:
        """
        Resolve the plan ID from its `durable ID`_.

        .. _durable ID: https://learn.microsoft.com/en-us/azure/marketplace/product-ingestion-api#method-2-durable-id
        """  # noqa E501
        # durable ID format example:
        #   plan/62c171e9-a2e1-45ab-9af0-d17e769da954
        # what do we want:
        #   62c171e9-a2e1-45ab-9af0-d17e769da954
        if self.plan_durable_id:
            return self.plan_durable_id.split("/")[-1]
        return None

    @property
    def product_id(self) -> Optional[str]:
        """
        Resolve the product ID from its `durable ID`_.

        .. _durable ID: https://learn.microsoft.com/en-us/azure/marketplace/product-ingestion-api#method-2-durable-id
        """  # noqa E501
        # durable ID format example:
        #   product/62c171e9-a2e1-45ab-9af0-d17e769da954
        # what do we want:
        #   62c171e9-a2e1-45ab-9af0-d17e769da954
        if self.product_durable_id:
            return self.product_durable_id.split("/")[-1]
        return None


@define
class DeprecationSchedule(AttrsJSONDecodeMixin):
    """
    Represent a deprecation schedule.

    It's part of :class:`~cloudpub.models.ms_azure.ProductSummary`,
    :class:`~cloudpub.models.ms_azure.PlanSummary` and
    :class:`~cloudpub.models.ms_azure.ProductSubmission`.

    `Schema definition for DeprecationSchedule <https://schema.mp.microsoft.com/schema/deprecation-schedule/2022-03-01-preview2>`_
    """  # noqa E501

    schema: Optional[str] = field(
        validator=optional(instance_of(str)), metadata={"alias": MS_SCHEMA, "hide_unset": True}
    )
    """
    The `resource schema`_ for Graph API.

    .. _resource schema: https://learn.microsoft.com/en-us/azure/marketplace/product-ingestion-api#resource-api-reference
    """  # noqa E501

    date: str
    """The date for deprecation."""

    date_offset: Optional[str] = field(
        validator=optional(instance_of(str)), metadata={"hide_unset": True}
    )
    """The date offset for deprecation."""

    reason: str = field(metadata={"default": "other"})
    """
    The deprecation reason.

    Expected value (one of):

    * ``criticalSecurityIssue``
    * ``endOfSupport``
    * ``other``
    """

    alternative: Optional[DeprecationAlternative] = field(
        converter=DeprecationAlternative.from_json,  # type: ignore
        on_setattr=NO_OP,
        metadata={"hide_unset": True},
    )
    """The alternative product or plan for the deprecated one."""


@define
class ProductSummary(AzureResource):
    """
    Represent a product summary.

    `Schema definition for ProductSummary <https://schema.mp.microsoft.com/schema/product/2022-03-01-preview2>`_
    """  # noqa E501

    identity: Identity = field(converter=Identity.from_json, on_setattr=NO_OP)  # type: ignore
    """
    The :class:`~cloudpub.models.ms_azure.Identity` representing the `offerId`
    from the `legacy CPP API`_.

    .. _legacy CPP API: https://learn.microsoft.com/en-us/azure/marketplace/cloud-partner-portal-api-overview
    """  # noqa E501

    type: str = field(validator=instance_of(str))
    """
    The resource type.

    Expected type (one of):

    * ``azureApplication``
    * ``azureContainer``
    * ``azureVirtualMachine``
    * ``consultingService``
    * ``containerApp``
    * ``coreVirtualMachine``
    * ``cosellOnly``
    * ``dynamics365BusinessCentral``
    * ``dynamics365ForCustomerEngagement``
    * ``dynamics365ForOperations``
    * ``iotEdgeModule``
    * ``managedService``
    * ``powerBiApp``
    * ``powerBiVisual``
    * ``softwareAsAService``
    * ``xbox360NonBackcompat``
    """

    alias: str
    """The product name to display in the Marketplace for customers."""

    lifecycle_state: Optional[str] = field(
        validator=optional(instance_of(str)),
        metadata={"alias": "lifecycleState", "hide_unset": True},
    )
    """
    The product lifecycle state.

    Expected value (one of):

    * ``generallyAvailable``
    * ``deprecated``
    * ``deleted``
    """

    deprecation_schedule: Optional[DeprecationSchedule] = field(
        metadata={"alias": "deprecationSchedule", "hide_unset": True},
        converter=DeprecationSchedule.from_json,  # type: ignore
        on_setattr=NO_OP,
    )
    """The deprecation schedule for the product if going to be deprecated."""


@define
class LeadConfiguration(AttrsJSONDecodeMixin):
    """
    Define the common fields for all lead configuration models.

    It's part of :class:`~cloudpub.models.ms_azure.CustomerLeads`.
    """

    contact_email: Optional[List[str]] = field(
        metadata={"alias": "contactEmail", "hide_unset": True}
    )
    """List of e-mails for a lead configuration."""


@define
class BlobLeadConfiguration(LeadConfiguration):
    """
    Define the blob lead configuration.

    It's part of :class:`~cloudpub.models.ms_azure.CustomerLeads`.
    """

    storage_connection_string: str = field(
        metadata={"alias": "storageAccountConnectionString"}, converter=_mask_secret
    )
    """
    The storage connection string.

    It can be either the plain text connection string or a masked value.
    """

    container_name: str = field(metadata={"alias": "containerName"})
    """The storage container name."""


@define
class DynamicsLeadConfiguration(LeadConfiguration):
    """
    Define the dynamics lead configuration.

    It's part of :class:`~cloudpub.models.ms_azure.CustomerLeads`.
    """

    instance_url: str = field(metadata={"alias": "instanceUrl"})
    """The dynamics instance URL."""

    authentication: str
    """
    The authentication type for dynamics.

    Expected value (one of):

    * ``azureAD``
    * ``office365``
    """

    username: Optional[str] = field(
        validator=optional(instance_of(str)), metadata={"hide_unset": True}
    )
    """The username for dynamics."""

    password: Optional[str] = field(
        validator=optional(instance_of(str)), metadata={"hide_unset": True}, converter=_mask_secret
    )
    """
    The password for dynamics.

    It can be either the plain text connection string or a masked value.
    """

    application_id: Optional[str] = field(
        validator=optional(instance_of(str)),
        metadata={"alias": "applicationId", "hide_unset": True},
    )
    """The dynamics application UUID."""

    application_key: Optional[str] = field(
        validator=optional(instance_of(str)),
        metadata={"alias": "applicationKey", "hide_unset": True},
        converter=_mask_secret,
    )
    """The dynamics application key."""

    directory_id: Optional[str] = field(
        validator=optional(instance_of(str)), metadata={"alias": "directoryId", "hide_unset": True}
    )
    """The dynamics directory UUID."""


@define
class EmailLeadConfiguration(AttrsJSONDecodeMixin):
    """
    Define the e-mail lead configuration.

    It's part of :class:`~cloudpub.models.ms_azure.CustomerLeads`.
    """

    contact_email: List[str] = field(metadata={"alias": "contactEmail"})
    """List of e-mails for the e-mail lead configuration."""


@define
class HttpsEndpointLeadConfiguration(LeadConfiguration):
    """
    Define the https lead configuration.

    It's part of :class:`~cloudpub.models.ms_azure.CustomerLeads`.
    """

    endpoint_url: str = field(metadata={"alias": "httpsEndpointUrl"})
    """The HTTPS endpoint for the lead configuration."""


@define
class MarketoLeadConfiguration(LeadConfiguration):
    """
    Define the marketo lead configuration.

    It's part of :class:`~cloudpub.models.ms_azure.CustomerLeads`.
    """

    server_id: str = field(metadata={"alias": "serverId"})
    """The marketo server ID."""

    munchkin_id: str = field(metadata={"alias": "munchkinId"})
    """The marketo munchkin ID."""

    form_id: str = field(metadata={"alias": "formId"})
    """The marketo form ID."""


@define
class SalesforceLeadConfiguration(LeadConfiguration):
    """
    Define the salesforce lead configuration.

    It's part of :class:`~cloudpub.models.ms_azure.CustomerLeads`.
    """

    object_identifier: str = field(metadata={"alias": "objectIdentifier"})
    """The salesforce object identifier."""


@define
class TableLeadConfiguration(LeadConfiguration):
    """
    Define the table lead configuration.

    It's part of :class:`~cloudpub.models.ms_azure.CustomerLeads`.
    """

    storage_connection_string: str = field(
        metadata={"alias": "storageAccountConnectionString"}, converter=_mask_secret
    )
    """
    The storage connection string.

    It can be either the plain text connection string as well as a masked value.
    """


@define
class CustomerLeads(AzureProductLinkedResource):
    """
    Represent the customer leads section.

    `Schema definition for CustomerLeads <https://schema.mp.microsoft.com/schema/customer-leads/2022-03-01-preview2>`_
    """  # noqa E501

    destination: str = field(validator=instance_of(str), metadata={"alias": "leadDestination"})
    """
    The lead destination type for the product.

    Expected value (one of):

    * ``none``
    * ``blob``
    * ``dynamics``
    * ``email``
    * ``httpsEndpoint``
    * ``marketo``
    * ``salesforce``
    * ``table``
    """

    blob_lead_config: Optional[BlobLeadConfiguration] = field(
        metadata={"alias": "blobLeadConfiguration", "hide_unset": True},
        converter=BlobLeadConfiguration.from_json,  # type: ignore
        on_setattr=NO_OP,
    )
    """The lead configuration for ``blob``."""

    dynamic_lead_config: Optional[DynamicsLeadConfiguration] = field(
        metadata={"alias": "dynamicsLeadConfiguration", "hide_unset": True},
        converter=DynamicsLeadConfiguration.from_json,  # type: ignore
        on_setattr=NO_OP,
    )
    """The lead configuration for ``dynamics``."""

    email_lead_config: Optional[EmailLeadConfiguration] = field(
        metadata={"alias": "emailLeadConfiguration", "hide_unset": True},
        converter=EmailLeadConfiguration.from_json,  # type: ignore
        on_setattr=NO_OP,
    )
    """The lead configuration for ``email``."""

    https_endpoint_lead_config: Optional[HttpsEndpointLeadConfiguration] = field(
        metadata={"alias": "httpsEndpointLeadConfiguration", "hide_unset": True},
        converter=HttpsEndpointLeadConfiguration.from_json,  # type: ignore
        on_setattr=NO_OP,
    )
    """The lead configuration for ``httpsEndpoint``."""

    marketo_lead_config: Optional[MarketoLeadConfiguration] = field(
        metadata={"alias": "marketoLeadConfiguration", "hide_unset": True},
        converter=MarketoLeadConfiguration.from_json,  # type: ignore
        on_setattr=NO_OP,
    )
    """The lead configuration for ``marketo``."""

    salesforce_lead_config: Optional[SalesforceLeadConfiguration] = field(
        metadata={"alias": "salesforceLeadConfiguration", "hide_unset": True},
        converter=SalesforceLeadConfiguration.from_json,  # type: ignore
        on_setattr=NO_OP,
    )
    """The lead configuration for ``salesforce``."""

    table_lead_config: Optional[TableLeadConfiguration] = field(
        metadata={"alias": "tableLeadConfiguration", "hide_unset": True},
        converter=TableLeadConfiguration.from_json,  # type: ignore
        on_setattr=NO_OP,
    )
    """The lead configuration for ``table``."""


@define
class TestDrive(AzureProductLinkedResource):
    """
    Represent the test drive section.

    `Schema definition for TestDrive <https://schema.mp.microsoft.com/schema/test-drive/2022-03-01-preview2>`_
    """  # noqa E501

    # Added to appease PytestCollection
    __test__ = False

    enabled: bool
    """Whether the TestDrive is enabled or not."""

    type: Optional[str] = field(validator=optional(instance_of(str)), metadata={"hide_unset": True})
    """
    The Test drive type, required only when ``enabled == True``.

    Expected value (one of):

    * ``azureResourceManager``
    * ``dynamicsForBusinessCentral``
    * ``dynamicsForCustomerEngagement``
    * ``dynamicsForOperations``
    * ``logicApp``
    * ``powerBi``
    """


@define
class GovernmentCertification(AttrsJSONDecodeMixin):
    """
    Define a government certification.

    It's part of :class:`~cloudpub.models.ms_azure.PlanSummary`.
    """

    name: str
    """The certification name."""

    link: str
    """The URL for the certification web-page."""


@define
class PlanSummary(AzureProductLinkedResource):
    """
    Represent a plan summary.

    `Schema definition for PlanSummary <https://schema.mp.microsoft.com/schema/plan/2022-03-01-preview2>`_
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
    """
    The regions where this plan is available.

    Valid values (unique):

    * ``azureGlobal``
    * ``azureGovernment``
    * ``azureGermany``
    * ``azureChina``
    """

    gov_certifications: Optional[List[GovernmentCertification]] = field(
        metadata={"alias": "azureGovernmentCertifications", "hide_unset": True},
        converter=lambda x: [GovernmentCertification.from_json(a) for a in x] if x else None,  # type: ignore  # noqa: E501
        on_setattr=NO_OP,
    )
    """Certifications for government plans."""

    display_rank: Optional[int] = field(metadata={"alias": "displayRank", "hide_unset": True})

    subtype: str = field(metadata={"hide_unset": True})
    """
    Specifies the plan type (AzureApplication-type products only).

    Expected value (one of):

    * ``managedApplication``
    * ``solutionTemplate``

    For more details: https://go.microsoft.com/fwlink/?linkid=2106322
    """

    lifecycle_state: Optional[str] = field(
        validator=optional(instance_of(str)),
        metadata={"alias": "lifecycleState", "hide_unset": True},
    )
    """
    The plan lifecycle state.

    Expected value (one of):

    * ``generallyAvailable``
    * ``deprecated``
    * ``deleted``
    """

    deprecation_schedule: Optional[DeprecationSchedule] = field(
        metadata={"alias": "deprecationSchedule", "hide_unset": True},
        converter=DeprecationSchedule.from_json,  # type: ignore
        on_setattr=NO_OP,
    )
    """The deprecation schedule for the plan if going to be deprecated."""


@define
class ProductProperty(AzureProductLinkedResource):
    """
    Represent a product property.

    `Schema definition for ProductProperty <https://schema.mp.microsoft.com/schema/property/2022-03-01-preview2>`_
    """  # noqa E501

    kind: str
    """Expected to be ``azureVM``"""

    terms_of_use: Optional[str] = field(
        validator=optional(instance_of(str)), metadata={"alias": "termsOfUse"}
    )
    """The product terms of use."""

    terms_conditions: Optional[str] = field(
        validator=optional(instance_of(str)), metadata={"alias": "termsConditions"}
    )
    """The product terms and conditions."""

    categories: Dict[str, List[str]]
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
class ThumbnailURL(AttrsJSONDecodeMixin):
    """
    Define a video thumbnail URL.

    It's part of :class:`~cloudpub.models.ms_azure.VideoThumbnails`.
    """

    url: str
    """URL of the thumbnail."""


@define
class VideoThumbnails(AttrsJSONDecodeMixin):
    """
    Define a group of thumbnails.

    It's part of :class:`~cloudpub.models.ms_azure.ListingTrailer`.
    """

    title: str
    """The thumbnail title."""

    image_list: List[ThumbnailURL] = field(
        metadata={"alias": "imageList"},
        converter=lambda x: [ThumbnailURL.from_json(a) for a in x] if x else [],  # type: ignore
        on_setattr=NO_OP,
    )


@define
class Listing(AzureProductLinkedResource):
    """
    Represent a product listing.

    `Schema definition for Listing <https://schema.mp.microsoft.com/schema/listing/2022-03-01-preview2>`_
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

    general_links: Optional[List[str]] = field(
        metadata={"alias": "generalLinks", "hide_unset": True}
    )
    """General links for the product listing."""

    cspmm: str = field(metadata={"alias": "cloudSolutionProviderMarketingMaterials"})
    """
    The `CSP`_ marketing materials for the product.

    .. _CSP: https://learn.microsoft.com/en-us/azure/marketplace/cloud-solution-providers
    """

    gov_support_site: Optional[str] = field(
        validator=optional(instance_of(str)),
        metadata={"alias": "governmentSupportWebsite", "hide_unset": True},
    )
    """The support web-site for government product listing."""

    global_support_site: Optional[str] = field(
        validator=optional(instance_of(str)),
        metadata={"alias": "globalSupportWebsite", "hide_unset": True},
    )
    """The support web-site for product listing."""

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

    cloud_solution_provider_contact: Optional[Contact] = field(
        metadata={"alias": "cloudSolutionProviderContact", "hide_unset": True},
        converter=Contact.from_json,  # type: ignore
        on_setattr=NO_OP,
    )
    """The :class:`~cloudpub.models.ms_azure.Contact` for cloud provider support."""

    language: str = field(metadata={"alias": "languageId"})
    """The language ID for the listing."""

    lifecycle_state: Optional[str] = field(
        validator=optional(instance_of(str)),
        metadata={"alias": "lifecycleState", "hide_unset": True},
    )
    """
    The Listing lifecycle state.

    Expected value (one of):

    * ``generallyAvailable``
    * ``deleted``
    """


@define
class ListingAsset(AzureProductLinkedResource):
    """
    Represent an asset listing.

    `Schema definition for ListingAsset <https://schema.mp.microsoft.com/schema/listing-asset/2022-03-01-preview2>`_
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

    lifecycle_state: Optional[str] = field(
        validator=optional(instance_of(str)),
        metadata={"alias": "lifecycleState", "hide_unset": True},
    )
    """
    The Listing lifecycle state.

    Expected value (one of):

    * ``generallyAvailable``
    * ``deleted``
    """

    @property
    def listing_id(self):
        """
        Resolve the listing ID from its `durable ID`_.

        .. _durable ID: https://learn.microsoft.com/en-us/azure/marketplace/product-ingestion-api#method-2-durable-id
        """  # noqa E501
        # durable ID format example:
        #   listing/62c171e9-a2e1-45ab-9af0-d17e769da954/.../...
        # what do we want:
        #   62c171e9-a2e1-45ab-9af0-d17e769da954
        return self.listing_durable_id.split("/")[1]


@define
class ListingTrailer(AzureProductLinkedResource):
    """Represent a video "trailer" asset for the given product.

    `Schema definition for ListingTrailer <https://schema.mp.microsoft.com/schema/listing-trailer/2022-03-01-preview3>`_
    """  # noqa E501

    kind: str
    """Expected to be ``azure``."""

    listing_durable_id: str = field(metadata={"alias": "listing"})
    """
    The listing-trailer `durable ID`_.
    """

    streaming_url: str = field(metadata={"alias": "streamingUrl"})
    """
    The URL for the video streaming.

    E.g: https://www.youtube.com/watch?v=XXXXX
    """

    assets: Dict[Literal["en-us"], VideoThumbnails]
    """
    Assets for the related video trailer.

    At the moment only content in English is supported.
    """

    @property
    def listing_id(self):
        """
        Resolve the listing-trailer ID from its `durable ID`_.

        .. _durable ID: https://learn.microsoft.com/en-us/azure/marketplace/product-ingestion-api#method-2-durable-id
        """  # noqa E501
        # durable ID format example:
        #   listing-trailer/62c171e9-a2e1-45ab-9af0-d17e769da954/.../...
        # what do we want:
        #   62c171e9-a2e1-45ab-9af0-d17e769da954
        return self.listing_durable_id.split("/")[1]


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

    `Schema definition for ProductReseller <https://schema.mp.microsoft.com/schema/reseller/2022-03-01-preview2>`_
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
        converter=lambda x: [Audience.from_json(a) for a in x] if x else [], on_setattr=NO_OP  # type: ignore  # noqa: E501
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
    def _validate_target_type(self, attribute: Attribute, value: Any):
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

    `Schema definition for ProductSubmission <https://schema.mp.microsoft.com/schema/submission/2022-03-01-preview2>`_
    """  # noqa E501

    target: PublishTarget = field(
        converter=PublishTarget.from_json, on_setattr=NO_OP  # type: ignore
    )
    """The product's :class:`~cloudpub.models.ms_azure.PublishTarget`."""

    status: Optional[str] = field(
        validator=optional(instance_of(str)), metadata={"hide_unset": True}
    )
    """
    The publishing status.

    Expected value when set (one of):

    * ``notStarted``
    * ``running``
    * ``completed``
    """

    result: Optional[str] = field(
        validator=optional(instance_of(str)), metadata={"hide_unset": True}
    )
    """
    The submission result when ``status == completed``.

    Expected value when set (one of):

    * ``pending``
    * ``succeeded``
    * ``failed``
    """

    created: Optional[str] = field(
        validator=optional(instance_of(str)), metadata={"hide_unset": True}
    )
    """The creation date for the submission."""

    lifecycle_state: Optional[str] = field(
        validator=optional(instance_of(str)),
        metadata={"alias": "lifecycleState", "hide_unset": True},
    )
    """
    The product publishing lifecycle state.

    Expected value (one of):

    * ``generallyAvailable``
    * ``deprecated``
    """

    deprecation_schedule: Optional[DeprecationSchedule] = field(
        metadata={"alias": "deprecationSchedule", "hide_unset": True},
        converter=DeprecationSchedule.from_json,  # type: ignore
        on_setattr=NO_OP,
    )
    """The deprecation schedule for the VM submission if it's going to be deprecated."""


@define
class PlanListing(AzurePlanLinkedResource):
    """
    Represent a plan listing.

    `Schema definition for PlanListing <https://schema.mp.microsoft.com/schema/plan-listing/2022-03-01-preview2>`_
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

    lifecycle_state: Optional[str] = field(
        validator=optional(instance_of(str)),
        metadata={"alias": "lifecycleState", "hide_unset": True},
    )
    """
    The Listing lifecycle state.

    Expected value (one of):

    * ``generallyAvailable``
    * ``deleted``
    """


@define
class CorePricing(AttrsJSONDecodeMixin):
    """Represent a price per core."""

    price_input_option: str = field(metadata={"alias": "priceInputOption"})
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
class SoftwareReservation(AttrsJSONDecodeMixin):
    """
    Define the reservation prices for a plan.

    It's part of :class:`~cloudpub.models.ms_azure.PriceAndAvailabilityPlan`.

    `Schema definition for SoftwareReservation <https://schema.mp.microsoft.com/schema/price-and-availability-software-reservation/2022-03-01-preview2>`_
    """  # noqa E501

    type: str
    """
    The reservation type.

    Expected value (one of):

    * ``month``
    * ``year``
    """

    term: int
    """The amount of months or years for reservation."""

    percentage_save: int = field(metadata={"alias": "percentageSave"})
    """The percentual of discount to be applied for the reservation."""


@define
class SoftwareTrial(AttrsJSONDecodeMixin):
    """
    Represent the software free trial period definition.

    It's part of :class:`~cloudpub.models.ms_azure.PriceAndAvailabilityPlan`.

    `Schema definition for SoftwareTrial <https://schema.mp.microsoft.com/schema/price-and-availability-trail/2022-03-01-preview2>`_
    """  # noqa E501

    type: str
    """
    The time type of trial.

    Expected value (one of):

    * ``day``
    * ``week``
    * ``month``
    * ``year``
    """

    value: int
    """The amount of time for the trial."""


@define
class PriceAndAvailabilityPlan(AzurePlanLinkedResource):
    """
    Represent the price and availability of a plan.

    `Schema definition for PriceAndAvailabilityPlan <https://schema.mp.microsoft.com/schema/price-and-availability-plan/2022-03-01-preview2>`_
    """  # noqa E501

    visibility: str
    """
    The the plan visibility on marketplace.

    Expected value (one of):

    * ``visible``
    * ``hidden``
    """

    billing_tag: Optional[str] = field(
        validator=optional(instance_of(str)), metadata={"alias": "billingTag", "hide_unset": True}
    )
    """The billing tag."""

    markets: List[str]
    """
    The countries which the plan is available.

    It expects the lowercase country code (e.g.: ``us``).
    """

    pricing: Pricing = field(converter=Pricing.from_json, on_setattr=NO_OP)  # type: ignore
    """The plan's :class:`~cloudpub.models.ms_azure.Pricing`."""

    trial: Optional[SoftwareTrial] = field(
        converter=SoftwareTrial.from_json, on_setattr=NO_OP  # type: ignore
    )
    """When set it allows customers to have a free trial during a certain period of time."""

    customer_markets: Optional[str] = field(
        validator=optional(instance_of(str)),
        metadata={"alias": "customerMarkets", "hide_unset": True},
    )
    """
    The market type.

    Expected value when set (one of):

    * ``customMarkets``
    * ``allMarkets``
    * ``allTaxRemittedMarkets``
    """

    software_reservation: List[SoftwareReservation] = field(
        metadata={"alias": "softwareReservation"},
        converter=lambda x: [SoftwareReservation.from_json(r) for r in x] if x else [],
        on_setattr=NO_OP,
    )
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
        converter=lambda x: [Audience.from_json(a) for a in x] if x else [],
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

    `Schema definition for PriceAndAvailabilityOffer <https://schema.mp.microsoft.com/schema/price-and-availability-offer/2022-03-01-preview2>`_
    """  # noqa E501

    preview_audiences: List[Audience] = field(
        metadata={"alias": "previewAudiences"},
        converter=lambda x: [Audience.from_json(a) for a in x] if x else [],
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

    friendly_name: Optional[str] = field(metadata={"alias": "friendlyName", "hide_unset": True})
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

    security_type: Optional[List[str]] = field(
        default=None,
        validator=optional(
            deep_iterable(member_validator=instance_of(str), iterable_validator=instance_of(list))
        ),
        metadata={"alias": "securityType", "hide_unset": True},
    )
    """The security type for Gen2 images: trusted launch and/or confidential."""


@define
class OSDiskURI(AttrsJSONDecodeMixin):
    """Represent an Operating System Disk URI."""

    uri: str = field(validator=instance_of(str))
    """The full SAS URI for the Virtual Machine Image."""


class DataDisk(AttrsJSONDecodeMixin):
    """
    Define a data disk.

    It's part of :class:`~cloudpub.models.ms_azure.VMImageSource`.

    `Schema definition for DataDisk <https://schema.mp.microsoft.com/schema/virtual-machine-data-disk/2022-03-01-preview2>`_
    """  # noqa: E501

    lun_number: int = field(metadata={"alias": "lunNumber"})
    """The LUN number for the data disk (max = 15)."""

    uri: str
    """The data disk URI."""


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

    data_disks: List[DataDisk] = field(
        metadata={"alias": "dataDisks"},
        converter=lambda x: [DataDisk.from_json(a) for a in x] if x else [],
    )
    """The list of data disks to mount within the OS."""

    @source_type.validator
    def _validate_source_type(self, attribute: Attribute, value: Any):
        if value != "sasUri" and value != "sharedImageGallery":
            raise ValueError(
                f"Got an unexpected value for \"{attribute.name}\": \"{value}\"\n"
                "Expected: \"sasUri\" or \"sharedImageGallery\"."
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
        converter=lambda x: [VMImageDefinition.from_json(a) for a in x] if x else [],
        on_setattr=NO_OP,
    )
    """The list of :class:`~cloudpub.models.ms_azure.VMImageDefinition` for this disk version."""

    lifecycle_state: Optional[str] = field(
        validator=optional(instance_of(str)),
        metadata={"alias": "lifecycleState", "hide_unset": True},
    )
    """
    The disk lifeclycle state.

    Expected value (one of):

    * ``generallyAvailable``
    * ``deprecated``
    * ``deleted``
    """

    deprecation_schedule: Optional[DeprecationSchedule] = field(
        metadata={"alias": "deprecationSchedule", "hide_unset": True},
        converter=DeprecationSchedule.from_json,  # type: ignore
        on_setattr=NO_OP,
    )
    """The deprecation schedule for the VM image if it's going to be deprecated."""


@define
class VMIPlanTechConfig(AzurePlanLinkedResource):
    """
    Represent the VM technical configuration of a Plan.

    `Schema definition for VMIPlanTechConfig <https://schema.mp.microsoft.com/schema/virtual-machine-plan-technical-configuration/2022-03-01-preview2>`_
    """  # noqa E501

    schema: str = field(
        validator=instance_of(str),
        metadata={
            "alias": MS_SCHEMA,
            "const": "https://schema.mp.microsoft.com/schema/virtual-machine-plan-technical-configuration/2022-03-01-preview5",  # noqa E501
        },
    )
    """
    The `resource schema`_ for Graph API.

    .. _resource schema: https://learn.microsoft.com/en-us/azure/marketplace/product-ingestion-api#resource-api-reference
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
        converter=lambda x: [VMISku.from_json(a) for a in x] if x else [], on_setattr=NO_OP
    )
    """The list of available :class:`~cloudpub.models.ms_azure.VMISku` in the plan."""

    disk_versions: List[DiskVersion] = field(
        metadata={"alias": "vmImageVersions"},
        converter=lambda x: [DiskVersion.from_json(a) for a in x] if x else [],
        on_setattr=NO_OP,
    )
    """The list of available :class:`~cloudpub.models.ms_azure.DiskVersion` in the plan."""

    base_plan_durable_id: Optional[str] = field(
        validator=optional(instance_of(str)), metadata={"alias": "basePlan", "hide_unset": True}
    )
    """
    The base plan `durable ID`_ when reusing.

    .. _durable ID: https://learn.microsoft.com/en-us/azure/marketplace/product-ingestion-api#method-2-durable-id
    """  # noqa E501

    @property
    def base_plan_id(self) -> Optional[str]:
        """
        Resolve the base plan ID from its `durable ID`_.

        .. _durable ID: https://learn.microsoft.com/en-us/azure/marketplace/product-ingestion-api#method-2-durable-id
        """  # noqa E501
        # durable ID format example:
        #   plan/62c171e9-a2e1-45ab-9af0-d17e769da954
        # what do we want:
        #   62c171e9-a2e1-45ab-9af0-d17e769da954
        if self.base_plan_durable_id:
            return self.base_plan_durable_id.split("/")[-1]
        return None


RESOURCE_MAPING = {
    "product": ProductSummary,
    "customer-leads": CustomerLeads,
    "test-drive": TestDrive,
    "plan": PlanSummary,
    "property": ProductProperty,
    "plan-listing": PlanListing,
    "listing": Listing,
    "listing-asset": ListingAsset,
    "listing-trailer": ListingTrailer,
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

    `Schema definition <https://schema.mp.microsoft.com/schema/resource-tree/2022-03-01-preview2>`_
    """  # noqa E501

    schema: str = field(validator=instance_of(str), metadata={"alias": MS_SCHEMA})
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
            MS_SCHEMA: self.schema,
            "root": self.root_id,
            "target": self.target.to_json(),
            "resources": [x.to_json() for x in self.resources],
        }
