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

    @mock.patch("cloudpub.ms_azure.session.requests.Session")
    def test_login(
        self,
        session_mock: mock.MagicMock,
        auth_dict: Dict[str, str],
        token: Dict[str, str],
    ) -> None:
        session_mock.return_value.request.return_value = response(200)
        session_mock.return_value.post.return_value = response(200, token)

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

        session_mock.return_value.request.assert_called_once()
        session_mock.return_value.post.assert_called_once_with(
            login_url, headers=login_header, data=login_data, timeout=30
        )

    @pytest.mark.parametrize(
        'method,path,json',
        [
            ('get', 'foo', {}),
            ('post', "foo", {"foo": "bar"}),
            ('put', "foo", {"foo": "bar"}),
        ],
    )
    @mock.patch("cloudpub.ms_azure.session.requests.Session")
    def test_request(
        self,
        mock_session: mock.MagicMock,
        method: str,
        path: str,
        json: Dict[str, Any],
        auth_dict: Dict[str, str],
        token: Dict[str, str],
    ) -> None:
        # for PartnerPortalSession._login
        mock_session.return_value.post.return_value = response(200, token)

        url = join_url("https://graph.microsoft.com/rp/product-ingestion", path)
        put_headers = {
            'Accept': 'application/json',
            'Authorization': f'Bearer {token["access_token"]}',
        }
        put_param = {'$version': auth_dict['AZURE_SCHEMA_VERSION']}

        session = PartnerPortalSession.make_graph_api_session(
            auth_dict, schema_version=auth_dict['AZURE_SCHEMA_VERSION']
        )

        if json:
            getattr(session, method)(path, json)
            mock_session.return_value.request.assert_called_once_with(
                method, url=url, params=put_param, headers=put_headers, json={"foo": "bar"}
            )
        else:
            getattr(session, method)(path)
            mock_session.return_value.request.assert_called_once_with(
                method, url=url, params=put_param, headers=put_headers
            )
