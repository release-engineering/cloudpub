import logging
from copy import deepcopy
from typing import Any, Dict, List
from unittest import mock

import pytest
from _pytest.logging import LogCaptureFixture
from httmock import response
from requests import Response
from requests.exceptions import HTTPError

from cloudpub.common import BaseService
from cloudpub.error import InvalidStateError, NotFoundError
from cloudpub.models.ms_azure import (
    ConfigureStatus,
    CustomerLeads,
    DiskVersion,
    Listing,
    ListingAsset,
    OSDiskURI,
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
    VMISku,
)
from cloudpub.ms_azure import AzurePublishingMetadata, AzureService
from cloudpub.ms_azure.utils import get_image_type_mapping


class TestAzureService:
    @mock.patch("cloudpub.ms_azure.service.PartnerPortalSession")
    def test_azure_service(self, mock_session: mock.MagicMock, auth_dict: Dict[str, str]) -> None:
        assert issubclass(AzureService, BaseService), "AzureService must be sublass of BaseService."

        svc = AzureService(credentials=auth_dict)

        mock_session.make_graph_api_session.assert_called_once_with(
            auth_keys=auth_dict, schema_version=auth_dict["AZURE_SCHEMA_VERSION"]
        )

        assert isinstance(svc, AzureService)
        assert not svc._products

    def test_raise_error(self, caplog: LogCaptureFixture):
        expected_err = "This is an error."

        with caplog.at_level(logging.DEBUG):
            with pytest.raises(ValueError, match=expected_err):
                AzureService._raise_error(ValueError, expected_err)
        assert expected_err in caplog.text

    @pytest.mark.parametrize(
        "response",
        [
            response(200, "OK"),
            response(404, "Not found"),
            response(415, "Some error"),
            response(500, "Another error"),
            response(512, "Yet another error"),
        ],
    )
    @mock.patch("cloudpub.ms_azure.AzureService._raise_error")
    def test_raise_for_status(
        self, mock_raise: mock.MagicMock, azure_service: AzureService, response: Response
    ) -> None:
        mock_raise.side_effect = Exception(response.text)

        if response.status_code < 299:
            azure_service._raise_for_status(response)
            mock_raise.assert_not_called()
        else:
            with pytest.raises(Exception):
                azure_service._raise_for_status(response)

            if response.status_code == 404:
                mock_raise.assert_called_once_with(NotFoundError, "Resource not found.")
            else:
                mock_raise.assert_called_once_with(HTTPError, f"Response content:\n{response.text}")

    @pytest.mark.parametrize(
        "content",
        [
            {"foo": "bar"},
            ("foo", "bar"),
            ["foo", "bar"],
            2,
        ],
    )
    @mock.patch("cloudpub.ms_azure.AzureService._raise_for_status")
    @mock.patch("cloudpub.ms_azure.AzureService._raise_error")
    @mock.patch("cloudpub.ms_azure.session.requests.Response")
    def test_assert_dict(
        self,
        mock_response: mock.MagicMock,
        mock_raise: mock.MagicMock,
        mock_raise_status: mock.MagicMock,
        azure_service: AzureService,
        content: Any,
    ) -> None:
        mock_response.json.return_value = content

        res = azure_service._assert_dict(mock_response)

        assert res == content
        mock_raise_status.assert_called_once_with(mock_response)
        if isinstance(content, dict):
            mock_raise.assert_not_called()
        else:
            mock_raise.assert_called_once_with(
                ValueError, f"Expected response to be a dictionary, got {type(content)}"
            )

    @mock.patch("cloudpub.ms_azure.AzureService._raise_for_status")
    def test_configure_request(
        self,
        mock_raise_status: mock.MagicMock,
        azure_service: AzureService,
        caplog: LogCaptureFixture,
    ) -> None:
        req_json = {"to": "configure"}
        res_json = {"foo": "bar"}
        res_obj = response(200, res_json)

        with mock.patch.object(azure_service.session, 'post', return_value=res_obj) as mock_post:
            with caplog.at_level(logging.DEBUG):
                res = azure_service._configure(req_json)

                mock_post.assert_called_once_with(path="configure", json=req_json)
                mock_raise_status.assert_called_once_with(response=res_obj)
                assert res == ConfigureStatus.from_json(res_json)
                assert f"Received the following data to create/modify: {req_json}" in caplog.text

    @mock.patch("cloudpub.ms_azure.AzureService._raise_for_status")
    def test_query_job_details(
        self,
        mock_raise_status: mock.MagicMock,
        azure_service: AzureService,
        caplog: LogCaptureFixture,
    ) -> None:
        res_json = {"status": "success"}
        res_obj = response(200, res_json)

        with mock.patch.object(azure_service.session, 'get', return_value=res_obj) as mock_get:
            with caplog.at_level(logging.DEBUG):
                res = azure_service._query_job_details("job-id")

                mock_get.assert_called_once_with(path="configure/job-id/status")
                mock_raise_status.assert_called_once_with(response=res_obj)
                assert res == ConfigureStatus.from_json(res_json)
                assert "Query job details for \"job-id\"" in caplog.text

    @mock.patch("cloudpub.ms_azure.utils.is_azure_job_not_complete")
    @mock.patch("cloudpub.ms_azure.AzureService._query_job_details")
    def test_wait_for_job_completion_successful_completion(
        self,
        mock_job_details: mock.MagicMock,
        mock_is_job_not_complete: mock.MagicMock,
        azure_service: AzureService,
        caplog: LogCaptureFixture,
        job_details_running_obj: ConfigureStatus,
        job_details_completed_successfully_obj: ConfigureStatus,
    ) -> None:
        mock_job_details.side_effect = [
            job_details_running_obj,
            job_details_running_obj,
            job_details_running_obj,
            job_details_completed_successfully_obj,
            job_details_running_obj,
        ]

        azure_service._wait_for_job_completion.retry.sleep = mock.Mock()  # type: ignore
        job_id = "job_id_111"
        with caplog.at_level(logging.DEBUG):
            res = azure_service._wait_for_job_completion(job_id=job_id)
            assert mock_job_details.call_count == 4
            assert res == job_details_completed_successfully_obj
            assert f"Job {job_id} failed" not in caplog.text
            assert f"Job {job_id} succeeded" in caplog.text

    @mock.patch("cloudpub.ms_azure.utils.is_azure_job_not_complete")
    @mock.patch("cloudpub.ms_azure.AzureService._query_job_details")
    def test_get_job_details_after_failed_completion(
        self,
        mock_job_details: mock.MagicMock,
        mock_is_job_not_completed: mock.MagicMock,
        azure_service: AzureService,
        caplog: LogCaptureFixture,
        job_details_running_obj: ConfigureStatus,
        job_details_completed_failure_obj: ConfigureStatus,
        errors: List[Dict[str, Any]],
    ) -> None:
        mock_job_details.side_effect = [
            job_details_running_obj,
            job_details_running_obj,
            job_details_running_obj,
            job_details_completed_failure_obj,
            job_details_running_obj,
        ]

        azure_service._wait_for_job_completion.retry.sleep = mock.Mock()  # type: ignore
        job_id = "job_id_111"
        with caplog.at_level(logging.ERROR):
            with pytest.raises(InvalidStateError) as e_info:
                azure_service._wait_for_job_completion(job_id=job_id)
                assert f"Job {job_id} failed: \n" in str(e_info.value)
            assert mock_job_details.call_count == 4
            assert f"Job {job_id} failed" in caplog.text
            assert f"Job {job_id} succeeded" not in caplog.text

    @mock.patch("cloudpub.ms_azure.AzureService._wait_for_job_completion")
    @mock.patch("cloudpub.ms_azure.AzureService._configure")
    def test_configure(
        self,
        mock_configure: mock.MagicMock,
        mock_wait_completion: mock.MagicMock,
        azure_service: AzureService,
        job_details_completed_successfully_obj: ConfigureStatus,
        submission_obj: ProductSubmission,
        caplog: LogCaptureFixture,
    ) -> None:
        mock_configure.return_value = job_details_completed_successfully_obj
        job_id = job_details_completed_successfully_obj.job_id
        expected_data = {
            "$schema": f"https://schema.mp.microsoft.com/schema/configure/{azure_service.AZURE_API_VERSION}",  # noqa E501
            "resources": [submission_obj.to_json()],
        }

        with caplog.at_level(logging.DEBUG):
            azure_service.configure(submission_obj)

        mock_configure.assert_called_once_with(data=expected_data)
        mock_wait_completion.assert_called_once_with(job_id=job_id)
        assert f"Data to configure: {expected_data}" in caplog.text

    @mock.patch("cloudpub.ms_azure.AzureService._raise_error")
    @mock.patch("cloudpub.ms_azure.AzureService._assert_dict")
    def test_products_success(
        self,
        mock_adict: mock.MagicMock,
        mock_raise: mock.MagicMock,
        azure_service: AzureService,
        product_summary: Dict[str, str],
        product_summary_obj: ProductSummary,
    ) -> None:
        res_data = {
            "value": [
                product_summary,
                product_summary,
                product_summary,
            ]
        }
        mock_adict.return_value = res_data
        res_obj = response(200, res_data)

        with mock.patch.object(azure_service.session, 'get', return_value=res_obj) as mock_get:
            for ps in azure_service.products:
                assert ps == product_summary_obj

        mock_adict.assert_called_once_with(res_obj)
        mock_raise.assert_not_called()
        mock_get.assert_called_once_with(path="/product", params={})

    @mock.patch("cloudpub.ms_azure.AzureService._raise_error")
    @mock.patch("cloudpub.ms_azure.AzureService._assert_dict")
    def test_products_invalid_data(
        self, mock_adict: mock.MagicMock, mock_raise: mock.MagicMock, azure_service: AzureService
    ) -> None:
        res_data = {"value": "invalid"}
        mock_adict.return_value = res_data
        expected_err = "Expected response.values to contain a list, got <class 'str'>."
        mock_raise.side_effect = ValueError(expected_err)
        res_obj = response(200, res_data)

        with mock.patch.object(azure_service.session, 'get', return_value=res_obj) as mock_get:
            with pytest.raises(ValueError, match=expected_err):
                for _ in azure_service.products:
                    pass

        mock_adict.assert_called_once_with(res_obj)
        mock_raise.assert_called_once_with(ValueError, expected_err)
        mock_get.assert_called_once_with(path="/product", params={})

    @mock.patch("cloudpub.ms_azure.AzureService.products")
    def test_list_products(
        self,
        mock_products: mock.MagicMock,
        azure_service: AzureService,
        product_summary: Dict[str, str],
    ) -> None:
        # Test uncached list
        azure_service._products = []
        mock_products.__iter__.return_value = [product_summary]

        res = azure_service.list_products()

        assert res == [product_summary]
        mock_products.__iter__.assert_called_once()
        assert azure_service._products == [product_summary]

        # Test cached list
        mock_products.reset_mock()
        azure_service.list_products()
        mock_products.__iter__.assert_not_called()

    @mock.patch("cloudpub.ms_azure.AzureService._assert_dict")
    def test_get_product(
        self,
        mock_adict: mock.MagicMock,
        azure_service: AzureService,
        product: Dict[str, Any],
        product_obj: Product,
    ) -> None:
        res_obj = response(200, product)
        mock_adict.return_value = product

        with mock.patch.object(azure_service.session, 'get', return_value=res_obj) as mock_get:
            res = azure_service.get_product("product-id")

            mock_get.assert_called_once_with(
                path="/resource-tree/product/product-id", params={"targetType": "preview"}
            )
            mock_adict.assert_called_once_with(res_obj)
            assert res == product_obj

    def test_get_product_not_found(
        self,
        azure_service: AzureService,
        product_obj: Product,
    ) -> None:
        res_obj = response(
            404,
            {
                "error": {
                    "code": "notFound",
                    "message": "whatever error",
                    "details": [],
                }
            },
        )

        with mock.patch.object(azure_service.session, 'get', return_value=res_obj) as mock_get:
            with pytest.raises(NotFoundError, match="No such product with id \"unknown-id\""):
                azure_service.get_product("unknown-id")
                calls = [
                    mock.call(path="/resource-tree/product/unknown-id?targetType=preview"),
                    mock.call(path="/resource-tree/product/unknown-id?targetType=live"),
                    mock.call(path="/resource-tree/product/unknown-id?targetType=draft"),
                ]
                mock_get.assert_has_calls(calls)

    @mock.patch("cloudpub.ms_azure.AzureService.get_product")
    @mock.patch("cloudpub.ms_azure.AzureService.products")
    def test_get_product_by_name(
        self,
        mock_products: mock.MagicMock,
        mock_getpr: mock.MagicMock,
        azure_service: AzureService,
        product_obj: Product,
        product_summary_obj: ProductSummary,
    ) -> None:
        # Note: mock_products is mocking the products property
        mock_products.__iter__.return_value = [product_summary_obj]
        mock_getpr.return_value = product_obj

        res = azure_service.get_product_by_name(product_name="example-product")

        mock_products.__iter__.assert_called_once()
        mock_getpr.assert_called_once_with("ffffffff-ffff-ffff-ffff-ffffffffffff")
        assert res == product_obj

    @mock.patch("cloudpub.ms_azure.AzureService.get_product")
    @mock.patch("cloudpub.ms_azure.AzureService.products")
    def test_get_product_by_name_not_found(
        self,
        mock_products: mock.MagicMock,
        mock_getpr: mock.MagicMock,
        azure_service: AzureService,
        product_obj: Product,
        product_summary_obj: ProductSummary,
    ) -> None:
        # Note: mock_products is mocking the products property
        mock_products.__iter__.return_value = [product_summary_obj]
        mock_getpr.return_value = product_obj

        with pytest.raises(NotFoundError, match="No such product with name \"foo-bar\""):
            azure_service.get_product_by_name(product_name="foo-bar")

        mock_products.__iter__.assert_called_once()
        mock_getpr.assert_not_called()

    @mock.patch("cloudpub.ms_azure.AzureService._assert_dict")
    def test_get_submissions(
        self,
        mock_adict: mock.MagicMock,
        azure_service: AzureService,
        submission_obj: ProductSubmission,
    ) -> None:
        dict_obj = {"value": [submission_obj.to_json()]}
        res_obj = response(200, dict_obj)
        mock_adict.return_value = dict_obj

        with mock.patch.object(azure_service.session, 'get', return_value=res_obj) as mock_get:
            res = azure_service.get_submissions("product-id")

            mock_get.assert_called_once_with(path="/submission/product-id")
            mock_adict.assert_called_once_with(res_obj)
            assert res == [submission_obj]

    @mock.patch("cloudpub.ms_azure.AzureService.get_submissions")
    def test_get_submission_state_success(
        self,
        mock_get_submissions: mock.MagicMock,
        azure_service: AzureService,
        submission_obj: ProductSubmission,
    ) -> None:
        submission_obj.target.targetType = "preview"
        mock_get_submissions.return_value = [submission_obj]

        res = azure_service.get_submission_state("product-id", state="preview")

        mock_get_submissions.assert_called_once_with("product-id")
        assert res == submission_obj

    @mock.patch("cloudpub.ms_azure.AzureService.get_submissions")
    def test_get_submission_state_not_found(
        self,
        mock_get_submissions: mock.MagicMock,
        azure_service: AzureService,
        submission_obj: ProductSubmission,
    ) -> None:
        submission_obj.target.targetType = "draft"
        mock_get_submissions.return_value = [submission_obj]

        res = azure_service.get_submission_state("product-id", state="preview")

        mock_get_submissions.assert_called_once_with("product-id")
        assert not res

    def test_filter_product_resources(
        self,
        azure_service: AzureService,
        product_summary_obj: ProductSummary,
        customer_leads_obj: CustomerLeads,
        test_drive_obj: TestDrive,
        plan_summary_obj: PlanSummary,
        product_property_obj: ProductProperty,
        plan_listing_obj: PlanListing,
        product_listing_obj: Listing,
        listing_asset_obj: ListingAsset,
        prav_offer_obj: PriceAndAvailabilityOffer,
        prav_plan_obj: PriceAndAvailabilityPlan,
        technical_config_obj: VMIPlanTechConfig,
        reseller_obj: ProductReseller,
        submission_obj: ProductSubmission,
        product_obj: Product,
    ) -> None:
        expected_resources = {
            "product": product_summary_obj,
            "customer-leads": customer_leads_obj,
            "test-drive": test_drive_obj,
            "plan": plan_summary_obj,
            "property": product_property_obj,
            "plan-listing": plan_listing_obj,
            "listing": product_listing_obj,
            "listing-asset": listing_asset_obj,
            "price-and-availability-offer": prav_offer_obj,
            "price-and-availability-plan": prav_plan_obj,
            "virtual-machine-plan-technical-configuration": technical_config_obj,
            "reseller": reseller_obj,
            "submission": submission_obj,
        }

        # Test success
        for key, value in expected_resources.items():
            res = azure_service.filter_product_resources(product=product_obj, resource=key)
            assert res == [value]

        # Test failure
        expected_err = "Invalid resource type \"foo\"."
        with pytest.raises(ValueError, match=expected_err):
            azure_service.filter_product_resources(product=product_obj, resource="foo")

    @mock.patch("cloudpub.ms_azure.AzureService.filter_product_resources")
    def test_get_plan_by_name(
        self,
        mock_filter: mock.MagicMock,
        plan_summary_obj: PlanSummary,
        product_obj: Product,
        azure_service: AzureService,
    ) -> None:
        mock_filter.return_value = [plan_summary_obj]

        # Test found
        res = azure_service.get_plan_by_name(product_obj, "plan-1")
        mock_filter.assert_called_once_with(product=product_obj, resource="plan")
        assert res == plan_summary_obj

        # Test not found
        with pytest.raises(NotFoundError, match="No such plan with name \"foo\""):
            azure_service.get_plan_by_name(product_obj, "foo")

    @pytest.mark.parametrize(
        "prev_status,final_status",
        [
            ('draft', 'draft'),
            ('draft', 'preview'),
            ('preview', 'live'),
        ],
    )
    @mock.patch("cloudpub.ms_azure.AzureService.configure")
    @mock.patch("cloudpub.ms_azure.AzureService.get_submission_state")
    def test_submit_to_status(
        self,
        mock_getsubst: mock.MagicMock,
        mock_configure: mock.MagicMock,
        prev_status: str,
        final_status: str,
        submission_obj: ProductSubmission,
        product_obj: Product,
        azure_service: AzureService,
    ) -> None:
        mock_getsubst.return_value = submission_obj
        submission_obj.target.targetType = final_status

        azure_service.submit_to_status(product_obj.id, final_status)

        mock_getsubst.assert_called_once_with(product_id=product_obj.id, state=prev_status)
        mock_configure.assert_called_once_with(resource=submission_obj)

    @mock.patch("cloudpub.ms_azure.AzureService.configure")
    @mock.patch("cloudpub.ms_azure.AzureService.get_submission_state")
    def test_submit_to_status_not_found(
        self,
        mock_getsubst: mock.MagicMock,
        mock_configure: mock.MagicMock,
        product_obj: Product,
        azure_service: AzureService,
    ) -> None:
        mock_getsubst.return_value = None
        err = f"Could not find the submission state \"preview\" for product \"{product_obj.id}\""

        with pytest.raises(RuntimeError, match=err):
            azure_service.submit_to_status(product_obj.id, "live")

        mock_configure.assert_not_called()

    @mock.patch("cloudpub.ms_azure.AzureService.configure")
    @mock.patch("cloudpub.ms_azure.AzureService.submit_to_status")
    @mock.patch("cloudpub.ms_azure.service.update_skus")
    @mock.patch("cloudpub.ms_azure.service.prepare_vm_images")
    @mock.patch("cloudpub.ms_azure.service.is_sas_present")
    @mock.patch("cloudpub.ms_azure.service.create_disk_version_from_scratch")
    @mock.patch("cloudpub.ms_azure.AzureService.filter_product_resources")
    @mock.patch("cloudpub.ms_azure.AzureService.get_plan_by_name")
    @mock.patch("cloudpub.ms_azure.AzureService.get_product_by_name")
    def test_publish_overwrite(
        self,
        mock_getpr_name: mock.MagicMock,
        mock_getpl_name: mock.MagicMock,
        mock_filter: mock.MagicMock,
        mock_disk_scratch: mock.MagicMock,
        mock_is_sas: mock.MagicMock,
        mock_prep_img: mock.MagicMock,
        mock_upd_sku: mock.MagicMock,
        mock_submit: mock.MagicMock,
        mock_configure: mock.MagicMock,
        product_obj: Product,
        plan_summary_obj: PlanSummary,
        metadata_azure_obj: AzurePublishingMetadata,
        technical_config_obj: VMIPlanTechConfig,
        disk_version_obj: DiskVersion,
        azure_service: AzureService,
    ) -> None:
        metadata_azure_obj.overwrite = True
        metadata_azure_obj.keepdraft = True
        metadata_azure_obj.destination = "example-product/plan-1"
        mock_getpr_name.return_value = product_obj
        mock_getpl_name.return_value = plan_summary_obj
        mock_filter.return_value = [technical_config_obj]
        mock_disk_scratch.return_value = disk_version_obj
        mock_upd_sku.return_value = technical_config_obj
        expected_source = VMImageSource(
            source_type="sasUri",
            os_disk=OSDiskURI(uri=metadata_azure_obj.image_path).to_json(),
            data_disks=[],
        )
        expected_tech_config = deepcopy(technical_config_obj)
        expected_tech_config.disk_versions = [disk_version_obj]

        azure_service.publish(metadata_azure_obj)

        mock_getpr_name.assert_called_once_with(product_name="example-product")
        mock_getpl_name.assert_called_once_with(product=product_obj, plan_name="plan-1")
        mock_filter.assert_called_once_with(
            product=product_obj, resource="virtual-machine-plan-technical-configuration"
        )
        mock_is_sas.assert_not_called()
        mock_prep_img.assert_not_called()
        mock_disk_scratch.assert_called_once_with(metadata_azure_obj, expected_source)
        mock_upd_sku.assert_called_once_with(
            disk_versions=[disk_version_obj],
            generation=metadata_azure_obj.generation,
            plan_name="plan-1",
        )
        mock_configure.assert_called_once_with(resource=technical_config_obj)
        mock_submit.assert_not_called()

    @mock.patch("cloudpub.ms_azure.AzureService.configure")
    @mock.patch("cloudpub.ms_azure.AzureService.submit_to_status")
    @mock.patch("cloudpub.ms_azure.service.update_skus")
    @mock.patch("cloudpub.ms_azure.service.prepare_vm_images")
    @mock.patch("cloudpub.ms_azure.service.is_sas_present")
    @mock.patch("cloudpub.ms_azure.service.create_disk_version_from_scratch")
    @mock.patch("cloudpub.ms_azure.AzureService.filter_product_resources")
    @mock.patch("cloudpub.ms_azure.AzureService.get_plan_by_name")
    @mock.patch("cloudpub.ms_azure.AzureService.get_product_by_name")
    def test_publish_nodiskversion(
        self,
        mock_getpr_name: mock.MagicMock,
        mock_getpl_name: mock.MagicMock,
        mock_filter: mock.MagicMock,
        mock_disk_scratch: mock.MagicMock,
        mock_is_sas: mock.MagicMock,
        mock_prep_img: mock.MagicMock,
        mock_upd_sku: mock.MagicMock,
        mock_submit: mock.MagicMock,
        mock_configure: mock.MagicMock,
        product_obj: Product,
        plan_summary_obj: PlanSummary,
        metadata_azure_obj: AzurePublishingMetadata,
        technical_config_obj: VMIPlanTechConfig,
        disk_version_obj: DiskVersion,
        azure_service: AzureService,
    ) -> None:
        metadata_azure_obj.overwrite = False
        metadata_azure_obj.keepdraft = True
        metadata_azure_obj.disk_version = "1.0.0"
        metadata_azure_obj.destination = "example-product/plan-1"
        mock_getpr_name.return_value = product_obj
        mock_getpl_name.return_value = plan_summary_obj
        technical_config_obj.disk_versions = []
        mock_filter.return_value = [technical_config_obj]
        mock_is_sas.return_value = False
        expected_source = VMImageSource(
            source_type="sasUri",
            os_disk=OSDiskURI(uri=metadata_azure_obj.image_path).to_json(),
            data_disks=[],
        )
        mock_disk_scratch.return_value = disk_version_obj
        disk_version_obj.vm_images[0].source = expected_source
        expected_tech_config = deepcopy(technical_config_obj)
        expected_tech_config.disk_versions.append(disk_version_obj)
        mock_upd_sku.return_value = [
            VMISku(id='plan-1', image_type='x64Gen2'),
            VMISku(id='plan-1-gen1', image_type='x64Gen1'),
        ]

        azure_service.publish(metadata_azure_obj)

        mock_getpr_name.assert_called_once_with(product_name="example-product")
        mock_getpl_name.assert_called_once_with(product=product_obj, plan_name="plan-1")
        mock_filter.assert_called_once_with(
            product=product_obj, resource="virtual-machine-plan-technical-configuration"
        )
        mock_is_sas.assert_called_once_with(technical_config_obj, metadata_azure_obj.image_path)
        mock_prep_img.assert_not_called()
        mock_upd_sku.assert_called_once_with(
            disk_versions=expected_tech_config.disk_versions,
            generation=metadata_azure_obj.generation,
            plan_name="plan-1",
        )
        mock_disk_scratch.assert_called_once_with(metadata_azure_obj, expected_source)
        mock_configure.assert_called_once_with(resource=expected_tech_config)
        mock_submit.assert_not_called()

    @mock.patch("cloudpub.ms_azure.AzureService.configure")
    @mock.patch("cloudpub.ms_azure.AzureService.submit_to_status")
    @mock.patch("cloudpub.ms_azure.service.update_skus")
    @mock.patch("cloudpub.ms_azure.service.prepare_vm_images")
    @mock.patch("cloudpub.ms_azure.service.is_sas_present")
    @mock.patch("cloudpub.ms_azure.service.create_disk_version_from_scratch")
    @mock.patch("cloudpub.ms_azure.AzureService.filter_product_resources")
    @mock.patch("cloudpub.ms_azure.AzureService.get_plan_by_name")
    @mock.patch("cloudpub.ms_azure.AzureService.get_product_by_name")
    def test_publish_saspresent(
        self,
        mock_getpr_name: mock.MagicMock,
        mock_getpl_name: mock.MagicMock,
        mock_filter: mock.MagicMock,
        mock_disk_scratch: mock.MagicMock,
        mock_is_sas: mock.MagicMock,
        mock_prep_img: mock.MagicMock,
        mock_upd_sku: mock.MagicMock,
        mock_submit: mock.MagicMock,
        mock_configure: mock.MagicMock,
        product_obj: Product,
        plan_summary_obj: PlanSummary,
        metadata_azure_obj: AzurePublishingMetadata,
        technical_config_obj: VMIPlanTechConfig,
        disk_version_obj: DiskVersion,
        azure_service: AzureService,
    ) -> None:
        metadata_azure_obj.overwrite = False
        metadata_azure_obj.keepdraft = True
        metadata_azure_obj.destination = "example-product/plan-1"
        metadata_azure_obj.disk_version = "2.0.0"
        mock_getpr_name.return_value = product_obj
        mock_getpl_name.return_value = plan_summary_obj
        mock_filter.return_value = [technical_config_obj]
        mock_is_sas.return_value = True
        mock_disk_scratch.return_value = disk_version_obj
        mock_upd_sku.return_value = technical_config_obj

        azure_service.publish(metadata_azure_obj)

        mock_getpr_name.assert_called_once_with(product_name="example-product")
        mock_getpl_name.assert_called_once_with(product=product_obj, plan_name="plan-1")
        mock_filter.assert_called_once_with(
            product=product_obj, resource="virtual-machine-plan-technical-configuration"
        )
        mock_is_sas.assert_called_once_with(
            technical_config_obj,
            metadata_azure_obj.image_path,
        )
        mock_prep_img.assert_not_called()
        mock_disk_scratch.assert_not_called()
        mock_upd_sku.assert_not_called()
        mock_configure.assert_not_called()
        mock_submit.assert_not_called()

    @mock.patch("cloudpub.ms_azure.AzureService.configure")
    @mock.patch("cloudpub.ms_azure.AzureService.submit_to_status")
    @mock.patch("cloudpub.ms_azure.service.prepare_vm_images")
    @mock.patch("cloudpub.ms_azure.service.is_sas_present")
    @mock.patch("cloudpub.ms_azure.service.create_disk_version_from_scratch")
    @mock.patch("cloudpub.ms_azure.AzureService.filter_product_resources")
    @mock.patch("cloudpub.ms_azure.AzureService.get_plan_by_name")
    @mock.patch("cloudpub.ms_azure.AzureService.get_product_by_name")
    def test_publish_novmimages(
        self,
        mock_getpr_name: mock.MagicMock,
        mock_getpl_name: mock.MagicMock,
        mock_filter: mock.MagicMock,
        mock_disk_scratch: mock.MagicMock,
        mock_is_sas: mock.MagicMock,
        mock_prep_img: mock.MagicMock,
        mock_submit: mock.MagicMock,
        mock_configure: mock.MagicMock,
        product_obj: Product,
        plan_summary_obj: PlanSummary,
        metadata_azure_obj: AzurePublishingMetadata,
        technical_config_obj: VMIPlanTechConfig,
        disk_version_obj: DiskVersion,
        azure_service: AzureService,
    ) -> None:
        metadata_azure_obj.overwrite = False
        metadata_azure_obj.keepdraft = True
        metadata_azure_obj.support_legacy = True
        metadata_azure_obj.destination = "example-product/plan-1"
        metadata_azure_obj.disk_version = "2.0.0"
        technical_config_obj.disk_versions[0].vm_images = []
        mock_getpr_name.return_value = product_obj
        mock_getpl_name.return_value = plan_summary_obj
        mock_filter.return_value = [technical_config_obj]
        mock_is_sas.return_value = False
        mock_disk_scratch.return_value = disk_version_obj
        expected_source = VMImageSource(
            source_type="sasUri",
            os_disk=OSDiskURI(uri=metadata_azure_obj.image_path).to_json(),
            data_disks=[],
        )
        expected_tech_config = deepcopy(technical_config_obj)
        expected_tech_config.disk_versions[0].vm_images.extend(
            [
                VMImageDefinition(
                    image_type=get_image_type_mapping(metadata_azure_obj.architecture, "V2"),
                    source=expected_source.to_json(),
                ),
                VMImageDefinition(
                    image_type=get_image_type_mapping(metadata_azure_obj.architecture, "V1"),
                    source=expected_source.to_json(),
                ),
            ]
        )

        azure_service.publish(metadata_azure_obj)

        mock_getpr_name.assert_called_once_with(product_name="example-product")
        mock_getpl_name.assert_called_once_with(product=product_obj, plan_name="plan-1")
        mock_filter.assert_called_once_with(
            product=product_obj, resource="virtual-machine-plan-technical-configuration"
        )
        mock_is_sas.assert_called_once_with(
            technical_config_obj,
            metadata_azure_obj.image_path,
        )
        mock_prep_img.assert_not_called()
        mock_disk_scratch.assert_not_called()
        mock_configure.assert_called_once_with(resource=expected_tech_config)
        mock_submit.assert_not_called()

    @mock.patch("cloudpub.ms_azure.AzureService.configure")
    @mock.patch("cloudpub.ms_azure.AzureService.submit_to_status")
    @mock.patch("cloudpub.ms_azure.service.prepare_vm_images")
    @mock.patch("cloudpub.ms_azure.service.is_sas_present")
    @mock.patch("cloudpub.ms_azure.service.create_disk_version_from_scratch")
    @mock.patch("cloudpub.ms_azure.AzureService.filter_product_resources")
    @mock.patch("cloudpub.ms_azure.AzureService.get_plan_by_name")
    @mock.patch("cloudpub.ms_azure.AzureService.get_product_by_name")
    def test_publish_disk_has_images(
        self,
        mock_getpr_name: mock.MagicMock,
        mock_getpl_name: mock.MagicMock,
        mock_filter: mock.MagicMock,
        mock_disk_scratch: mock.MagicMock,
        mock_is_sas: mock.MagicMock,
        mock_prep_img: mock.MagicMock,
        mock_submit: mock.MagicMock,
        mock_configure: mock.MagicMock,
        product_obj: Product,
        plan_summary_obj: PlanSummary,
        metadata_azure_obj: AzurePublishingMetadata,
        technical_config_obj: VMIPlanTechConfig,
        disk_version_obj: DiskVersion,
        azure_service: AzureService,
    ) -> None:
        metadata_azure_obj.overwrite = False
        metadata_azure_obj.keepdraft = True
        metadata_azure_obj.support_legacy = True
        metadata_azure_obj.destination = "example-product/plan-1"
        metadata_azure_obj.disk_version = "2.0.0"
        mock_getpr_name.return_value = product_obj
        mock_getpl_name.return_value = plan_summary_obj
        mock_filter.return_value = [technical_config_obj]
        mock_is_sas.return_value = False
        expected_source = VMImageSource(
            source_type="sasUri",
            os_disk=OSDiskURI(uri=metadata_azure_obj.image_path).to_json(),
            data_disks=[],
        )
        # Invert the VM images to have the Gen 2 first
        disk_version_obj.vm_images.pop(0)
        disk_version_obj.vm_images.append(
            VMImageDefinition(
                image_type=get_image_type_mapping(metadata_azure_obj.architecture, "V1"),
                source=expected_source.to_json(),
            )
        )

        mock_prep_img.return_value = deepcopy(
            disk_version_obj.vm_images
        )  # During submit it will pop the disk_versions
        technical_config_obj.disk_versions = [disk_version_obj]
        technical_config_obj.disk_versions = [disk_version_obj]

        azure_service.publish(metadata_azure_obj)
        mock_getpr_name.assert_called_once_with(product_name="example-product")
        mock_getpl_name.assert_called_once_with(product=product_obj, plan_name="plan-1")
        mock_filter.assert_called_once_with(
            product=product_obj, resource="virtual-machine-plan-technical-configuration"
        )
        mock_is_sas.assert_called_once_with(
            technical_config_obj,
            metadata_azure_obj.image_path,
        )
        mock_prep_img.assert_called_once_with(
            metadata=metadata_azure_obj,
            gen1=disk_version_obj.vm_images[1],
            gen2=disk_version_obj.vm_images[0],
            source=expected_source,
        )
        mock_disk_scratch.assert_not_called()
        mock_configure.assert_called_once_with(resource=technical_config_obj)
        mock_submit.assert_not_called()

    def test_is_submission_in_preview(
        self,
        submission_obj: ProductSubmission,
        azure_service: AzureService,
    ) -> None:
        # 1 - Initial state: submission is draft
        with mock.patch("cloudpub.ms_azure.AzureService.get_submission_state") as mock_substt:
            mock_substt.return_value = submission_obj
            res = azure_service._is_submission_in_preview(submission_obj)
            assert res is False
            mock_substt.assert_not_called()

        # 2 - Current state is "live"
        current = deepcopy(submission_obj)
        current.target.targetType = "preview"
        durable_id = "submission/ffffffff-ffff-ffff-ffff-ffffffffffff/1234"
        current.durable_id = durable_id
        submission_obj.durable_id = durable_id
        with mock.patch("cloudpub.ms_azure.AzureService.get_submission_state") as mock_substt:
            mock_substt.return_value = submission_obj
            res = azure_service._is_submission_in_preview(current)
            assert res is False
            mock_substt.assert_called_once_with(current.product_id, "live")

        # 3 - Current state is "preview" with an older published "live" state
        submission_obj.durable_id = "submission/ffffffff-ffff-ffff-ffff-ffffffffffff/4321"
        with mock.patch("cloudpub.ms_azure.AzureService.get_submission_state") as mock_substt:
            mock_substt.return_value = submission_obj
            res = azure_service._is_submission_in_preview(current)
            assert res is True
            mock_substt.assert_called_once_with(current.product_id, "live")

        # 4 - Current state is "preview" with no published content
        with mock.patch("cloudpub.ms_azure.AzureService.get_submission_state") as mock_substt:
            mock_substt.return_value = None
            res = azure_service._is_submission_in_preview(current)
            assert res is True
            mock_substt.assert_called_once_with(current.product_id, "live")

    @mock.patch("cloudpub.ms_azure.AzureService.configure")
    @mock.patch("cloudpub.ms_azure.AzureService.submit_to_status")
    @mock.patch("cloudpub.ms_azure.service.prepare_vm_images")
    @mock.patch("cloudpub.ms_azure.service.is_sas_present")
    @mock.patch("cloudpub.ms_azure.service.create_disk_version_from_scratch")
    @mock.patch("cloudpub.ms_azure.AzureService.filter_product_resources")
    @mock.patch("cloudpub.ms_azure.AzureService.get_plan_by_name")
    @mock.patch("cloudpub.ms_azure.AzureService.get_product_by_name")
    def test_publish_live(
        self,
        mock_getpr_name: mock.MagicMock,
        mock_getpl_name: mock.MagicMock,
        mock_filter: mock.MagicMock,
        mock_disk_scratch: mock.MagicMock,
        mock_is_sas: mock.MagicMock,
        mock_prep_img: mock.MagicMock,
        mock_submit: mock.MagicMock,
        mock_configure: mock.MagicMock,
        product_obj: Product,
        plan_summary_obj: PlanSummary,
        metadata_azure_obj: AzurePublishingMetadata,
        technical_config_obj: VMIPlanTechConfig,
        disk_version_obj: DiskVersion,
        submission_obj: ProductSubmission,
        azure_service: AzureService,
    ) -> None:
        metadata_azure_obj.overwrite = False
        metadata_azure_obj.keepdraft = False
        metadata_azure_obj.support_legacy = True
        metadata_azure_obj.destination = "example-product/plan-1"
        metadata_azure_obj.disk_version = "2.0.0"
        mock_getpr_name.return_value = product_obj
        mock_getpl_name.return_value = plan_summary_obj
        mock_filter.side_effect = [
            [technical_config_obj],
            [submission_obj],
        ]
        mock_is_sas.return_value = False
        expected_source = VMImageSource(
            source_type="sasUri",
            os_disk=OSDiskURI(uri=metadata_azure_obj.image_path).to_json(),
            data_disks=[],
        )
        disk_version_obj.vm_images[0] = VMImageDefinition(
            image_type=get_image_type_mapping(metadata_azure_obj.architecture, "V1"),
            source=expected_source.to_json(),
        )
        mock_prep_img.return_value = deepcopy(
            disk_version_obj.vm_images
        )  # During submit it will pop the disk_versions
        technical_config_obj.disk_versions = [disk_version_obj]
        technical_config_obj.disk_versions = [disk_version_obj]

        azure_service.publish(metadata_azure_obj)
        mock_getpr_name.assert_called_once_with(product_name="example-product")
        mock_getpl_name.assert_called_once_with(product=product_obj, plan_name="plan-1")
        filter_calls = [
            mock.call(product=product_obj, resource="virtual-machine-plan-technical-configuration"),
            mock.call(product=product_obj, resource="submission"),
        ]
        mock_filter.assert_has_calls(filter_calls)
        mock_is_sas.assert_called_once_with(
            technical_config_obj,
            metadata_azure_obj.image_path,
        )
        mock_prep_img.assert_called_once_with(
            metadata=metadata_azure_obj,
            gen1=disk_version_obj.vm_images[0],
            gen2=disk_version_obj.vm_images[1],
            source=expected_source,
        )
        mock_disk_scratch.assert_not_called()
        mock_configure.assert_called_once_with(resource=technical_config_obj)
        submit_calls = [
            mock.call(product_id=product_obj.id, status="preview"),
            mock.call(product_id=product_obj.id, status="live"),
        ]
        mock_submit.assert_has_calls(submit_calls)

    @mock.patch("cloudpub.ms_azure.AzureService.configure")
    @mock.patch("cloudpub.ms_azure.service.update_skus")
    @mock.patch("cloudpub.ms_azure.AzureService.submit_to_status")
    @mock.patch("cloudpub.ms_azure.service.create_disk_version_from_scratch")
    @mock.patch("cloudpub.ms_azure.AzureService.filter_product_resources")
    @mock.patch("cloudpub.ms_azure.AzureService._get_plan_tech_config")
    @mock.patch("cloudpub.ms_azure.AzureService.get_plan_by_name")
    @mock.patch("cloudpub.ms_azure.AzureService.get_product_by_name")
    def test_publish_deprecated(
        self,
        mock_getpr_name: mock.MagicMock,
        mock_getpl_name: mock.MagicMock,
        mock_get_tech: mock.MagicMock,
        mock_filter: mock.MagicMock,
        mock_disk_scratch: mock.MagicMock,
        mock_submit: mock.MagicMock,
        mock_upd8_skus: mock.MagicMock,
        mock_configure: mock.MagicMock,
        product_obj: Product,
        plan_summary_obj: PlanSummary,
        metadata_azure_obj: AzurePublishingMetadata,
        technical_config_obj: VMIPlanTechConfig,
        disk_version_obj: DiskVersion,
        submission_obj: ProductSubmission,
        gen1_image: Dict[str, Any],
        azure_service: AzureService,
    ) -> None:
        metadata_azure_obj.overwrite = False
        metadata_azure_obj.keepdraft = False
        metadata_azure_obj.support_legacy = True
        metadata_azure_obj.destination = "example-product/plan-1"
        metadata_azure_obj.disk_version = "2.0.0"

        # Create a deprecated disk_version which should be filtered out on result
        deprecated_dv = DiskVersion.from_json(
            {
                "versionNumber": "1.2.3",
                "vmImages": [gen1_image],
                "lifecycleState": "deprecated",
                "deprecationSchedule": {
                    "dateOffset": "P90D",
                    "date": "2023-10-12",
                    "reason": "other",
                },
            }
        )
        # Set the deprecated disk_version alongside a valid one
        technical_config_obj.disk_versions = [disk_version_obj, deprecated_dv]
        mock_get_tech.return_value = technical_config_obj

        # Assign the return value to create_disk_version_from_scratch and update_skus
        mock_disk_scratch.return_value = technical_config_obj.disk_versions[0]
        mock_upd8_skus.return_value = technical_config_obj.skus

        # Before publishing we should have the deprecated_dv
        assert deprecated_dv in technical_config_obj.disk_versions
        assert deprecated_dv.lifecycle_state is not None
        assert deprecated_dv.deprecation_schedule is not None

        azure_service.publish(metadata_azure_obj)

        # After publishing we should still have the deprecated_dv
        assert deprecated_dv in technical_config_obj.disk_versions
        assert deprecated_dv.lifecycle_state is None
        assert deprecated_dv.deprecation_schedule is None
