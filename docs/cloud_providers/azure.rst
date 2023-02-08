Azure Provider
==============

Provide the classes to associate a VHD image into a product on Azure Marketplace.

.. note::
   The current implementation of AzureProvider follows the `Product Ingestion API`_ compatible with
   the version ``2022-07-01``, which is the default value set in the factory 
   :meth:`~cloudpub.ms_azure.session.PartnerPortalSession.make_graph_api_session`.


**Index:**

- `Providers`_
- `Session`_
- `Azure Models`_
    - `Azure Product`_
    - `Product Resources`_
    - `Resources internal elements`_

Providers
---------

.. autoclass:: cloudpub.ms_azure.AzurePublishingMetadata()
   :members:
   :inherited-members:
   :special-members: __init__

.. autoclass:: cloudpub.ms_azure.AzureService()
   :members:
   :special-members: __init__


Session
-------

.. autoclass:: cloudpub.ms_azure.session.PartnerPortalSession()
   :members:
   :inherited-members:
   :special-members: __init__

.. autoclass:: cloudpub.ms_azure.session.AccessToken()
   :members:
   :special-members: __init__

..
   The include below will make `Azure Models` available in this page.
   The extension had to be changed to avoid duplicate parsing on Sphinx

.. include:: models/azure.rst.incl 


.. _Product Ingestion API: https://learn.microsoft.com/en-us/azure/marketplace/product-ingestion-api
