# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CloudPub is a Python library (no CLI) for publishing VM images to cloud marketplace product listings. Supports AWS Marketplace Catalog and Microsoft Azure. Part of [release-engineering](https://github.com/release-engineering) tooling, complementing Stratosphere Tooling with minimal dependencies for Pub integration.

## Development Commands

```bash
# Run tests (pick your Python version)
tox -e py313

# Run a single test file or test
pytest -vv tests/aws/test_service.py
pytest -vv tests/aws/test_service.py::TestClassName::test_method

# Lint (flake8 + black + isort)
tox -e lint

# Auto-format
tox -e autoformat

# Type check
tox -e mypy

# Security scan (bandit + safety)
tox -e security

# Build docs
tox -e docs

# Repin dependencies
tox -e pip-compile
```

## Code Standards

- **Line length**: 100 characters
- **Formatter**: `black -S -t py310 -l 100` (note `-S` preserves single quotes)
- **Import sorting**: `isort -l 100 --profile black`
- **Docstrings**: required on public classes/functions (flake8-docstrings); D100/D104/D105 ignored globally, D101/D102/D103 ignored in tests
- **Type checking**: mypy with `--warn-unused-ignores --ignore-missing-imports`
- **Python**: 3.10 through 3.13

## Architecture

### Service Pattern

`BaseService[T]` (`cloudpub/common.py`) is a generic abstract class parameterized on a metadata type extending `PublishingMetadata`. Each cloud provider implements `publish(metadata: T)`:

- **`AWSProductService`** (`cloudpub/aws/service.py`) — uses boto3 for AWS Marketplace Catalog API. Manages product versions, delivery options, and changesets. Polls changesets via tenacity retry (default: 288 attempts x 10min = 48h).
- **`AzureService`** (`cloudpub/ms_azure/service.py`) — uses the Product Ingestion API via `PartnerPortalSession` (`cloudpub/ms_azure/session.py`), a custom `requests.Session` with HTTPS retry and SAS URI handling. Uses `deepdiff` for minimal change detection. Supports draft/preview/live staging.

### Data Models

All models live in `cloudpub/models/` and use `attrs` classes with `AttrsJSONDecodeMixin` (`cloudpub/models/common.py`). This mixin provides `from_json()`/`to_json()` with field alias support (e.g., `"VersionTitle"` ↔ `version_title`), nested object conversion, and optional field hiding.

- `cloudpub/models/aws.py` — AWS response/request models
- `cloudpub/models/ms_azure.py` — Azure resource models with a `RESOURCE_MAPING` dict for type dispatch

### Azure Schemas

`schemas/azure/` contains JSON schema files for Azure resource validation, updated via `tox -e azure_schemas`.

## Testing

Tests mirror the source structure under `tests/`. Each provider subdir has a `conftest.py` with shared fixtures. HTTP interactions are mocked with `httmock` (AWS) and `requests-mock` (Azure).

## Dependencies

Unpinned deps in `setup.py`, pinned with hashes in `requirements.txt` and `requirements-test.txt` via pip-tools. Install with `pip install --no-deps --require-hashes -r requirements.txt`.
