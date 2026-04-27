import importlib
import os
import threading
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, List, Tuple
from unittest import mock

import pytest
from httmock import response
from requests.adapters import HTTPAdapter

from cloudpub.ms_azure.session import AZURE_SESSION_TIMEOUT, AccessToken, PartnerPortalSession
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


def _start_local_server(handler: type[BaseHTTPRequestHandler]) -> tuple[HTTPServer, int]:
    server = HTTPServer(("127.0.0.1", 0), handler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, port


def _sequential_http_handler(
    responses: List[Tuple[int, bytes | None]],
) -> tuple[type[BaseHTTPRequestHandler], List[int]]:
    """Build a handler that returns each (status, body) in order for GET/PUT."""
    call_count = [0]

    class Handler(BaseHTTPRequestHandler):
        def respond(self) -> None:
            call_count[0] += 1
            idx = call_count[0] - 1
            status, body = responses[idx] if idx < len(responses) else responses[-1]
            self.send_response(status)
            if body is not None:
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
            else:
                self.end_headers()

        do_GET = respond
        do_PUT = respond
        do_POST = respond

        def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003
            pass

    return Handler, call_count


def _partner_portal_over_http(
    auth_dict: Dict[str, str],
    port: int,
    **session_kwargs: Any,
) -> PartnerPortalSession:
    """Build a PartnerPortalSession that targets a local HTTP server using the retry adapter."""
    session = PartnerPortalSession(
        auth_keys=auth_dict,
        prefix_url=f"http://127.0.0.1:{port}/rp/product-ingestion",
        mandatory_params={"$version": auth_dict["AZURE_SCHEMA_VERSION"]},
        backoff_factor=0,
        **session_kwargs,
    )
    # __init__ only mounts https://; mirror the same Retry policy for http used in tests
    session.session.mount("http://", session.session.get_adapter("https://"))
    return session


class TestPartnerPortalSessionRetries:
    """
    Exercise PartnerPortalSession urllib3 Retry behavior via real HTTP transport.

    PartnerPortalSession mounts urllib3 Retry on https:// for status codes in
    ``range(500, 512)`` (500–511). These tests exercise the real transport; the
    ``requests_mock`` library patches ``Session.send`` and would skip urllib3 retries.
    """

    def test_default_status_forcelist_is_500_through_511(self, auth_dict: Dict[str, str]) -> None:
        p = PartnerPortalSession(
            auth_keys=auth_dict,
            prefix_url="https://graph.microsoft.com/rp/product-ingestion",
            mandatory_params={"$version": auth_dict["AZURE_SCHEMA_VERSION"]},
        )
        adapter = p.session.get_adapter("https://")
        assert isinstance(adapter, HTTPAdapter)
        retry = adapter.max_retries
        assert retry.total == 5
        assert retry.backoff_factor == 1
        assert retry.status_forcelist == tuple(range(500, 512))

    @pytest.mark.parametrize(
        "first_status",
        [500, 503, 511],
    )
    def test_get_retries_on_forcelist_status_then_succeeds(
        self,
        auth_dict: Dict[str, str],
        first_status: int,
    ) -> None:
        ok = b'{"ok": true}'
        handler_cls, call_count = _sequential_http_handler(
            [(first_status, None), (200, ok)],
        )
        server, port = _start_local_server(handler_cls)
        try:
            s = _partner_portal_over_http(auth_dict, port)
            with mock.patch.object(PartnerPortalSession, "_get_token", return_value="t"):
                r = s.get("foo")
            assert r.status_code == 200
            assert r.json() == {"ok": True}
            assert call_count[0] == 2
        finally:
            server.shutdown()
            server.server_close()

    def test_put_retries_on_forcelist_status_then_succeeds(self, auth_dict: Dict[str, str]) -> None:
        ok = b'{"saved": true}'
        handler_cls, call_count = _sequential_http_handler([(503, None), (200, ok)])
        server, port = _start_local_server(handler_cls)
        try:
            s = _partner_portal_over_http(auth_dict, port)
            with mock.patch.object(PartnerPortalSession, "_get_token", return_value="t"):
                r = s.put("foo", json={"a": 1})
            assert r.status_code == 200
            assert call_count[0] == 2
        finally:
            server.shutdown()
            server.server_close()

    @pytest.mark.parametrize(
        "status",
        [403, 407, 408, 429],
    )
    def test_get_does_not_retry_status_outside_forcelist(
        self, auth_dict: Dict[str, str], status: int
    ) -> None:
        handler_cls, call_count = _sequential_http_handler([(status, None), (200, b"{}")])
        server, port = _start_local_server(handler_cls)
        try:
            s = _partner_portal_over_http(auth_dict, port)
            with mock.patch.object(PartnerPortalSession, "_get_token", return_value="t"):
                r = s.get("foo")
            assert r.status_code == status
            assert call_count[0] == 1
        finally:
            server.shutdown()
            server.server_close()

    def test_get_does_not_retry_512(self, auth_dict: Dict[str, str]) -> None:
        """512 is not in ``range(500, 512)`` (upper bound is 511)."""
        handler_cls, call_count = _sequential_http_handler([(512, None), (200, b"{}")])
        server, port = _start_local_server(handler_cls)
        try:
            s = _partner_portal_over_http(auth_dict, port)
            with mock.patch.object(PartnerPortalSession, "_get_token", return_value="t"):
                r = s.get("foo")
            assert r.status_code == 512
            assert call_count[0] == 1
        finally:
            server.shutdown()
            server.server_close()

    def test_urllib3_retry_forcelist_covers_500_through_511(
        self,
    ) -> None:
        """Match ``status_forcelist=tuple(range(500, 512))`` (excludes 512)."""
        from urllib3.util.retry import Retry

        r = Retry(
            total=5,
            backoff_factor=1,
            status_forcelist=tuple(range(500, 512)),
        )
        for code in range(500, 512):
            assert r.is_retry(method="GET", status_code=code)
        assert not r.is_retry(method="GET", status_code=407)
        assert not r.is_retry(method="GET", status_code=408)
        assert not r.is_retry(method="GET", status_code=429)
        assert not r.is_retry(method="GET", status_code=499)
        assert not r.is_retry(method="GET", status_code=512)

    def test_post_does_not_retry_by_default_urllib3(self, auth_dict: Dict[str, str]) -> None:
        """POST is not in urllib3 Retry default allowed_methods; status 500 is not retried."""
        handler_cls, call_count = _sequential_http_handler(
            [(500, None), (200, b"{}")],
        )
        server, port = _start_local_server(handler_cls)
        try:
            s = _partner_portal_over_http(auth_dict, port)
            with mock.patch.object(PartnerPortalSession, "_get_token", return_value="t"):
                r = s.post("foo", json={})
            assert r.status_code == 500
            assert call_count[0] == 1
        finally:
            server.shutdown()
            server.server_close()
