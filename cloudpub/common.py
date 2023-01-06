# SPDX-License-Identifier: GPL-3.0-or-later
import logging
from abc import ABCMeta, abstractmethod

log = logging.getLogger(__name__)


class PublishingMetadata:
    """
    A collection of metadata necessary for associating an existing VM Image into a product listing
    and publishing it.

    Args:
        image_path (str)
            The image URL or ID to be associated with a product listing
        architecture (str)
            The VM Image architecture
        destination (str)
            The product listing to update with the given ``image_path``
        overwrite (bool)
            Whether to overwrite the product listing with the given image or not (append only).
        keepdraft (bool):
            Whether to just associate the VM Image with the destination but avoid publishing or not.
            When set to ``False`` it will publish the content as GA.
    """

    def __init__(
        self, image_path: str, architecture: str, destination: str, overwrite: bool, keepdraft: bool
    ) -> None:
        self.image_path = image_path
        self.architecture = architecture
        self.destination = destination
        self.overwrite = overwrite
        self.keepdraft = keepdraft


class BaseService(ABCMeta):
    """
    Base class for all cloud provider services.
    """

    @abstractmethod
    def publish(self, metadata: PublishingMetadata):
        """
        Associate a VM image with a given product listing (destination) and publish it.

        Args:
            metadata (PublishingMetadata): metadata for the VM image publishing.
        """
        raise NotImplementedError
