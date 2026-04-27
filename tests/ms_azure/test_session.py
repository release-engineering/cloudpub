import importlib
import os
from datetime import datetime, timedelta
from typing import Any, Dict, cast
from unittest import mock

import pytest
import requests
from httmock import response
from requests import Response as RequestsResponse

from cloudpub.ms_azure.session import (
    AZURE_SESSION_TIMEOUT,
    AZURE_TOTAL_RETRIES,
    AccessToken,
    PartnerPortalSession,
    _should_retry_request_http_error,
)
from cloudpub.utils import join_url


class TestShouldRetryRequestHttpError:
    def test_returns_false_for_non_http_error(self) -> None:
        assert not _should_retry_request_http_error(ValueError('not http'))

    def test_returns_false_when_http_error_has_no_response(self) -> None:
        exc = requests.exceptions.HTTPError(response=cast(RequestsResponse, None))
        assert exc.response is None
        assert not _should_retry_request_http_error(exc)


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
            login_url, headers=login_header, data=login_data, timeout=AZURE_SESSION_TIMEOUT
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
                method,
                url=url,
                params=put_param,
                headers=put_headers,
                json={"foo": "bar"},
                timeout=AZURE_SESSION_TIMEOUT,
            )
        else:
            getattr(session, method)(path)
            mock_session.return_value.request.assert_called_once_with(
                method,
                url=url,
                params=put_param,
                headers=put_headers,
                timeout=AZURE_SESSION_TIMEOUT,
            )

    @mock.patch("cloudpub.ms_azure.session.requests.Session")
    def test_azure_session_timeout_from_env(
        self,
        session_mock: mock.MagicMock,
        auth_dict: Dict[str, str],
        token: Dict[str, str],
    ) -> None:
        """AZURE_SESSION_TIMEOUT from the environment is used for login and API calls."""
        import cloudpub.ms_azure.session as session_mod

        env_timeout = "37.5"
        try:
            with mock.patch.dict(os.environ, {"AZURE_SESSION_TIMEOUT": env_timeout}, clear=False):
                importlib.reload(session_mod)
                assert session_mod.AZURE_SESSION_TIMEOUT == float(env_timeout)

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

                session = session_mod.PartnerPortalSession.make_graph_api_session(
                    auth_dict, schema_version=auth_dict['AZURE_SCHEMA_VERSION']
                )
                session.get("/foo")

                session_mock.return_value.post.assert_called_once_with(
                    login_url,
                    headers=login_header,
                    data=login_data,
                    timeout=float(env_timeout),
                )
                session_mock.return_value.request.assert_called_once_with(
                    "get",
                    url=join_url("https://graph.microsoft.com/rp/product-ingestion", "foo"),
                    params={'$version': auth_dict['AZURE_SCHEMA_VERSION']},
                    headers={
                        'Accept': 'application/json',
                        'Authorization': f'Bearer {token["access_token"]}',
                    },
                    timeout=float(env_timeout),
                )
        finally:
            importlib.reload(session_mod)

    @pytest.mark.parametrize(
        'method,path,body',
        [
            ('get', 'foo', None),
            ('post', "foo", {"foo": "bar"}),
            ('put', "foo", {"foo": "bar"}),
        ],
    )
    @mock.patch("cloudpub.ms_azure.session.requests.Session")
    def test_request_respects_explicit_timeout(
        self,
        mock_session: mock.MagicMock,
        method: str,
        path: str,
        body: Dict[str, Any] | None,
        auth_dict: Dict[str, str],
        token: Dict[str, str],
    ) -> None:
        """Explicit timeout= on get/post/put overrides AZURE_SESSION_TIMEOUT."""
        mock_session.return_value.post.return_value = response(200, token)

        url = join_url("https://graph.microsoft.com/rp/product-ingestion", path)
        put_headers = {
            'Accept': 'application/json',
            'Authorization': f'Bearer {token["access_token"]}',
        }
        put_param = {'$version': auth_dict['AZURE_SCHEMA_VERSION']}
        explicit_timeout = 88.0

        session = PartnerPortalSession.make_graph_api_session(
            auth_dict, schema_version=auth_dict['AZURE_SCHEMA_VERSION']
        )

        if body is not None:
            getattr(session, method)(path, body, timeout=explicit_timeout)
            mock_session.return_value.request.assert_called_once_with(
                method,
                url=url,
                params=put_param,
                headers=put_headers,
                json={"foo": "bar"},
                timeout=explicit_timeout,
            )
        else:
            getattr(session, method)(path, timeout=explicit_timeout)
            mock_session.return_value.request.assert_called_once_with(
                method,
                url=url,
                params=put_param,
                headers=put_headers,
                timeout=explicit_timeout,
            )

    @staticmethod
    def _http_error(status_code: int = 408) -> requests.exceptions.HTTPError:
        resp = requests.Response()
        resp.status_code = status_code
        return requests.exceptions.HTTPError(response=resp)

    @mock.patch('time.sleep')
    @mock.patch("cloudpub.ms_azure.session.requests.Session")
    def test_request_retries_on_http_error_then_succeeds(
        self,
        mock_session: mock.MagicMock,
        _sleep: mock.MagicMock,
        auth_dict: Dict[str, str],
        token: Dict[str, str],
    ) -> None:
        """Transient HTTPError from the underlying request is retried; success returns normally."""
        mock_session.return_value.post.return_value = response(200, token)
        ok = response(200, {})
        err = self._http_error()
        mock_session.return_value.request.side_effect = [err, err, ok]

        session = PartnerPortalSession.make_graph_api_session(
            auth_dict, schema_version=auth_dict['AZURE_SCHEMA_VERSION']
        )
        out = session.get('/foo')

        assert out is ok
        assert mock_session.return_value.request.call_count == 3

    @mock.patch('time.sleep')
    @mock.patch("cloudpub.ms_azure.session.requests.Session")
    def test_request_stops_after_max_retries_on_persistent_http_error(
        self,
        mock_session: mock.MagicMock,
        _sleep: mock.MagicMock,
        auth_dict: Dict[str, str],
        token: Dict[str, str],
    ) -> None:
        """The HTTPError on every attempt stops after AZURE_TOTAL_RETRIES and reraises."""
        mock_session.return_value.post.return_value = response(200, token)
        err = self._http_error(500)
        mock_session.return_value.request.side_effect = err

        session = PartnerPortalSession.make_graph_api_session(
            auth_dict, schema_version=auth_dict['AZURE_SCHEMA_VERSION']
        )
        with pytest.raises(requests.exceptions.HTTPError) as exc_info:
            session.get('/foo')

        assert exc_info.value is err
        assert mock_session.return_value.request.call_count == AZURE_TOTAL_RETRIES

    @pytest.mark.parametrize('status', [400, 407, 513])
    @mock.patch('time.sleep')
    @mock.patch("cloudpub.ms_azure.session.requests.Session")
    def test_request_does_not_retry_http_error_outside_status_range(
        self,
        mock_session: mock.MagicMock,
        _sleep: mock.MagicMock,
        status: int,
        auth_dict: Dict[str, str],
        token: Dict[str, str],
    ) -> None:
        """The HTTPError outside 408–512 is not retried."""
        mock_session.return_value.post.return_value = response(200, token)
        err = self._http_error(status)
        mock_session.return_value.request.side_effect = err

        session = PartnerPortalSession.make_graph_api_session(
            auth_dict, schema_version=auth_dict['AZURE_SCHEMA_VERSION']
        )
        with pytest.raises(requests.exceptions.HTTPError) as exc_info:
            session.get('/foo')

        assert exc_info.value is err
        assert mock_session.return_value.request.call_count == 1

    @mock.patch('time.sleep')
    @mock.patch("cloudpub.ms_azure.session.requests.Session")
    def test_request_does_not_retry_http_error_without_response(
        self,
        mock_session: mock.MagicMock,
        _sleep: mock.MagicMock,
        auth_dict: Dict[str, str],
        token: Dict[str, str],
    ) -> None:
        """The HTTPError with no attached response is not retried (cannot map to status range)."""
        mock_session.return_value.post.return_value = response(200, token)
        err = requests.exceptions.HTTPError(response=cast(RequestsResponse, None))
        assert err.response is None
        mock_session.return_value.request.side_effect = err

        session = PartnerPortalSession.make_graph_api_session(
            auth_dict, schema_version=auth_dict['AZURE_SCHEMA_VERSION']
        )
        with pytest.raises(requests.exceptions.HTTPError) as exc_info:
            session.get('/foo')

        assert exc_info.value is err
        assert mock_session.return_value.request.call_count == 1

    @pytest.mark.parametrize(
        'error',
        [
            ValueError('not an http error'),
            requests.exceptions.ConnectionError('connection refused'),
        ],
    )
    @mock.patch('time.sleep')
    @mock.patch("cloudpub.ms_azure.session.requests.Session")
    def test_request_does_not_retry_non_http_error(
        self,
        mock_session: mock.MagicMock,
        _sleep: mock.MagicMock,
        error: Exception,
        auth_dict: Dict[str, str],
        token: Dict[str, str],
    ) -> None:
        """The retry policy only applies to HTTPError; other exceptions are not retried."""
        mock_session.return_value.post.return_value = response(200, token)
        mock_session.return_value.request.side_effect = error

        session = PartnerPortalSession.make_graph_api_session(
            auth_dict, schema_version=auth_dict['AZURE_SCHEMA_VERSION']
        )
        with pytest.raises(type(error)) as exc_info:
            session.get('/foo')

        assert exc_info.value is error
        assert mock_session.return_value.request.call_count == 1

    @mock.patch('time.sleep')
    @mock.patch("cloudpub.ms_azure.session.requests.Session")
    def test_request_retries_after_raise_for_status_on_transient_http_status(
        self,
        mock_session: mock.MagicMock,
        _sleep: mock.MagicMock,
        auth_dict: Dict[str, str],
        token: Dict[str, str],
    ) -> None:
        """503 from the transport + default raise_for_status triggers retry, then succeeds."""
        mock_session.return_value.post.return_value = response(200, token)
        err_503 = response(503, {})
        ok = response(200, {})
        mock_session.return_value.request.side_effect = [err_503, err_503, ok]

        session = PartnerPortalSession.make_graph_api_session(
            auth_dict, schema_version=auth_dict['AZURE_SCHEMA_VERSION']
        )
        out = session.get('/foo')

        assert out is ok
        assert mock_session.return_value.request.call_count == 3

    @mock.patch('time.sleep')
    @mock.patch("cloudpub.ms_azure.session.requests.Session")
    def test_request_retries_after_raise_for_status_on_status_512_upper_bound(
        self,
        mock_session: mock.MagicMock,
        _sleep: mock.MagicMock,
        auth_dict: Dict[str, str],
        token: Dict[str, str],
    ) -> None:
        """512 is the inclusive upper bound of retriable statuses; first attempt is retried."""
        mock_session.return_value.post.return_value = response(200, token)
        err_512 = response(512, {})
        ok = response(200, {})
        mock_session.return_value.request.side_effect = [err_512, ok]

        session = PartnerPortalSession.make_graph_api_session(
            auth_dict, schema_version=auth_dict['AZURE_SCHEMA_VERSION']
        )
        out = session.get('/foo')

        assert out is ok
        assert out.status_code == 200
        assert mock_session.return_value.request.call_count == 2
