AWS Provider
==============

Provide the classes to associate a VHD image into a product on AWS Marketplace.

.. note::

   Uses `Boto3`_ to access AWS Marketplace public API.

**Index:**

- `Providers`_

Providers
---------

.. autoclass:: cloudpub.aws.AWSVersionMetadata()
   :members:
   :inherited-members:
   :special-members: __init__

.. autoclass:: cloudpub.aws.AWSProductService()
   :members:
   :special-members: __init__

..
   The include below will make `AWS Models` available in this page.
   The extension had to be changed to avoid duplicate parsing on Sphinx

.. include:: models/aws.rst.incl


.. _Boto3: https://boto3.amazonaws.com/v1/documentation/api/latest/guide/quickstart.html
