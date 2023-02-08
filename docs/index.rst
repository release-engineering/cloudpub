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
   cloud_providers/aws


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

Example for AWS:

.. code-block:: python

    from cloudpub.ms_azure import AWSVersionMetadata, AWSProductService
    from cloudpub.models.aws import VersionMapping

    # Fill out the version metadata

    example_version_mapping = VersionMapping({
      "Version": {
        "VersionTitle": "example-changeset",
        "ReleaseNotes": "https://access.redhat.com/foo/bar"
      },
      "DeliveryOptions": [
      {
        "Details": {
          "AmiDeliveryOptionDetails": {
          "AmiSource": {
            "AmiId": "ami-123412341234",
            "AccessRoleArn": "arn:aws:iam::12341234:role/example",
            "UserName": "example-user",
            "OperatingSystemName": "EXAMPLE",
            "OperatingSystemVersion": "EXAMPLE-1.2",
            "ScanningPort": 22
          },
          "UsageInstructions": "Example.",
          "RecommendedInstanceType": "m5.large",
          "SecurityGroups": [
            {
              "FromPort": 22,
              "IpProtocol": "tcp",
              "IpRanges": [
              "0.0.0.0/0"
              ],
              "ToPort": 22
            }
          ]
        }
      }
    })

    # Instantiate the AWSVersionMetadata with the required information
    metadata = AWSVersionMetadata(
      destination="product-example/plan-example",
      sas_uri="https://foo.com/bar/image.vhd",
      disk_version="2.1.0",
      keepdraft=False,  # When `False` it means publish to live.
      product_type = "AmiProduct",
      entity_id = "1234-1234-1234-2134",
      version_mapping = example_version_mapping
    )

    # Associate the image with the destination and publish the changes
    svc = AWSProductService(access_id=example_id, secret_key=example_secret)
    svc.publish(metadata)
