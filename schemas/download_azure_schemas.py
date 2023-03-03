#!/usr/bin/env python
"""
Download and store all JSON schemas from Azure Product Ingestion API schemas.

Usage:
    python download_azure_schemas.py [data_dir]
"""
import json
import os
import sys
from typing import Any, Dict

import requests

# This script is used to download all schemas from Product Ingestion API
# for the pinned version defined in `SCHEMAS_VERSION`

SCHEMAS_VERSION = "2022-03-01-preview2"
"""Define the pinned version for the Product Ingestion API schemas."""

SCHEMAS_URL = "https://product-ingestion.azureedge.net/schema/{RESOURCE}/{SCHEMAS_VERSION}"
"""The base URL to download the schemas."""

SCHEMAS_RESOURCES = [
    "product",
    "customer-leads",
    "test-drive",
    "plan",
    "property",
    "plan-listing",
    "listing",
    "listing-asset",
    "listing-trailer",
    "price-and-availability-offer",
    "price-and-availability-plan",
    "virtual-machine-plan-technical-configuration",
    "reseller",
    "submission",
    "resource-tree",
]
"""The list of schemas to download."""


def get_schema_json(resource: str) -> Dict[str, Any]:
    """
    Return the requested resource schema.
    
    Args:
        resource
            A resource name from ``SCHEMAS_RESOURCES``
    Returns:
        The parsed JSON from Microsoft.
    """
    print(f"Requesting the schema \"{resource}\" on version \"{SCHEMAS_VERSION}\"")
    url = SCHEMAS_URL.format(RESOURCE=resource, SCHEMAS_VERSION=SCHEMAS_VERSION)
    res = requests.get(url)
    res.raise_for_status()
    return res.json()


def store_schema(file_name: str, json_data: Dict[str, Any]) -> None:
    """
    Write the JSON data into the given file name.

    Args:
        file_name
            The path to the file to store the JSON.
        json_data
            The JSON data to store in the file.
    """
    print(f"Writing data fo {file_name}")
    with open(file_name, 'w') as f:
        json.dump(json_data, f, indent=2, sort_keys=True)


def download_and_store(store_dir: str = "azure") -> None:
    """
    Download all resources from the pinned version and store them.
    
    Args:
        store_dir
            Path to the directory to store all downloaded JSON files.
    """
    if not os.path.isdir(store_dir):
        print(f"Creating the storage directory \"{store_dir}\"")
        os.makedirs(store_dir)

    for resource in SCHEMAS_RESOURCES:
        out_file = os.path.join(store_dir, f"{resource}-{SCHEMAS_VERSION}.json")
        data = get_schema_json(resource)
        store_schema(out_file, data)


if __name__ == "__main__":
    args = []
    sys_args_len = len(sys.argv)
    store_dir = sys.argv[sys_args_len -1] if sys_args_len > 1 else None
    if store_dir:
        args.append(store_dir)
    download_and_store(*args)
