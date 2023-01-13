from typing import Any, Dict, List
from unittest import mock

import pytest

from cloudpub.models.ms_azure import (
    CustomerLeads,
    DiskVersion,
    Listing,
    ListingAsset,
    PlanListing,
    PlanSummary,
    PriceAndAvailabilityOffer,
    PriceAndAvailabilityPlan,
    Product,
    ProductProperty,
    ProductReseller,
    ProductSubmission,
    ProductSummary,
    TestDrive,
    VMImageDefinition,
    VMImageSource,
    VMIPlanTechConfig,
)
from cloudpub.ms_azure import AzurePublishingMetadata, AzureService


@pytest.fixture
def token() -> Dict[str, str]:
    return {
        "token_type": "Bearer",
        "expires_in": "3599",
        "ext_expires_in": "3599",
        "expires_on": "1646935200",  # 2022-03-10 15:00:00
        "not_before": "1646931600",  # 2022-03-10 14:00:00
        "resource": "https://graph.microsoft.com/rp/product-ingestion",
        "access_token": "aBcDeFgHiJkLmNoPqRsTuVwXyZ",
    }


@pytest.fixture()
def auth_dict() -> Dict[str, str]:
    return {
        "AZURE_TENANT_ID": "foo",
        "AZURE_CLIENT_ID": "bar",
        "AZURE_API_SECRET": "abcdefghijklmnopqrstuvwxyz0123456789",
        "AZURE_PUBLISHER_NAME": "publisher",
        "AZURE_API_VERSION": "2022-07-01",
    }


@pytest.fixture
@mock.patch("cloudpub.ms_azure.service.PartnerPortalSession")
def azure_service(auth_dict: Dict[str, str]) -> AzureService:
    """Return an instance of AzureService with mocked PartnerPortalSession."""
    return AzureService(auth_dict)


def job_details(status: str, result: str, errors: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "$schema": "https://schema",
        "jobId": "aa0a0000-0e00-00aa-aa00-a00000000a00",
        "jobStatus": status,
        "jobResult": result,
        "jobStart": "2022-06-13T09:59:34.3049612Z",
        "jobEnd": "2022-06-13T10:00:39.866244Z",
        "resourceUri": "https://resource.com",
        "errors": errors,
    }


@pytest.fixture
def job_details_not_started() -> Dict[str, Any]:
    return job_details(status="notStarted", result="pending", errors=[])


@pytest.fixture
def job_details_running() -> Dict[str, Any]:
    return job_details(status="running", result="pending", errors=[])


@pytest.fixture
def job_details_completed_successfully() -> Dict[str, Any]:
    return job_details(status="completed", result="succeeded", errors=[])


@pytest.fixture
def job_details_completed_failure(errors: List[Dict[str, Any]]) -> Dict[str, Any]:
    return job_details(status="completed", result="failed", errors=errors)


@pytest.fixture
def errors() -> List[Dict[str, Any]]:
    return [
        {
            "code": "conflict",
            "message": "Error message",
            "details": [{"code": "invalidResource", "message": "Failure for resource"}],
        }
    ]


@pytest.fixture
def configure_success_response() -> Dict[str, Any]:
    return {
        "$schema": "https://schema",
        "jobId": "0a0a00aa-00a0-0a00-0a0a-00000a000a00",
        "jobStatus": "running",
        "jobResult": "pending",
        "jobStart": "2022-06-13T08:43:47.5235Z",
        "jobEnd": "0001-01-01T00:00:00",
        "errors": [],
    }


@pytest.fixture
def configure_failure_response() -> Dict[str, Any]:
    return {
        "error": {
            "code": "badRequest",
            "message": "Invalid configuration: schema validation failed",
            "details": [
                {
                    "code": "schemaValidationError",
                    "message": "Schema validation failed for schema https://scheme",
                }
            ],
        }
    }


@pytest.fixture
def metadata_azure(common_metadata: Dict[str, str]) -> Dict[str, str]:
    d = {
        "disk_version": "2.1.0",
        "sku_id": "test-plan",
        "generation": "V2",
    }
    d.update(common_metadata)
    d.update({"image_path": "https://foo.com/bar/image.vhd"})
    d.update({"destination": "test-offer/test-plan"})
    return d


@pytest.fixture
def product_summary() -> Dict[str, Any]:
    return {
        "$schema": "https://product-ingestion.azureedge.net/schema/product/2022-03-01-preview3",
        "id": "product/ffffffff-ffff-ffff-ffff-ffffffffffff",
        "identity": {"externalId": "example-product"},
        "type": "azureVirtualMachine",
        "alias": "Example Product",
    }


@pytest.fixture
def customer_leads() -> Dict[str, str]:
    return {
        "$schema": "https://product-ingestion.azureedge.net/schema/customer-leads/2022-03-01-preview2",  # noqa: E501
        "id": "customer-leads/ffffffff-ffff-ffff-ffff-ffffffffffff",
        "product": "product/ffffffff-ffff-ffff-ffff-ffffffffffff",
        "leadDestination": "none",
    }


@pytest.fixture
def test_drive() -> Dict[str, Any]:
    return {
        "$schema": "https://product-ingestion.azureedge.net/schema/test-drive/2022-03-01-preview2",
        "id": "test-drive/ffffffff-ffff-ffff-ffff-ffffffffffff",
        "product": "product/ffffffff-ffff-ffff-ffff-ffffffffffff",
        "enabled": False,
    }


@pytest.fixture
def plan_summary() -> Dict[str, Any]:
    return {
        "$schema": "https://product-ingestion.azureedge.net/schema/plan/2022-03-01-preview2",
        "id": "plan/ffffffff-ffff-ffff-ffff-ffffffffffff/00000000-0000-0000-0000-000000000000",
        "identity": {"externalId": "plan-1"},
        "alias": "Plan 1",
        "azureRegions": ["azureGlobal"],
        "product": "product/ffffffff-ffff-ffff-ffff-ffffffffffff",
    }


@pytest.fixture
def product_property() -> Dict[str, Any]:
    return {
        "$schema": "https://product-ingestion.azureedge.net/schema/property/2022-03-01-preview3",
        "id": "property/ffffffff-ffff-ffff-ffff-ffffffffffff/public/main",
        "product": "product/ffffffff-ffff-ffff-ffff-ffffffffffff",
        "kind": "azureVM",
        "termsOfUse": "test",
        "termsConditions": "custom",
        "categories": {"compute": ["operating-systems"]},
    }


@pytest.fixture
def product_listing() -> Dict[str, Any]:
    return {
        "$schema": "https://product-ingestion.azureedge.net/schema/listing/2022-03-01-preview3",
        "id": "listing/ffffffff-ffff-ffff-ffff-ffffffffffff/public/main/default/en-us",
        "product": "product/ffffffff-ffff-ffff-ffff-ffffffffffff",
        "kind": "azureVM",
        "title": "Test Product",
        "description": "This is the description",
        "searchResultSummary": "product test",
        "shortDescription": "Short description",
        "privacyPolicyLink": "https://www.foo.com/bar/privacy-policy",
        "cloudSolutionProviderMarketingMaterials": "",
        "supportContact": {"name": "a", "email": "a@b.com", "phone": "12345678"},
        "engineeringContact": {"name": "a", "email": "a@b.com", "phone": "123456"},
        "languageId": "en-us",
    }


@pytest.fixture
def plan_listing() -> Dict[str, Any]:
    return {
        "$schema": "https://product-ingestion.azureedge.net/schema/plan-listing/2022-03-01-preview3",  # noqa: E501
        "id": "plan-listing/ffffffff-ffff-ffff-ffff-ffffffffffff/public/main/00000000-0000-0000-0000-000000000000/en-us",  # noqa: E501
        "product": "product/ffffffff-ffff-ffff-ffff-ffffffffffff",
        "kind": "azureVM-plan",
        "name": "Plan 1",
        "description": "a",
        "summary": "a",
        "plan": "plan/ffffffff-ffff-ffff-ffff-ffffffffffff/00000000-0000-0000-0000-000000000000",
        "languageId": "en-us",
    }


@pytest.fixture
def listing_asset() -> Dict[str, Any]:
    return {
        "$schema": "https://product-ingestion.azureedge.net/schema/listing-asset/2022-03-01-preview3",  # noqa: E501
        "id": "listing-asset/ffffffff-ffff-ffff-ffff-ffffffffffff/public/main/default/en-us/azurelogosmall/1",  # noqa: E501
        "product": "product/ffffffff-ffff-ffff-ffff-ffffffffffff",
        "kind": "azure",
        "listing": "listing/ffffffff-ffff-ffff-ffff-ffffffffffff/public/main/default/en-us",
        "type": "azureLogoSmall",
        "languageId": "en-us",
        "description": "",
        "displayOrder": 0,
        "fileName": "SmallLogo.png",
        "friendlyName": "SmallLogo.png",
        "url": "https://ingestionpackagesprod1.blob.core.windows.net/file/foo.png",
    }


@pytest.fixture
def prav_offer() -> Dict[str, Any]:
    return {
        "$schema": "https://product-ingestion.azureedge.net/schema/price-and-availability-offer/2022-03-01-preview3",  # noqa: E501
        "id": "price-and-availability-offer/ffffffff-ffff-ffff-ffff-ffffffffffff",
        "product": "product/ffffffff-ffff-ffff-ffff-ffffffffffff",
        "previewAudiences": [
            {"type": "subscription", "id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "label": ""}
        ],
    }


@pytest.fixture
def prav_plan() -> Dict[str, Any]:
    return {
        "$schema": "https://schema.mp.microsoft.com/schema/price-and-availability-plan/2022-03-01-preview4",  # noqa: E501
        "id": "price-and-availability-plan/ffffffff-ffff-ffff-ffff-ffffffffffff/00000000-0000-0000-0000-000000000000",  # noqa: E501
        "product": "product/ffffffff-ffff-ffff-ffff-ffffffffffff",
        "plan": "plan/ffffffff-ffff-ffff-ffff-ffffffffffff/00000000-0000-0000-0000-000000000000",
        "visibility": "visible",
        "markets": [
            "us",
        ],
        "pricing": {
            "licenseModel": "payAsYouGo",
            "corePricing": {"priceInputOption": "perCore", "pricePerCore": 1111.0},
        },
        "trial": None,
        "softwareReservation": [],
        "audience": "public",
        "privateAudiences": [],
    }


@pytest.fixture
def vmimage_source() -> Dict[str, Any]:
    return {
        "sourceType": "sasUri",
        "osDisk": {"uri": "https://uri.test.com"},
        "dataDisks": [],
    }


@pytest.fixture
def gen1_image(vmimage_source) -> Dict[str, Any]:
    return {
        "imageType": "x64Gen1",
        "source": vmimage_source,
    }


@pytest.fixture
def gen2_image(vmimage_source) -> Dict[str, Any]:
    return {
        "imageType": "x64Gen2",
        "source": vmimage_source,
    }


@pytest.fixture
def disk_version(gen1_image: Dict[str, Any], gen2_image: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "versionNumber": "2.0.0",
        "vmImages": [gen1_image, gen2_image],
        "lifecycleState": "generallyAvailable",
    }


@pytest.fixture
def technical_config(disk_version: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "$schema": "https://product-ingestion.azureedge.net/schema/virtual-machine-plan-technical-configuration/2022-03-01-preview2",  # noqa: E501
        "id": "virtual-machine-plan-technical-configuration/ffffffff-ffff-ffff-ffff-ffffffffffff/00000000-0000-0000-0000-000000000000",  # noqa: E501
        "product": "product/ffffffff-ffff-ffff-ffff-ffffffffffff",
        "plan": "plan/00000000-0000-0000-0000-000000000000",
        "operatingSystem": {"family": "linux", "friendlyName": "Linux", "type": "redHat"},
        "recommendedVmSizes": [],
        "openPorts": [],
        "vmProperties": {
            "supportsExtensions": True,
            "supportsBackup": False,
            "supportsAcceleratedNetworking": False,
            "isNetworkVirtualAppliance": False,
            "supportsNVMe": False,
            "supportsCloudInit": False,
            "supportsAadLogin": False,
            "supportsHibernation": False,
            "supportsRemoteConnection": True,
            "requiresCustomArmTemplate": False,
        },
        "skus": [
            {"imageType": "x64Gen2", "skuId": "plan-1"},
            {"imageType": "x64Gen1", "skuId": "plan-1-gen1"},
        ],
        "vmImageVersions": [disk_version],
    }


@pytest.fixture
def reseller() -> Dict[str, Any]:
    return {
        "$schema": "https://product-ingestion.azureedge.net/schema/reseller/2022-03-01-preview2",
        "id": "reseller/ffffffff-ffff-ffff-ffff-ffffffffffff",
        "product": "product/ffffffff-ffff-ffff-ffff-ffffffffffff",
        "resellerChannelState": "notSet",
        "audiences": [],
    }


@pytest.fixture
def publish_target() -> Dict[str, str]:
    return {"targetType": "draft"}


@pytest.fixture
def submission(publish_target: Dict[str, str]) -> Dict[str, Any]:
    return {
        "$schema": "https://product-ingestion.azureedge.net/schema/submission/2022-03-01-preview2",
        "id": "submission/ffffffff-ffff-ffff-ffff-ffffffffffff/0",
        "product": "product/ffffffff-ffff-ffff-ffff-ffffffffffff",
        "target": publish_target,
        "lifecycleState": "generallyAvailable",
    }


@pytest.fixture
def product(
    publish_target: Dict[str, str],
    product_summary: Dict[str, str],
    customer_leads: Dict[str, str],
    test_drive: Dict[str, Any],
    plan_summary: Dict[str, Any],
    product_property: Dict[str, Any],
    product_listing: Dict[str, Any],
    plan_listing: Dict[str, Any],
    listing_asset: Dict[str, Any],
    prav_offer: Dict[str, Any],
    prav_plan: Dict[str, Any],
    technical_config: Dict[str, Any],
    reseller: Dict[str, Any],
    submission: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "$schema": "https://product-ingestion.azureedge.net/schema/resource-tree/2022-03-01-preview2",  # noqa: E501
        "root": "product/product/ffffffff-ffff-ffff-ffff-ffffffffffff",
        "target": publish_target,
        "resources": [
            product_summary,
            technical_config,
            customer_leads,
            test_drive,
            plan_summary,
            product_property,
            product_listing,
            plan_listing,
            listing_asset,
            prav_offer,
            prav_plan,
            reseller,
            submission,
        ],
    }


@pytest.fixture
def metadata_azure_obj(metadata_azure: Dict[str, Any]) -> AzurePublishingMetadata:
    return AzurePublishingMetadata(**metadata_azure)


@pytest.fixture
def product_obj(product: Dict[str, Any]) -> Product:
    return Product.from_json(product)


@pytest.fixture
def product_summary_obj(product_summary: Dict[str, str]) -> ProductSummary:
    return ProductSummary.from_json(product_summary)


@pytest.fixture
def submission_obj(submission: Dict[str, Any]) -> ProductSubmission:
    return ProductSubmission.from_json(submission)


@pytest.fixture
def plan_summary_obj(plan_summary: Dict[str, Any]) -> PlanSummary:
    return PlanSummary.from_json(plan_summary)


@pytest.fixture
def customer_leads_obj(customer_leads: Dict[str, str]) -> CustomerLeads:
    return CustomerLeads.from_json(customer_leads)


@pytest.fixture
def test_drive_obj(test_drive: Dict[str, Any]) -> TestDrive:
    return TestDrive.from_json(test_drive)


@pytest.fixture
def product_property_obj(product_property: Dict[str, Any]) -> ProductProperty:
    return ProductProperty.from_json(product_property)


@pytest.fixture
def product_listing_obj(product_listing: Dict[str, Any]) -> Listing:
    return Listing.from_json(product_listing)


@pytest.fixture
def plan_listing_obj(plan_listing: Dict[str, Any]) -> PlanListing:
    return PlanListing.from_json(plan_listing)


@pytest.fixture
def listing_asset_obj(listing_asset: Dict[str, Any]) -> ListingAsset:
    return ListingAsset.from_json(listing_asset)


@pytest.fixture
def prav_offer_obj(prav_offer: Dict[str, Any]) -> PriceAndAvailabilityOffer:
    return PriceAndAvailabilityOffer.from_json(prav_offer)


@pytest.fixture
def prav_plan_obj(prav_plan: Dict[str, Any]) -> PriceAndAvailabilityPlan:
    return PriceAndAvailabilityPlan.from_json(prav_plan)


@pytest.fixture
def technical_config_obj(technical_config: Dict[str, Any]) -> VMIPlanTechConfig:
    return VMIPlanTechConfig.from_json(technical_config)


@pytest.fixture
def reseller_obj(reseller: Dict[str, Any]) -> ProductReseller:
    return ProductReseller.from_json(reseller)


@pytest.fixture
def gen1_image_obj(gen1_image: Dict[str, Any]) -> VMImageDefinition:
    return VMImageDefinition.from_json(gen1_image)


@pytest.fixture
def gen2_image_obj(gen2_image: Dict[str, Any]) -> VMImageDefinition:
    return VMImageDefinition.from_json(gen2_image)


@pytest.fixture
def disk_version_obj(disk_version: Dict[str, Any]) -> DiskVersion:
    return DiskVersion.from_json(disk_version)


@pytest.fixture
def vmimage_source_obj(vmimage_source: Dict[str, Any]) -> VMImageSource:
    return VMImageSource.from_json(vmimage_source)
