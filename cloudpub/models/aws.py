# SPDX-License-Identifier: GPL-3.0-or-later
import logging
import sys
from typing import Any, Dict, List, Optional, Union

if sys.version_info >= (3, 8):
    from typing import Literal, TypedDict  # pragma: no cover
else:
    from typing_extensions import Literal, TypedDict  # pragma: no cover

from attrs import Attribute, define, field
from attrs.setters import NO_OP
from attrs.validators import deep_iterable, ge, instance_of, optional

from cloudpub.models.common import AttrsJSONDecodeMixin

log = logging.getLogger(__name__)


@define
class Version(AttrsJSONDecodeMixin):
    """Represent the version information."""

    version_title: str = field(validator=instance_of(str), metadata={"alias": "VersionTitle"})
    """
    The title given to a version. This will display in AWS Marketplace as the name of the version.
    """

    release_notes: str = field(validator=instance_of(str), metadata={"alias": "ReleaseNotes"})
    """
    The release notes for the version update. This will provide what was updated in the version.
    Usually is a link to access.redhat.com for this version.
    """


@define
class AMISource(AttrsJSONDecodeMixin):
    """Represent the Ami Source information."""

    ami_id: str = field(validator=instance_of(str), metadata={"alias": "AmiId"})
    """The Ami Id associated with the version update."""

    access_role_arn: str = field(validator=instance_of(str), metadata={"alias": "AccessRoleArn"})
    """The role to use to access to AMI."""

    username: str = field(validator=instance_of(str), metadata={"alias": "UserName"})
    """The username used to login to the AMI. (Usually set to ec2-user)"""

    operating_system_name: str = field(
        validator=instance_of(str), metadata={"alias": "OperatingSystemName"}
    )
    """The name of the Operating System used by the AMI."""

    operating_system_version: str = field(
        validator=instance_of(str), metadata={"alias": "OperatingSystemVersion"}
    )

    """The version of the Operating System used by the AMI."""

    scanning_port: int = field(validator=instance_of(int), metadata={"alias": "ScanningPort"})
    """AMI scanning port, used when importing the AMI into AWS Marketplace to validate the AMI."""


@define
class SecurityGroup(AttrsJSONDecodeMixin):
    """Represent the security group information."""

    from_port: int = field(validator=instance_of(int), metadata={"alias": "FromPort"})
    """
    If the protocol is TCP or UDP, this is the start of the port range.
    If the protocol is ICMP or ICMPv6, this is the type number.
    A value of -1 indicates all ICMP/ICMPv6 types. If you specify all ICMP/ICMPv6 types,
    you must specify all ICMP/ICMPv6 codes.
    """

    ip_protocol: str = field(validator=instance_of(str), metadata={"alias": "IpProtocol"})

    """The IP protocol name ( tcp , udp , icmp , icmpv6 )."""
    ip_ranges: List[str] = field(
        validator=deep_iterable(
            member_validator=instance_of(str),
            iterable_validator=instance_of(list),
        ),
        metadata={"alias": "IpRanges"},
    )
    """The IPv4 ranges."""

    to_port: int = field(validator=instance_of(int), metadata={"alias": "ToPort"})
    """
    If the protocol is TCP or UDP, this is the end of the port range.
    If the protocol is ICMP or ICMPv6, this is the type number.
    A value of -1 indicates all ICMP/ICMPv6 types. If you specify all ICMP/ICMPv6 types,
    you must specify all ICMP/ICMPv6 codes.
    """


@define
class SecurityGroupRecommendations(AttrsJSONDecodeMixin):
    """Represent the security group information for recommendations."""

    from_port: int = field(validator=instance_of(int), metadata={"alias": "FromPort"})
    """
    If the protocol is TCP or UDP, this is the start of the port range.
    If the protocol is ICMP or ICMPv6, this is the type number.
    A value of -1 indicates all ICMP/ICMPv6 types. If you specify all ICMP/ICMPv6 types,
    you must specify all ICMP/ICMPv6 codes.
    """

    ip_protocol: str = field(validator=instance_of(str), metadata={"alias": "Protocol"})

    """The IP protocol name ( tcp , udp , icmp , icmpv6 )."""
    cidr_ips: List[str] = field(
        validator=deep_iterable(
            member_validator=instance_of(str),
            iterable_validator=instance_of(list),
        ),
        metadata={"alias": "CidrIps"},
    )
    """The IPv4 ranges."""

    to_port: int = field(validator=instance_of(int), metadata={"alias": "ToPort"})
    """
    If the protocol is TCP or UDP, this is the end of the port range.
    If the protocol is ICMP or ICMPv6, this is the type number.
    A value of -1 indicates all ICMP/ICMPv6 types. If you specify all ICMP/ICMPv6 types,
    you must specify all ICMP/ICMPv6 codes.
    """


@define
class AccessEndpointUrl(AttrsJSONDecodeMixin):
    """Represent the access endpoint url information."""

    port: int = field(validator=instance_of(int), metadata={"alias": "Port"})
    """Port to access the endpoint URL."""

    protocol: str = field(validator=instance_of(str), metadata={"alias": "Protocol"})
    """Protocol to access the endpoint URL (http, https)."""


@define
class AmiDeliveryOptionsDetails(AttrsJSONDecodeMixin):
    """Represent the delivery options details information."""

    ami_source: AMISource = field(
        converter=AMISource.from_json,  # type: ignore
        on_setattr=NO_OP,
        metadata={"alias": "AmiSource"},
    )
    """AMI Source object."""

    usage_instructions: str = field(
        validator=instance_of(str), metadata={"alias": "UsageInstructions"}
    )
    """Instructions on the usage of the AMI instance."""

    recommended_instance_type: str = field(
        validator=instance_of(str), metadata={"alias": "RecommendedInstanceType"}
    )

    """Recommended instance type of the AMI. IE m5.medium"""

    security_groups: List[SecurityGroup] = field(
        converter=lambda x: [SecurityGroup.from_json(a) for a in x] if x else [],
        on_setattr=NO_OP,
        metadata={"alias": "SecurityGroups"},
    )
    """Security group object"""

    access_endpoint_url: AccessEndpointUrl = field(
        converter=AccessEndpointUrl.from_json,  # type: ignore
        on_setattr=NO_OP,
        metadata={"alias": "AccessEndpointUrl", "hide_unset": True},
    )
    """Access endpoint url object"""


@define
class DeliveryOptionsDetails(AttrsJSONDecodeMixin):
    """Represent the ami delivery options information."""

    ami_delivery_options_details: AmiDeliveryOptionsDetails = field(
        converter=AmiDeliveryOptionsDetails.from_json,  # type: ignore
        on_setattr=NO_OP,
        metadata={"alias": "AmiDeliveryOptionDetails"},
    )
    """Ami Delivery Options details"""


@define
class DeliveryInstructionsAccess(AttrsJSONDecodeMixin):
    """Represent a single element of access from class :class:`~cloudpub.models.aws.DeliveryOptionsInstructions`."""  # noqa: E501

    type: str = field(metadata={"hide_unset": True, "alias": "Type"})
    """Type instructions for access"""

    port: int = field(validator=[instance_of(int), ge(0)], metadata={"alias": "Port"})
    """Port used for AMI access"""

    protocol: str = field(metadata={"hide_unset": True, "alias": "Protocol"})
    """Protocol to use for AMI access"""


@define
class DeliveryOptionsInstructions(AttrsJSONDecodeMixin):
    """Represent a single element of instructions from class :class:`~cloudpub.models.aws.DeliveryOption`."""  # noqa: E501

    usage: str = field(metadata={"hide_unset": True, "alias": "Usage"})
    """AMI usage instructions"""

    access: Optional[DeliveryInstructionsAccess] = field(
        converter=DeliveryInstructionsAccess.from_json,  # type: ignore
        on_setattr=NO_OP,
        metadata={"hide_unset": True, "alias": "Access"},
    )
    """Instructions on how to access this AMI"""


@define
class DeliveryOptionsRecommendations(AttrsJSONDecodeMixin):
    """Represent a single element of recommendations from class :class:`~cloudpub.models.aws.DeliveryOption`."""  # noqa: E501

    instance_type: str = field(metadata={"hide_unset": True, "alias": "InstanceType"})
    """Instance type for this recommendation"""

    security_groups: List[SecurityGroupRecommendations] = field(
        converter=lambda x: [SecurityGroupRecommendations.from_json(a) for a in x] if x else [],
        on_setattr=NO_OP,
        metadata={"alias": "SecurityGroups"},
    )
    """Security groups to use with this AMI."""


@define
class DeliveryOption(AttrsJSONDecodeMixin):
    """Represent the delivery option information."""

    id: str = field(metadata={"hide_unset": True, "alias": "Id"})
    """AMI Id used for overwriting a current Version in AWS"""

    type: str = field(metadata={"hide_unset": True, "alias": "Type"})
    """Type of delivery option

    Expected value:

    * ``AmazonMachineImage``
    """

    source_id: str = field(metadata={"hide_unset": True, "alias": "SourceId"})
    """Source Id for the delivery option"""

    short_description: str = field(metadata={"hide_unset": True, "alias": "ShortDescription"})
    """Short description of the delivery options"""

    long_description: Optional[str] = field(
        validator=optional(instance_of(str)),
        metadata={"alias": "LongDescription", "hide_unset": True},
    )
    """Long description of Delivery option. (optional)"""

    instructions: DeliveryOptionsInstructions = field(
        converter=DeliveryOptionsInstructions.from_json,  # type: ignore
        on_setattr=NO_OP,
        metadata={"alias": "Instructions", "hide_unset": True},
    )
    """Instructions on usage of this AMI"""

    recommendations: DeliveryOptionsRecommendations = field(
        converter=DeliveryOptionsRecommendations.from_json,  # type: ignore
        on_setattr=NO_OP,
        metadata={"alias": "Recommendations", "hide_unset": True},
    )
    """Recommendations when using this AMI"""

    visibility: Optional[str] = field(
        validator=optional(instance_of(str)), metadata={"alias": "Visibility", "hide_unset": True}
    )
    """Define the visilibity of the current product within AWS marketplace.

    Expected value (one of):

    * ``Public``
    * ``Limited``
    * ``Restricted``
    """

    details: DeliveryOptionsDetails = field(
        converter=DeliveryOptionsDetails.from_json,  # type: ignore
        on_setattr=NO_OP,
        metadata={"alias": "Details"},
    )
    """Details object for Delivery Options"""

    title: str = field(metadata={"hide_unset": True, "alias": "Title"})
    """Title for this DeliveryOption"""

    ami_alias: Optional[str] = field(
        validator=optional(instance_of(str)), metadata={"alias": "AmiAlias", "hide_unset": True}
    )
    """Alias for the ami"""


@define
class VersionMapping(AttrsJSONDecodeMixin):
    """Represent the version mapping information."""

    version: Version = field(
        converter=Version.from_json, on_setattr=NO_OP, metadata={"alias": "Version"}  # type: ignore
    )
    """Version object."""

    delivery_options: List[DeliveryOption] = field(
        converter=lambda x: [DeliveryOption.from_json(a) for a in x] if x else [],
        on_setattr=NO_OP,
        metadata={"alias": "DeliveryOptions"},
    )
    """Delivery Options object."""


#
# Product Detail Response Data
#


@define
class ProductDetailDescription(AttrsJSONDecodeMixin):
    """Represent the "Details" section of the :class:`~cloudpub.models.aws.ProductDetailResponse`."""  # noqa: E501

    replacement_product_id: Optional[str] = field(
        validator=optional(instance_of(str)),
        metadata={"alias": "ReplacementProductId", "hide_unset": True},
    )
    """The ID of the product which is replacing the current one, if applicable."""

    highlights: List[str] = field(
        validator=deep_iterable(
            member_validator=instance_of(str),
            iterable_validator=instance_of(list),
        ),
        metadata={"alias": "Highlights"},
    )
    """List of highlights of the current product."""

    product_code: str = field(validator=instance_of(str), metadata={"alias": "ProductCode"})
    """A unique code to identify the product within AWS."""

    search_keywords: List[str] = field(
        validator=deep_iterable(
            member_validator=instance_of(str),
            iterable_validator=instance_of(list),
        ),
        metadata={"alias": "SearchKeywords"},
    )

    product_title: str = field(validator=instance_of(str), metadata={"alias": "ProductTitle"})
    """The product title to be displayed in the marketplace"""

    short_description: str = field(
        validator=instance_of(str), metadata={"alias": "ShortDescription"}
    )
    """The summary of the product."""

    long_description: str = field(validator=instance_of(str), metadata={"alias": "LongDescription"})
    """A detailed description of the product."""

    manufacturer: str = field(validator=instance_of(str), metadata={"alias": "Manufacturer"})
    """The product's manufacturer name."""

    product_state: str = field(validator=instance_of(str), metadata={"alias": "ProductState"})
    """The state of the current product.

    Expected value (one of):

    * ``Available``
    * ``Limited``
    """

    visibility: str = field(validator=instance_of(str), metadata={"alias": "Visibility"})
    """Define the visilibity of the current product within AWS marketplace.

    Expected value (one of):

    * ``Public``
    * ``Limited``
    * ``Restricted``
    """

    associated_products: Optional[str] = field(
        validator=optional(instance_of(str)),
        metadata={"alias": "AssociatedProducts", "hide_unset": True},
    )
    """Associated products within the current one."""
    # we could see just null

    sku: Optional[str] = field(
        validator=optional(instance_of(str)), metadata={"alias": "Sku", "hide_unset": True}
    )
    """The SKUs for the current product."""

    categories: List[str] = field(
        validator=deep_iterable(
            member_validator=instance_of(str),
            iterable_validator=instance_of(list),
        ),
        metadata={"alias": "Categories"},
    )
    """The marketplace categories for the current product."""


@define
class OperatingSystem(AttrsJSONDecodeMixin):
    """Represent the operating_system attribute of :class:`~cloudpub.models.aws.ProductVersionsVirtualizationSource`."""  # noqa: E501

    name: str = field(validator=instance_of(str), metadata={"alias": "Name"})
    """The OS name."""

    version: str = field(validator=instance_of(str), metadata={"alias": "Version"})
    """The OS version."""

    username: str = field(validator=instance_of(str), metadata={"alias": "Username"})
    """The main username to log in into the OS."""

    scanning_port: int = field(
        validator=[instance_of(int), ge(0)], metadata={"alias": "ScanningPort"}
    )
    """The main port used to remotely access the OS."""


@define
class SourcesCompatibility(AttrsJSONDecodeMixin):
    """Represent the compatibility attribute of :class:`~cloudpub.models.aws.ProductVersionsVirtualizationSource`."""  # noqa: E501

    available_instance_types: List[str] = field(
        validator=deep_iterable(
            member_validator=instance_of(str),
            iterable_validator=instance_of(list),
        ),
        metadata={"alias": "AvailableInstanceTypes"},
    )
    """The instance types supported by the current VM."""

    restricted_instance_types: List[str] = field(
        validator=deep_iterable(
            member_validator=instance_of(str),
            iterable_validator=instance_of(list),
        ),
        metadata={"alias": "RestrictedInstanceTypes"},
    )
    """The restricted instance types for the current VM."""


@define
class ProductVersionsBase(AttrsJSONDecodeMixin):
    """The base definition for product versions."""

    source_id: str = field(validator=instance_of(str), metadata={"alias": "Id"})
    """The ID for the current product version."""

    type: str = field(metadata={"alias": "Type"})
    """The product version type.

    Expected value (one of):

    * ``AmazonMachineImage``
    * ``CloudFormationTemplate``
    """

    @type.validator
    def valid_type(self, attribute: Attribute, value: Any) -> None:
        """Ensure the attribute ``type`` has an expected value."""
        valid_values = ["AmazonMachineImage", "CloudFormationTemplate"]
        if value not in valid_values:
            raise ValueError(f"Invalid value for {attribute.name}. Expected: {valid_values}")


@define
class ProductVersionsVirtualizationSource(ProductVersionsBase):
    """Represent one of the supported source types from :class:`~cloudpub.models.aws.ProductVersionsResponse`."""  # noqa: E501

    image: str = field(validator=instance_of(str), metadata={"alias": "Image"})
    """The AMI for the virtualization source."""

    architecture: str = field(validator=instance_of(str), metadata={"alias": "Architecture"})
    """The VM architecture for the virtualization source."""

    virtualization_type: str = field(
        validator=instance_of(str), metadata={"alias": "VirtualizationType"}
    )
    """The virtualization type.

    Expected value (one of):

    * ``hvm``
    * ``pv``
    """

    operating_system: OperatingSystem = field(
        converter=OperatingSystem.from_json,  # type: ignore
        on_setattr=NO_OP,
        metadata={"alias": "OperatingSystem"},
    )
    """The operating system for the current version."""

    compatibility: SourcesCompatibility = field(
        converter=SourcesCompatibility.from_json,  # type: ignore
        on_setattr=NO_OP,
        metadata={"alias": "Compatibility"},
    )
    """The source compatibilities for the current version."""


@define
class ProductVersionsCloudFormationSource(ProductVersionsBase):
    """Represent one of the supported source types from :class:`~cloudpub.models.aws.ProductVersionsResponse`."""  # noqa: E501

    nested_documents: Optional[List[str]] = field(
        metadata={"alias": "NestedDocuments", "hide_unset": True}
    )
    """List of nested documents for the current CloudFormation source."""

    consumed_sources: List[str] = field(
        validator=deep_iterable(
            member_validator=instance_of(str),
            iterable_validator=instance_of(list),
        ),
        metadata={"alias": "ConsumedSources"},
    )
    """The consumed sources for the current CloudFormation source."""

    aws_dependent_services: List[str] = field(
        validator=deep_iterable(
            member_validator=instance_of(str),
            iterable_validator=instance_of(list),
        ),
        metadata={"alias": "AWSDependentServices"},
    )
    """The dependent services for the current CloudFormation source."""

    architecture_diagram: Optional[str] = field(
        validator=optional(instance_of(str)),
        metadata={"alias": "ArchitectureDiagram", "hide_unset": True},
    )
    """The architecture diagram of the current CloudFormation source."""

    template: Optional[str] = field(
        validator=optional(instance_of(str)), metadata={"alias": "Template", "hide_unset": True}
    )
    """The CloudFormation's template."""


def convert_source(
    x: Any,
) -> Union[ProductVersionsVirtualizationSource, ProductVersionsCloudFormationSource]:
    """Convert the incoming JSON into one of the suppported source element from :class:`~ProductVersionsResponse`."""  # noqa: E501
    try:
        return ProductVersionsVirtualizationSource.from_json(x)
    except TypeError:
        pass
    return ProductVersionsCloudFormationSource.from_json(x)


@define
class ProductVersionsResponse(AttrsJSONDecodeMixin):
    """Represent the "Versions" section of the :class:`~cloudpub.models.aws.ProductDetailResponse`."""  # noqa: E501

    version_id: str = field(validator=instance_of(str), metadata={"alias": "Id"})
    """The ID of the current version."""

    release_notes: Optional[str] = field(
        validator=optional(instance_of(str)), metadata={"alias": "ReleaseNotes", "hide_unset": True}
    )
    """The version's release notes."""

    upgrade_instructions: Optional[str] = field(
        validator=optional(instance_of(str)),
        metadata={"alias": "UpgradeInstructions", "hide_unset": True},
    )
    """The instructions on how to upgrade from previous versions to the current one."""

    version_title: Optional[str] = field(
        validator=optional(instance_of(str)), metadata={"alias": "VersionTitle", "hide_unset": True}
    )
    """The name of the current version."""

    creation_date: Optional[str] = field(
        validator=optional(instance_of(str)), metadata={"alias": "CreationDate", "hide_unset": True}
    )
    """The version's creation date."""

    sources: List[
        Union[ProductVersionsVirtualizationSource, ProductVersionsCloudFormationSource]
    ] = field(
        converter=lambda x: [convert_source(a) for a in x] if x else [],
        on_setattr=NO_OP,
        metadata={"alias": "Sources"},
    )
    """The linked sources for the current version."""

    delivery_options: List[DeliveryOption] = field(
        converter=lambda x: [DeliveryOption.from_json(a) for a in x] if x else [],
        on_setattr=NO_OP,
        metadata={"alias": "DeliveryOptions"},
    )
    """The delivery options for the current version."""


@define
class BaseResources(AttrsJSONDecodeMixin):
    """Common base class for extra resources.

    Child classes:

    * :class:`~AdditionalResources`
    * :class:`~PromoResourcesVideo`

    """

    type: Literal["Link"] = field(metadata={"alias": "Type"})
    """The extra resource type."""

    url: str = field(validator=instance_of(str), metadata={"alias": "Url"})
    """The extra resource URL."""


@define
class AdditionalResources(BaseResources):
    """Represent a single element of additional_resources from class :class:`~cloudpub.models.aws.PromotionalResources`."""  # noqa: E501

    text: str = field(validator=instance_of(str), metadata={"alias": "Text"})
    """The additional resource text."""


@define
class PromoResourcesVideo(BaseResources):
    """Represent a single element of videos from class :class:`~cloudpub.models.aws.PromotionalResources`."""  # noqa: E501

    title: str = field(metadata={"alias": "Title"})
    """The promotional video title."""


@define
class PromotionalResources(AttrsJSONDecodeMixin):
    """Represent the "PromotionalResources" section of the :class:`~cloudpub.models.aws.ProductDetailResponse`."""  # noqa: E501

    promotional_media: Optional[str] = field(
        validator=optional(instance_of(str)),
        metadata={"alias": "PromotionalMedia", "hide_unset": True},
    )
    """The product's promotional media."""

    logo_url: str = field(validator=instance_of(str), metadata={"alias": "LogoUrl"})
    """The URL for the product's logo."""

    additional_resources: List[AdditionalResources] = field(
        converter=lambda x: [AdditionalResources.from_json(a) for a in x] if x else [],
        on_setattr=NO_OP,
        metadata={"alias": "AdditionalResources"},
    )
    """The product's additional resources."""

    videos: List[PromoResourcesVideo] = field(
        converter=lambda x: [PromoResourcesVideo.from_json(a) for a in x] if x else [],
        on_setattr=NO_OP,
        metadata={"alias": "Videos"},
    )
    """The promotional/demonstration videos about the product."""


@define
class Dimensions(AttrsJSONDecodeMixin):
    """Represent a single element of dimensions from :class:`~cloudpub.models.aws.ProductDetailResponse`."""  # noqa: E501

    types: List[str] = field(
        validator=deep_iterable(
            member_validator=instance_of(str),
            iterable_validator=instance_of(list),
        ),
        metadata={"alias": "Types"},
    )
    """The dimensions types."""

    description: Optional[str] = field(
        validator=optional(instance_of(str)), metadata={"alias": "Description", "hide_unset": True}
    )
    """The dimensions description."""

    unit: str = field(validator=instance_of(str), metadata={"alias": "Unit"})
    """The unit measuring the dimensions consumption unit."""

    key: str = field(validator=instance_of(str), metadata={"alias": "Key"})
    """The dimension's key."""

    name: str = field(validator=instance_of(str), metadata={"alias": "Name"})
    """The dimension's name."""


@define
class SupportInformation(AttrsJSONDecodeMixin):
    """Represent the support_information attribute of :class:`~cloudpub.models.aws.ProductDetailResponse`."""  # noqa: E501

    description: Optional[str] = field(
        validator=optional(instance_of(str)), metadata={"alias": "Description", "hide_unset": True}
    )
    """The description of the provided support for the product."""

    resources: Optional[List[str]] = field(
        validator=optional(
            deep_iterable(member_validator=instance_of(str), iterable_validator=instance_of(list))
        ),
        metadata={"alias": "Resources", "hide_unset": True},
    )
    """Additional resources for the provided support."""


@define
class RegionAvailability(AttrsJSONDecodeMixin):
    """Represent the region_availability attribute of :class:`~cloudpub.models.aws.ProductDetailResponse`."""  # noqa: E501

    restrict: List[str] = field(
        validator=deep_iterable(
            member_validator=instance_of(str),
            iterable_validator=instance_of(list),
        ),
        metadata={"alias": "Restrict"},
    )
    """The list of restricted regions for the curent product."""

    regions: List[str] = field(
        validator=deep_iterable(
            member_validator=instance_of(str),
            iterable_validator=instance_of(list),
        ),
        metadata={"alias": "Regions"},
    )
    """The available regions for the current product."""

    future_region_support: Optional[str] = field(
        validator=optional(instance_of(str)),
        metadata={"alias": "FutureRegionSupport", "hide_unset": True},
    )
    """The list of future avaialble regions for the current product."""


@define
class PositiveTargeting(AttrsJSONDecodeMixin):
    """Represent the positive_targeting attribute of :class:`~cloudpub.models.aws.TargetingDetail`."""  # noqa: E501

    buyer_accounts: Optional[List[str]] = field(
        validator=optional(
            deep_iterable(member_validator=instance_of(str), iterable_validator=instance_of(list))
        ),
        metadata={"alias": "BuyerAccounts", "hide_unset": True},
    )
    """List of buyer accounts."""


@define
class TargetingDetail(AttrsJSONDecodeMixin):
    """Represent the targeting attribute of :class:`~cloudpub.models.aws.ProductDetailResponse`."""

    positive_targeting: PositiveTargeting = field(
        converter=PositiveTargeting.from_json,  # type: ignore
        on_setattr=NO_OP,
        metadata={"alias": "PositiveTargeting"},
    )
    """The positive targeting object for the ``TargetingDetail``."""


@define
class ProductDetailResponse(AttrsJSONDecodeMixin):
    """Represent the parsed elements from "Details" of :class:`~cloudpub.models.aws.DescribeEntityResponse`."""  # noqa: E501

    versions: List[ProductVersionsResponse] = field(
        converter=lambda x: [ProductVersionsResponse.from_json(a) for a in x] if x else [],
        on_setattr=NO_OP,
        metadata={"alias": "Versions"},
    )
    """The product's versions list."""

    description: ProductDetailDescription = field(
        converter=ProductDetailDescription.from_json,  # type: ignore
        on_setattr=NO_OP,
        metadata={"alias": "Description"},
    )
    """The product's description."""

    promotional_resources: PromotionalResources = field(
        converter=PromotionalResources.from_json,  # type: ignore
        on_setattr=NO_OP,
        metadata={"alias": "PromotionalResources"},
    )
    """The product's promotional resources."""

    dimensions: List[Dimensions] = field(
        converter=lambda x: [Dimensions.from_json(a) for a in x] if x else [],
        on_setattr=NO_OP,
        metadata={"alias": "Dimensions"},
    )
    """The product's dimensions."""

    support_information: SupportInformation = field(
        converter=SupportInformation.from_json,  # type: ignore
        on_setattr=NO_OP,
        metadata={"alias": "SupportInformation"},
    )
    """The product's support information."""

    region_availability: RegionAvailability = field(
        converter=RegionAvailability.from_json,  # type: ignore
        on_setattr=NO_OP,
        metadata={"alias": "RegionAvailability"},
    )
    """The product's availability on AWS regions."""

    targeting: TargetingDetail = field(
        converter=TargetingDetail.from_json,  # type: ignore
        on_setattr=NO_OP,
        metadata={"alias": "Targeting"},
    )
    """The product's targeting."""

    compatibility: Optional[SourcesCompatibility] = field(
        converter=SourcesCompatibility.from_json,  # type: ignore
        on_setattr=NO_OP,
        metadata={"alias": "Compatibility", "hide_unset": True},
    )
    """The product's compatibility."""


@define
class ResponseMetadata(AttrsJSONDecodeMixin):
    """Represent the describe_entity HTTPS response metadata.

    It's part of :class:`~cloudpub.models.aws.DescribeEntityResponse`.
    """

    request_id: str = field(metadata={"alias": "RequestId"})
    """The UUID of the request to AWS."""

    status_code: int = field(metadata={"alias": "HTTPStatusCode"})
    """The HTTP status code returned in the response."""

    http_headers: Dict[str, str] = field(metadata={"alias": "HTTPHeaders"})
    """The HTTP readers returned in the response.

    Fields:

    * ``date``: The HTTP response date (e.g.: "Fri, 25 Aug 2023 20:50:06 GMT")
    * ``content-type``: The HTTP content type (e.g: "application/json")
    # ``content-length``: The HTTP body length (e.g.: "3029")
    # ``connection``: The HTTP connection definition (e.g.: "keep-alive")
    # ``x-amzn-requestid``: The UUID of the request ID to AWS.
    """

    retry_attemps: int = field(metadata={"alias": "RetryAttempts"})


@define
class DescribeEntityResponse(AttrsJSONDecodeMixin):
    """Represent the response of ``MarketplaceCatalog.Client.describe_entity``.

    `Documentation <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/marketplace-catalog/client/describe_entity.html>`_
    """  # noqa: E501

    type: str = field(validator=instance_of(str), metadata={"alias": "EntityType"})
    """The named type of the entity, in the format of ``EntityType@Version``."""

    identifier: str = field(validator=instance_of(str), metadata={"alias": "EntityIdentifier"})
    """The identifier of the entity, in the format of ``EntityId@RevisionId``."""

    arn: str = field(validator=instance_of(str), metadata={"alias": "EntityArn"})
    """The ARN associated to the unique identifier for the entity referenced in this request."""

    last_modified_date: str = field(
        validator=instance_of(str), metadata={"alias": "LastModifiedDate"}
    )
    """The last modified date of the entity, in ISO 8601 format (2018-02-27T13:45:22Z)."""

    details: Optional[str] = field(
        validator=optional(instance_of(str)), metadata={"alias": "Details", "hide_unset": True}
    )
    """This stringified JSON object includes the details of the entity."""

    details_document: ProductDetailResponse = field(
        converter=ProductDetailResponse.from_json,  # type: ignore
        on_setattr=NO_OP,
        metadata={"alias": "DetailsDocument"},
    )
    """This json object of the details of the entity."""

    meta: ResponseMetadata = field(
        converter=ResponseMetadata.from_json,  # type: ignore
        on_setattr=NO_OP,
        metadata={"alias": "ResponseMetadata"},
    )
    """The describe_entity response's metadata."""


#
# List entities Response Data
#


@define
class EntitySummary(AttrsJSONDecodeMixin):
    """Represent a single element of attribute "entity_summary_list" of :class:`~cloudpub.models.aws.ListEntitiesResponse`."""  # noqa: E501

    name: str = field(validator=instance_of(str), metadata={"alias": "Name"})
    """The name for the entity. This value is not unique. It is defined by the seller."""

    entity_type: str = field(validator=instance_of(str), metadata={"alias": "EntityType"})
    """The type of the entity."""

    entity_id: str = field(validator=instance_of(str), metadata={"alias": "EntityId"})
    """The unique identifier for the entity."""

    entity_arn: str = field(validator=instance_of(str), metadata={"alias": "EntityArn"})
    """The ARN associated with the unique identifier for the entity."""

    last_modified_date: str = field(
        validator=instance_of(str), metadata={"alias": "LastModifiedDate"}
    )
    """The last time the entity was published, using ISO 8601 format (2018-02-27T13:45:22Z)."""

    visibility: str = field(validator=instance_of(str), metadata={"alias": "Visibility"})
    """The visibility status of the entity to buyers.

    This value can be `Public` (everyone can view the entity),
    `Limited` (the entity is visible to limited accounts only),
    or `Restricted` (the entity was published and then unpublished and only
    existing buyers can view it).
    """


@define
class ListEntitiesResponse(AttrsJSONDecodeMixin):
    """Represent the response of ``MarketplaceCatalog.Client.list_entities``.

    `Documentation <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/marketplace-catalog/client/list_entities.html>`_
    """  # noqa: E501

    entity_summary_list: List[EntitySummary] = field(
        converter=lambda x: [EntitySummary.from_json(a) for a in x] if x else [],  # type: ignore
        on_setattr=NO_OP,
        metadata={"alias": "EntitySummaryList"},
    )
    """Array of EntitySummary objects."""

    next_token: Optional[str] = field(
        validator=optional(instance_of(str)), metadata={"alias": "NextToken", "hide_unset": True}
    )
    """The value of the next token if it exists. Null if there is no more result."""


#
# ChangeSet Response Data
#
@define
class ErrorDetail(AttrsJSONDecodeMixin):
    """Represent the details of a single error."""

    code: str = field(validator=instance_of(str), metadata={"alias": "ErrorCode"})
    """The error code that identifies the type of error."""

    message: str = field(validator=instance_of(str), metadata={"alias": "ErrorMessage"})
    """The message for the error."""


@define
class BaseEntity(AttrsJSONDecodeMixin):
    """Represent an in change entity on AWS."""

    type: str = field(validator=instance_of(str), metadata={"alias": "Type"})
    """The named type of the entity, in the format of ``EntityType@Version``."""

    identifier: str = field(validator=instance_of(str), metadata={"alias": "Identifier"})
    """The identifier of the entity, in the format of ``EntityId@RevisionId``."""


@define
class ChangeSummary(AttrsJSONDecodeMixin):
    """Represent a single element of the "change_set" attribute of :class:`~cloudpub.models.aws.DescribeChangeSetReponse`."""  # noqa: E501

    change_type: str = field(validator=instance_of(str), metadata={"alias": "ChangeType"})
    """The type of the change."""

    entity: BaseEntity = field(
        converter=BaseEntity.from_json,  # type: ignore
        on_setattr=NO_OP,
        metadata={"alias": "Entity"},
    )
    """The entity to be changed."""

    details: str = field(validator=instance_of(str), metadata={"alias": "Details"})
    """This object contains details specific to the change type of the requested change."""

    error_details: List[ErrorDetail] = field(
        converter=lambda x: [ErrorDetail.from_json(a) for a in x] if x else [],  # type: ignore
        on_setattr=NO_OP,
        metadata={"alias": "ErrorDetailList"},
    )
    """An array of ``ErrorDetail`` objects associated with the change."""

    name: Optional[str] = field(
        validator=optional(instance_of(str)), metadata={"alias": "ChangeName"}
    )
    """Optional name for the change."""


@define
class DescribeChangeSetReponse(AttrsJSONDecodeMixin):
    """Represent the response of ``MarketplaceCatalog.Client.describe_change_set``.

    `Documentation <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/marketplace-catalog/client/describe_change_set.html>`_
    """  # noqa: E501

    id: str = field(validator=instance_of(str), metadata={"alias": "ChangeSetId"})
    """The unique identifier for the change set referenced in this request."""

    arn: str = field(validator=instance_of(str), metadata={"alias": "ChangeSetArn"})
    """The ARN associated with the unique identifier for the change set referenced in this request."""  # noqa: E501

    name: Optional[str] = field(
        validator=optional(instance_of(str)),
        metadata={"alias": "ChangeSetName", "hide_unset": True},
    )

    start_time: str = field(validator=instance_of(str), metadata={"alias": "StartTime"})
    """The date and time, in ISO 8601 format (2018-02-27T13:45:22Z), the request started."""

    end_time: Optional[str] = field(
        validator=optional(instance_of(str)), metadata={"alias": "EndTime", "hide_unset": True}
    )
    """The date and time, in ISO 8601 format (2018-02-27T13:45:22Z) the request transitioned to a terminal state.

    The change cannot transition to a different state.
    Null if the request is not in a terminal state.
    """  # noqa: E501

    status: str = field(validator=instance_of(str), metadata={"alias": "Status"})
    """The status of the change request.

    Expected value (one of):

    * ``PREPARING``
    * ``APPLYING``
    * ``SUCCEEDED``
    * ``CANCELLED``
    * ``FAILED``
    """

    failure_code: Optional[str] = field(
        validator=optional(instance_of(str)), metadata={"alias": "FailureCode", "hide_unset": True}
    )
    """Returned if the change set is in ``FAILED`` status.

    Can be either ``CLIENT_ERROR``, which means that there are issues with the request
    (see the ``ErrorDetailList``), or ``SERVER_FAULT``, which means that there is a problem
    in the system, and you should retry your request.
    """

    failure_description: Optional[str] = field(
        validator=optional(instance_of(str)),
        metadata={"alias": "FailureDescription", "hide_unset": True},
    )
    """Returned if there is a failure on the change set, but that failure is not related to any of the changes in the request."""  # noqa: E501

    change_set: List[ChangeSummary] = field(
        converter=lambda x: [ChangeSummary.from_json(a) for a in x] if x else [],  # type: ignore
        on_setattr=NO_OP,
        metadata={"alias": "ChangeSet"},
    )
    """An array of ChangeSummary objects."""


@define
class ListChangeSet(AttrsJSONDecodeMixin):
    """Represent a single element of the "change_set_list" attribute of :class:`~cloudpub.models.aws.ListChangeSetsResponse`."""  # noqa: E501

    id: str = field(validator=instance_of(str), metadata={"alias": "ChangeSetId"})
    """The unique identifier for the change set referenced in this request."""

    arn: str = field(validator=instance_of(str), metadata={"alias": "ChangeSetArn"})
    """The ARN associated with the unique identifier for the change set referenced in this request."""  # noqa: E501

    name: Optional[str] = field(
        validator=optional(instance_of(str)),
        metadata={"alias": "ChangeSetName", "hide_unset": True},
    )
    """The name of the Changeset."""

    start_time: str = field(validator=instance_of(str), metadata={"alias": "StartTime"})
    """The date and time, in ISO 8601 format (2018-02-27T13:45:22Z), the request started."""

    end_time: Optional[str] = field(
        validator=optional(instance_of(str)), metadata={"alias": "EndTime", "hide_unset": True}
    )
    """The date and time, in ISO 8601 format (2018-02-27T13:45:22Z) the request transitioned to a terminal state.

    The change cannot transition to a different state.
    Null if the request is not in a terminal state.
    """  # noqa: E501

    status: str = field(validator=instance_of(str), metadata={"alias": "Status"})
    """The status of the change request.

    Expected value (one of):

    * ``PREPARING``
    * ``APPLYING``
    * ``SUCCEEDED``
    * ``CANCELLED``
    * ``FAILED``
    """

    entity_id_list: List[str] = field(
        validator=deep_iterable(
            member_validator=instance_of(str),
            iterable_validator=instance_of(list),
        ),
        metadata={"alias": "EntityIdList"},
    )
    """List of entities that this changeset affects. This should generally be length of 1."""

    failure_code: Optional[str] = field(
        validator=optional(instance_of(str)), metadata={"alias": "FailureCode", "hide_unset": True}
    )
    """Returned if the change set is in ``FAILED`` status.

    Can be either ``CLIENT_ERROR``, which means that there are issues with the request
    (see the ``ErrorDetailList``), or ``SERVER_FAULT``, which means that there is a problem
    in the system, and you should retry your request.
    """


@define
class ListChangeSetsResponse(AttrsJSONDecodeMixin):
    """Represent the response of ``MarketplaceCatalog.Client.list_change_sets``.

    `Documentation <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/marketplace-catalog/client/list_change_sets.html#MarketplaceCatalog.Client.list_change_sets>`_
    """  # noqa: E501

    meta: ResponseMetadata = field(
        converter=ResponseMetadata.from_json,  # type: ignore
        on_setattr=NO_OP,
        metadata={"alias": "ResponseMetadata"},
    )
    """The describe_entity response's metadata."""

    change_set_list: List[ListChangeSet] = field(
        converter=lambda x: [ListChangeSet.from_json(a) for a in x] if x else [],  # type: ignore
        on_setattr=NO_OP,
        metadata={"alias": "ChangeSetSummaryList"},
    )
    """An array of ChangeSummary objects."""

    next_token: Optional[str] = field(
        validator=optional(instance_of(str)), metadata={"alias": "NextToken", "hide_unset": True}
    )
    """The value of the next token if it exists. Null if there is no more result."""


#
# Custom dictionaries
#


class GroupedVersions(TypedDict):
    """Represent a simplified data for versions with fewer information."""

    delivery_options: List[DeliveryOption]
    """List of ``DeliveryOption`` objects of a specific version."""

    created_date: str
    """The creation date of a specific version."""

    ami_ids: List[str]
    """A list of AMI ids."""


class ChangeSetResponse(TypedDict):
    """Represent the response of ``MarketplaceCatalog.Client.start_change_set`` or ``MarketplaceCatalog.Client.cancel_change_set``."""  # noqa: E501

    ChangeSetId: str
    """The unique identifier for the change set referenced in this request."""

    ChangeSetArn: str
    """The ARN associated with the change set referenced in this request."""
