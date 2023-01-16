import logging
import urllib.parse as urlparse
from typing import Dict

log = logging.getLogger(__name__)


def get_url_params(url: str) -> Dict[str, str]:
    """
    Convert the URL into a dictionary of its parameters.

    Example:
        >>> url = "https://foo.com/bar?key1=value1&key2=value2"
        >>> get_url_params(url)
        {"key1": "value1", "key2": "value2"}

    Args:
        url (str)
            The full URL to parse the parameters
    Returns:
        dict: The parsed parameters
    """
    parser = urlparse.urlparse(url)
    params = parser.query
    # Check if URL has params
    if not params:
        return {}
    # The URL parameters separator is '&' while '=' is the key/value assignment for each param.
    return {k: v for k, v in (x.split("=") for x in params.split("&") if x)}


def join_url(*args: str) -> str:
    """Concatenate multiple URLs."""
    return "/".join(arg.strip("/") for arg in args)


def base_url(url: str) -> str:
    """Return the base URL."""
    parsed_url = urlparse.urlparse(url)
    return f"{parsed_url.scheme}://{parsed_url.netloc}"
