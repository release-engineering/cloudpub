from cloudpub.models.aws import AMISource, DeliveryOptions, SecurityGroup, Version, VersionMapping


def test_aws_resource_props(
    version_obj: Version,
    ami_obj: AMISource,
    security_group_obj: SecurityGroup,
    delivery_options_obj: DeliveryOptions,
    version_mapping_obj: VersionMapping,
) -> None:
    # Version testing
    assert version_obj.version_title == "Test-Version-Title"
    assert version_obj.release_notes == "Test notes"

    # AMI testing
    assert ami_obj.ami_id == "ffffffff-ffff-ffff-ffff-ffffffffffff"
    assert ami_obj.access_role_arn == "arn:aws:iam::000000000000:role/FakeScanning"
    assert ami_obj.username == "ec2-user"
    assert ami_obj.operating_system_name == "fake"
    assert ami_obj.operating_system_version == "Fake-9.0.3_HVM-203325325232-x86_64-2"
    assert ami_obj.scanning_port == 22

    # Security Group testing
    assert security_group_obj.from_port == 22
    assert security_group_obj.ip_protocol == "Test notes"
    assert security_group_obj.ip_ranges == ["22.22.22.22", "00.00.00.00"]
    assert security_group_obj.to_port == 22

    # Security Group testing
    assert delivery_options_obj.ami_source == ami_obj
    assert delivery_options_obj.usage_instructions == "Test notes"
    assert delivery_options_obj.recommended_instance_type == "x1.medium"
    assert delivery_options_obj.security_groups == [security_group_obj]

    # Delivery Version testing
    assert version_mapping_obj.version == version_obj
    assert version_mapping_obj.delivery_options == delivery_options_obj
