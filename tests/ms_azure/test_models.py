from typing import Any, Dict

import pytest

from cloudpub.models.ms_azure import (
    CustomerLeads,
    DiskVersion,
    ListingAsset,
    PlanListing,
    PlanSummary,
    Product,
    PublishTarget,
    VMImageSource,
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
