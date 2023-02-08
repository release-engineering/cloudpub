# Documentation

This directory contains the necessary elements to build the documentation for `CloudPub` through Sphinx.

The documentation is automatically generated and published in GitLab pages through the GitLab CI.

## Manually building

To manually build the documentation in your local environment, simply execute:

```{bash}
tox -e docs
```

## Updating

Most of the documentation is automatically retrieved by the docstrings from source code, which should
follow the [Google Style](https://sphinxcontrib-napoleon.readthedocs.io/en/latest/example_google.html)
and formatted in [RST](https://docutils.sourceforge.io/rst.html).

A few elements need to be changed manually in the `*.rst` files, namely any additional quickstart topics
on `index.rst` or the declaration of a new class for `autodoc`.

The documentation files are composed by:

- **index.rst**: The documentation landing page with the index of topics.
- **cloud_providers/*.rst**: The documentation for `CloudPub`'s main classes.
