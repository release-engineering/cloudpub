# SPDX-License-Identifier: GPL-3.0-or-later
import logging
from abc import ABC, abstractmethod
from typing import NoReturn

from requests import HTTPError, Response

from cloudpub.error import NotFoundError

log = logging.getLogger(__name__)


class PublishingMetadata:
    """A collection of necessary information for associating a VM Image with a product."""

    def __init__(
        self,
        image_path: str,
        architecture: str,
        destination: str,
        overwrite: bool = False,
        keepdraft: bool = False,
    ) -> None:
        """
        Create an instanece of PublishingMetadata.

        Args:
        image_path (str)
            The image URL or ID to be associated with a product listing
        architecture (str)
            The VM Image architecture
        destination (str)
            The product listing to update with the given ``image_path``
        overwrite (bool, optional)
            Whether to overwrite the product listing with the given image or not (append only).
            This defaults to `False`.
        keepdraft (bool, optional):
            Whether to just associate the VM Image with the destination but avoid publishing or not.
            When set to `False` it will publish the content as GA.
            This defaults to `True`.
        """
        self.image_path = image_path
        self.architecture = architecture
        self.destination = destination
        self.overwrite = overwrite
        self.keepdraft = keepdraft
        self.__validate()

    def __validate(self):
        mandatory = [
            "image_path",
            "architecture",
            "destination",
        ]
        for param in mandatory:
            if not getattr(self, param, None):
                raise ValueError(f"The parameter \"{param}\" must not be None.")


class BaseService(ABC):
    """Base class for all cloud provider services."""

    @staticmethod
    def _raise_error(exception: Exception, message=str) -> NoReturn:
        """
        Log and raise an error.

        Args
            exception (Exception)
                The exception type to raise.
            message (str)
                The error message.
        Raises:
            Exception: the requested exception with the incoming message.
        """
        log.error(message)
        raise exception(message)

    def _raise_for_status(self, response: Response) -> None:
        """
        Log and raise a requests.Response error if any.

        Args
            response (requests.Response)
                The response object
        Raises:
            NotFoundError: when the `response.status_code` is 404
            HTTPError: when raised by `requests.Response.raise_for_status`.
        """
        try:
            if response.status_code == 404:
                self._raise_error(NotFoundError, "Resource not found.")
            response.raise_for_status()
        except HTTPError:
            self._raise_error(HTTPError, f"Response content:\n{response.text}")

    @abstractmethod
    def publish(self, metadata: PublishingMetadata):
        """
        Associate a VM image with a given product listing (destination) and publish it.

        Args:
            metadata (PublishingMetadata): metadata for the VM image publishing.
        """
