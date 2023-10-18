from typing import Any, Dict

import pytest

from cloudpub.models.ms_azure import (
    CustomerLeads,
    DeprecationAlternative,
    DeprecationSchedule,
    DiskVersion,
    ListingAsset,
    ListingTrailer,
    PlanListing,
    PlanSummary,
    Product,
    PublishTarget,
    VMImageSource,
    VMIPlanTechConfig,
    _mask_secret,
)


def test_serialize_deserialize_json(disk_version: Dict[str, Any]) -> None:
    """Test the (de)serialization from `AttrsJSONDecodeMixin`."""
    d = DiskVersion.from_json(disk_version)
    assert d.to_json() == disk_version


def test_serialize_product_tojson(product: Dict[str, Any], product_obj: Product) -> None:
    """Test the Product overridden method `to_json`."""
    assert product_obj.to_json() == product


def test_azure_resource_props(
    product_obj: Product,
    plan_summary_obj: PlanSummary,
    customer_leads_obj: CustomerLeads,
    plan_listing_obj: PlanListing,
    listing_asset_obj: ListingAsset,
    listing_trailer_obj: ListingTrailer,
) -> None:
    # Test the properties of AzureResource
    assert product_obj.id == "ffffffff-ffff-ffff-ffff-ffffffffffff"
    assert product_obj.resource == "product"
    assert plan_summary_obj.id == "00000000-0000-0000-0000-000000000000"
    assert plan_summary_obj.resource == "plan"

    # Test the properties of AzureProductLinkedResource
    assert customer_leads_obj.id == customer_leads_obj.product_id
    assert customer_leads_obj.product_id == "ffffffff-ffff-ffff-ffff-ffffffffffff"
    assert customer_leads_obj.resource == "customer-leads"

    # Test the properties of AzurePlanLinkedResource
    assert plan_listing_obj.plan_id == plan_summary_obj.id
    assert plan_listing_obj.resource == "plan-listing"

    # Test the properties of ListingAsset
    assert listing_asset_obj.listing_id == product_obj.id
    assert listing_asset_obj.resource == "listing-asset"

    # Test the properties of ListingTrailer
    assert listing_trailer_obj.listing_id == product_obj.id
    assert listing_trailer_obj.resource == "listing-trailer"


def test_publish_target_invalid(publish_target: Dict[str, str]) -> None:
    publish_target.update({"targetType": "foobar"})
    expected_error = (
        "Got an unexpected value for \"targetType\": \"foobar\"\n"
        "Expected: \"\\['draft', 'preview', 'live'\\]\"."
    )
    with pytest.raises(ValueError, match=expected_error):
        PublishTarget.from_json(publish_target)


def test_vm_image_source_invalid(vmimage_source: Dict[str, Any]) -> None:
    vmimage_source.update({"sourceType": "foobar"})
    expected_error = (
        "Got an unexpected value for \"source_type\": \"foobar\"\n" "Expected: \"sasUri\"."
    )
    with pytest.raises(ValueError, match=expected_error):
        VMImageSource.from_json(vmimage_source)


@pytest.mark.parametrize(
    "value",
    ["super_secret_value", "another_secret_value", "*********"],
)
def test_mask_secrets(value: str) -> None:
    assert _mask_secret(value) == "*********"


def test_deprecation_alternative_properties() -> None:
    product_id = "ffffffff-ffff-ffff-ffff-ffffffffffff"
    product_durable = f"product/{product_id}"
    plan_id = "00000000-0000-0000-0000-000000000000"
    plan_durable = f"plan/{product_id}/{plan_id}"

    # Test deprecation for "product"
    obj = DeprecationAlternative.from_json({"product": product_durable})

    assert obj.product_id == product_id
    assert obj.plan_id is None

    # Test deprecation for "plan"
    obj = DeprecationAlternative.from_json({"plan": plan_durable})

    assert obj.product_id is None
    assert obj.plan_id == plan_id


def test_vmi_plan_tech_config_property(technical_config: Dict[str, Any]) -> None:
    # Test base_plan_id not set
    obj = VMIPlanTechConfig.from_json(technical_config)

    assert obj.base_plan_id is None

    # Test base_plan_id set
    plan_id = "00000000-0000-0000-0000-000000000000"
    plan_durable = f"plan/ffffffff-ffff-ffff-ffff-ffffffffffff/{plan_id}"
    technical_config.update({"basePlan": plan_durable})

    obj = VMIPlanTechConfig.from_json(technical_config)

    assert obj.base_plan_id == plan_id


def test_deprecation_schedule_defaults() -> None:
    """Test the default values for DeprecationSchedule."""
    data = {
        "date": "12/12/2023",
    }
    res = DeprecationSchedule.from_json(data)

    assert res.reason == "other"
