import logging
import urllib.parse as urlparse
from typing import Dict

log = logging.getLogger(__name__)


def get_url_params(url: str) -> Dict[str, str]:
    """
    Convert the URL into a dictionary of its parameters.

    Example:
        >>> url = "https://foo.com/bar?key1=value1&key2=value2"
        >>> self._parse_next_link(url)
        {"key1": "value1", "key2": "value2"}

    Args:
        next_link (str)
            The full next link URL
    Returns:
        dict: The parsed parameters
    """
    link_params = url.split("?")
    # Check if URL has params
    if len(link_params) == 1:  # Just the URL, no params
        return {}
    # We don't want to get the URL, just the params
    params = link_params[-1]
    # The URL parameters separator is '&' while '=' is the key/value assignment for each param.
    return {k: v for k, v in (x.split("=") for x in params.split("&") if x)}


def join_url(*args: str) -> str:
    """Concatenate multiple URLs."""
    return "/".join(arg.strip("/") for arg in args)


def base_url(url: str) -> str:
    """Return the base URL."""
    parsed_url = urlparse.urlparse(url)
    return f"{parsed_url.scheme}://{parsed_url.netloc}"
