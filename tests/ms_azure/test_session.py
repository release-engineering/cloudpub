from datetime import datetime, timedelta
from typing import Any, Dict
from unittest import mock

import pytest
from httmock import response

from cloudpub.ms_azure.session import AccessToken, PartnerPortalSession
from cloudpub.utils import join_url


class TestAccessToken:
    def test_access_token(self, token: Dict[str, str]) -> None:
        at = AccessToken(token)

        # Check token value
        assert at.access_token == token["access_token"]

        # Check expiration
        assert at.expires_on == datetime.fromtimestamp(int(token["expires_on"]))
        assert at.is_expired()
        future_time = datetime.now() + timedelta(minutes=30)
        at.expires_on = future_time
        assert not at.is_expired()


class TestPartnerPortalSession:
    def test_make_session(self, auth_dict: Dict[str, str]) -> None:
        session = PartnerPortalSession.make_graph_api_session(auth_keys=auth_dict)

        assert isinstance(session, PartnerPortalSession)
        assert session.resource == "https://graph.microsoft.com"

    def test_make_session_invalid_auth_dict(self, auth_dict: Dict[str, str]) -> None:
        keys = [
            "AZURE_PUBLISHER_NAME",
            "AZURE_CLIENT_ID",
            "AZURE_TENANT_ID",
            "AZURE_API_SECRET",
        ]

        err_msg = "The key/value for \"{key}\" must be set."

        for key in keys:
            expected_msg = err_msg.format(key=key)
            copyauth_dict = auth_dict.copy()
            del copyauth_dict[key]
            with pytest.raises(ValueError, match=expected_msg):
                PartnerPortalSession.make_graph_api_session(copyauth_dict)

    @mock.patch("cloudpub.ms_azure.session.requests.post")
    @mock.patch("cloudpub.ms_azure.session.requests.request")
    def test_login(
        self,
        req_mock: mock.MagicMock,
        post_mock: mock.MagicMock,
        auth_dict: Dict[str, str],
        token: Dict[str, str],
    ) -> None:
        req_mock.return_value = response(200)
        post_mock.return_value = response(200, token)

        tenant = auth_dict['AZURE_TENANT_ID']
        login_url = f"https://login.microsoftonline.com/{tenant}/oauth2/token"
        login_header = {"Accept": "application/json"}
        login_data = {
            "resource": "https://graph.microsoft.com",
            "client_id": auth_dict["AZURE_CLIENT_ID"],
            "client_secret": auth_dict["AZURE_API_SECRET"],
            "grant_type": "client_credentials",
        }

        session = PartnerPortalSession.make_graph_api_session(auth_dict)
        session.get("/foo")

        req_mock.assert_called_once()
        post_mock.assert_called_once_with(login_url, headers=login_header, data=login_data)

    @pytest.mark.parametrize(
        'method,path,json',
        [
            ('get', 'foo', {}),
            ('post', "foo", {"foo": "bar"}),
            ('put', "foo", {"foo": "bar"}),
        ],
    )
    @mock.patch("cloudpub.ms_azure.session.requests")
    def test_request(
        self,
        mock_req: mock.MagicMock,
        method: str,
        path: str,
        json: Dict[str, Any],
        auth_dict: Dict[str, str],
        token: Dict[str, str],
    ) -> None:
        mock_req.post.return_value = response(200, token)  # for PartnerPortalSession._login

        url = join_url("https://graph.microsoft.com/rp/product-ingestion", path)
        put_headers = {
            'Accept': 'application/json',
            'Authorization': f'Bearer {token["access_token"]}',
        }
        put_param = {'$version': auth_dict['AZURE_API_VERSION']}

        session = PartnerPortalSession.make_graph_api_session(auth_dict)

        if json:
            getattr(session, method)(path, json)
            mock_req.request.assert_called_once_with(
                method, url=url, params=put_param, headers=put_headers, json={"foo": "bar"}
            )
        else:
            getattr(session, method)(path)
            mock_req.request.assert_called_once_with(
                method, url=url, params=put_param, headers=put_headers
            )
