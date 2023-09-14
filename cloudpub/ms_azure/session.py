# SPDX-License-Identifier: GPL-3.0-or-later
import logging
from datetime import datetime
from typing import Any, Dict, Optional

import requests
from requests.adapters import HTTPAdapter, Retry

from cloudpub.utils import base_url, join_url

log = logging.getLogger(__name__)


class AccessToken:
    """Represent the Microsoft API Authorization token."""

    def __init__(self, json: Dict[str, str]):
        """
        Create a new AccessToken object.

        Args:
            json (dict)
                The login response with from Microsoft.
        """
        self.expires_on = datetime.fromtimestamp(int(json["expires_on"]))
        self.access_token = json["access_token"]
        log.debug(f"Obtained token with expiration date on {self.expires_on}")

    def is_expired(self) -> bool:
        """Return True if the token is expired and False otherwise."""
        if datetime.now() > self.expires_on:
            return True
        return False


class PartnerPortalSession:
    """
    Implement the session for Azure API using the Active Directory credentials.

    It's expected to be instantiated through the factory method
    :meth:`~PartnerPortalSession.make_graph_api_session`.
    """

    LOGIN_URL_TMPL = "https://login.microsoftonline.com/{AZURE_TENANT_ID}/oauth2/token"

    def __init__(
        self,
        auth_keys: Dict[str, str],
        prefix_url: str,
        mandatory_params: Optional[Dict[str, str]] = None,
        **kwargs,
    ):
        """
        Create a new PartnerPortalSession object.

        Args:
            auth_keys (dict)
                Dictionary with the required secrets to login into a Microsoft API.
            prefix_url (str)
                The API prefix URL.
            mandatory_params (dict, optional)
                Mandatory parameters to pass for each API request, if any.
        """
        self.auth_keys = self._validate_auth_keys(auth_keys)
        self._prefix_url = prefix_url
        self.resource = base_url(prefix_url)
        self._mandatory_params = mandatory_params
        self._token: Optional[AccessToken] = None
        self.publisher = auth_keys["AZURE_PUBLISHER_NAME"]
        self._additional_args = kwargs
        self.session = requests.Session()
        total_retries = kwargs.pop("total_retries", 5)
        backoff_factor = kwargs.pop("backoff_factor", 1)
        status_forcelist = kwargs.pop("status_forcelist", tuple(range(500, 512)))
        retries = Retry(
            total=total_retries,
            backoff_factor=backoff_factor,
            status_forcelist=status_forcelist,
        )
        self.session.mount('https://', HTTPAdapter(max_retries=retries))

    @classmethod
    def make_graph_api_session(
        cls, auth_keys: Dict[str, Any], schema_version: str = '2022-03-01-preview3'
    ) -> 'PartnerPortalSession':
        """
        Create a PartnerPortalSession for the Microsoft Graph API.

        Args:
            auth_keys (dict)
                Dictionary with the required secrets to login into a Microsoft API.
            api_version (str)
                The schema version to use on each request.
                Defaults to ``2022-03-01-preview3``.
        Raises:
            ValueError on authentication failure.
        """
        log.debug("Creating a session with Azure Private Offer API")
        mparams = {'$version': schema_version}
        prefix_url = "https://graph.microsoft.com/rp/product-ingestion"
        return cls(auth_keys=auth_keys, prefix_url=prefix_url, mandatory_params=mparams)

    @staticmethod
    def _validate_auth_keys(auth_keys: Dict[str, str]) -> Dict[str, str]:
        """Validate whether auth_keys contains all required keys."""
        mandatory_keys = [
            "AZURE_PUBLISHER_NAME",
            "AZURE_CLIENT_ID",
            "AZURE_TENANT_ID",
            "AZURE_API_SECRET",
        ]
        for key in mandatory_keys:
            log.debug(f"Validating mandatory key \"{key}\"")
            if key not in auth_keys.keys() or not auth_keys.get(key):
                err_msg = f'The key/value for "{key}" must be set.'
                log.error(err_msg)
                raise ValueError(err_msg)
        return auth_keys

    def _login(self) -> AccessToken:
        """Retrieve the authentication token from Microsoft."""
        log.info("Retrieving the bearer token from Microsoft")
        url = self.LOGIN_URL_TMPL.format(**self.auth_keys)

        headers = {
            "Accept": "application/json",
        }

        data = {
            "resource": self.resource,
            "client_id": self.auth_keys["AZURE_CLIENT_ID"],
            "client_secret": self.auth_keys["AZURE_API_SECRET"],
            "grant_type": "client_credentials",
        }

        resp = self.session.post(url, headers=headers, data=data, timeout=30)
        resp.raise_for_status()
        return AccessToken(resp.json())

    def _get_token(self) -> str:
        """Request a new bearer token from Microsoft."""
        if not self._token or self._token.is_expired():
            self._token = self._login()
        log.debug("Serving the bearer token")
        return self._token.access_token

    def _request(
        self, method: str, path: str, params: Optional[Dict[str, Any]] = None, **kwargs: Any
    ) -> requests.Response:
        """Execute a generic API request."""
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._get_token()}",
        }

        if self._mandatory_params:
            if not params:
                params = {}
            params.update(self._mandatory_params)

        log.info(f"Sending a {method} request to {path}")
        formatted_url = self._prefix_url.format(**self.auth_keys)
        url = join_url(formatted_url, path)
        return self.session.request(method, url=url, params=params, headers=headers, **kwargs)

    def get(self, path: str, **kwargs: Any) -> requests.Response:
        """Execute an API GET request."""
        return self._request("get", path, **kwargs)

    def post(self, path: str, json: Dict[str, Any], **kwargs: Any) -> requests.Response:
        """Execute an API POST request."""
        return self._request("post", path, json=json, **kwargs)

    def put(self, path: str, json: Dict[str, Any], **kwargs: Any) -> requests.Response:
        """Execute an API PUT request."""
        return self._request("put", path, json=json, **kwargs)
