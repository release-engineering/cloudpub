# SPDX-License-Identifier: GPL-3.0-or-later
import logging
from typing import List

from attrs import define, field
from attrs.setters import NO_OP
from attrs.validators import deep_iterable, instance_of

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
        converter=lambda x: [SecurityGroup.from_json(a) for a in x],
        on_setattr=NO_OP,
        metadata={"alias": "SecurityGroups"},
    )
    """Security group object"""


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
class DeliveryOptions(AttrsJSONDecodeMixin):
    """Represent the delivery options information."""

    id: str = field(metadata={"hide_unset": True, "alias": "Id"})
    """AMI Id used for overwriting a current Version in AWS"""
    details: DeliveryOptionsDetails = field(
        converter=DeliveryOptionsDetails.from_json,  # type: ignore
        on_setattr=NO_OP,
        metadata={"alias": "Details"},
    )
    """Details object for Delivery Options"""


@define
class VersionMapping(AttrsJSONDecodeMixin):
    """Represent the version mapping information."""

    version: Version = field(
        converter=Version.from_json, on_setattr=NO_OP, metadata={"alias": "Version"}  # type: ignore
    )
    """Version object."""
    delivery_options: List[DeliveryOptions] = field(
        converter=lambda x: [DeliveryOptions.from_json(a) for a in x],
        on_setattr=NO_OP,
        metadata={"alias": "DeliveryOptions"},
    )
    """Delivery Options object."""
