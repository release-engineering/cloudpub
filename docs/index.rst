.. cloudpub documentation master file, created by
   sphinx-quickstart on Thu Jan 12 16:24:17 2023.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

CloudPub
========

A library for publishing product listings on various clouds.

Cloud Providers
---------------

.. toctree::
   :maxdepth: 3
   :caption: Contents:

   cloud_providers/base
   cloud_providers/azure


Quick Start
-----------

Install cloudpub:

::

    pip install .

Once installed it's possible to use the cloud provider classes to associate an image with a product
and publish it.

Example for Azure:

.. code-block:: python

    from cloudpub.ms_azure import AzurePublishingMetadata, AzureService 

    # Instantiate the AzurePublishingMetadata with the required information
    metadata = AzurePublishingMetadata(
      destination="product-example/plan-example",
      sas_uri="https://foo.com/bar/image.vhd",
      disk_version="2.1.0",
      keepdraft=False,  # When `False` it means publish to live.
    )

    # Associate the image with the destination and publish the changes
    svc = AzureService(credentials={...})
    svc.publish(metadata)
