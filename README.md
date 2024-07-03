# CloudPub

A library for publishing product listings on various clouds marketplaces

used by [release-engineering](https://github.com/release-engineering) publishing tools.

![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/release-engineering/cloudpub/tox-test.yml)
![GitHub Release](https://img.shields.io/github/v/release/release-engineering/cloudpub)
[![PyPI version](https://badge.fury.io/py/cloudpub.svg)](https://badge.fury.io/py/cloudpub)

- [Source](https://github.com/release-engineering/cloudpub)
- [Documentation](https://release-engineering.github.io/cloudpub/)


## Overview

The `CloudPub` is a library to allow associating and publishing VM images into product listings on
different cloud marketplaces.


### Objective

This library implements a small subset of Stratosphere Tooling actions which concerns only for
associating a VM Image with a product listing and publishing it.

It's not inteneded to replace the already existing Stratosphere Tooling but rather complement them
by:

1. Providing a very small and cohesive implementation of the required actions
2. Using the minimal external dependencies as possible for better integration with Pub
3. Following the same patterns from already existing Pub libraries
4. Not implementing a CLI of any type as its intended to be used as a library only


## Documentation

The documentation of `CloudPub` is [available here](https://release-engineering.github.io/cloudpub/).

## Installation

To install this library go to the project's root directory and execute:

```{bash}
    pip install -r requirements.txt
    pip install .
```

## Development

### Prerequisites

The versions listed below are the one which were tested and work. Other versions can work as well.

- Install or create a `virtualenv` for `python` >= 3.8
- Install `tox` >= 3.25

### Dependency Management

To manage dependencies, this project uses [pip-tools](https://github.com/jazzband/pip-tools) so that
the dependencies are pinned and their hashes are verified during installation.

The unpinned dependencies are recorded in **setup.py** and the **requirements.txt** are regenerated
each time `tox` runs. Alternatively you can run `tox -e pip-compile` manually
to achieve the same result. To upgrade a package, use the `-P` argument of the `pip-compile` command.

When installing the dependencies use the command `pip install --no-deps --require-hashes -r requirements.txt`.

To ensure the pinned dependencies are not vulnerable, this project uses [safety](https://github.com/pyupio/safety),
which runs on every pull-request or can be run manually by `tox -e security`.

### Coding Standards

The codebase conforms to the style enforced by `flake8` with the following exceptions:

- The maximum line length allowed is 100 characters instead of 80 characters

In addition to `flake8`, docstrings are also enforced by the plugin `flake8-docstrings` with
the following exemptions:

- D100: Missing docstring in public module
- D104: Missing docstring in public package
- D105: Missing docstring in magic method

Additionally, `black` is used to enforce other coding standards.

To verify that your code meets these standards, you may run `tox -e lint`.

To automatically format your code you man run `tox -e autoformat`.

### Unit tests

To run unit tests use `tox -e py38,py39,py310,py311`.
