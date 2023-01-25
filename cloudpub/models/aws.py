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
    release_notes: str = field(validator=instance_of(str), metadata={"alias": "ReleaseNotes"})


@define
class AMISource(AttrsJSONDecodeMixin):
    """Represent the Ami Source information."""

    ami_id: str = field(validator=instance_of(str), metadata={"alias": "AmiId"})
    access_role_arn: str = field(validator=instance_of(str), metadata={"alias": "AccessRoleArn"})
    username: str = field(validator=instance_of(str), metadata={"alias": "UserName"})
    operating_system_name: str = field(
        validator=instance_of(str), metadata={"alias": "OperatingSystemName"}
    )
    operating_system_version: str = field(
        validator=instance_of(str), metadata={"alias": "OperatingSystemVersion"}
    )
    scanning_port: int = field(validator=instance_of(int), metadata={"alias": "ScanningPort"})


@define
class SecurityGroup(AttrsJSONDecodeMixin):
    """Represent the security group information."""

    from_port: int = field(validator=instance_of(int), metadata={"alias": "FromPort"})
    ip_protocol: str = field(validator=instance_of(str), metadata={"alias": "IpProtocol"})
    ip_ranges: List[str] = field(
        validator=deep_iterable(
            member_validator=instance_of(str),
            iterable_validator=instance_of(list),
        ),
        metadata={"alias": "IpRanges"},
    )
    to_port: int = field(validator=instance_of(int), metadata={"alias": "ToPort"})


@define
class DeliveryOptions(AttrsJSONDecodeMixin):
    """Represent the delivery options information."""

    ami_source: AMISource = field(
        converter=AMISource.from_json,  # type: ignore
        on_setattr=NO_OP,
        metadata={"alias": "AmiSource"},
    )
    usage_instructions: str = field(
        validator=instance_of(str), metadata={"alias": "UsageInstructions"}
    )
    recommended_instance_type: str = field(
        validator=instance_of(str), metadata={"alias": "RecommendedInstanceType"}
    )
    security_groups: List[SecurityGroup] = field(
        converter=lambda x: [SecurityGroup.from_json(a) for a in x],
        on_setattr=NO_OP,
        metadata={"alias": "SecurityGroups"},
    )


@define
class VersionMapping(AttrsJSONDecodeMixin):
    """Represent the version mapping information."""

    version: Version = field(
        converter=Version.from_json, on_setattr=NO_OP, metadata={"alias": "Version"}  # type: ignore
    )
    delivery_options: DeliveryOptions = field(
        converter=DeliveryOptions.from_json,  # type: ignore
        on_setattr=NO_OP,
        metadata={"alias": "DeliveryOptions"},
    )
