# SPDX-License-Identifier: GPL-3.0-or-later


class LoginFailed(RuntimeError):
    """Report login failure to some marketplace."""


class InvalidAuthData(RuntimeError):
    """Report invalid input data for authentication."""


class UnexpectedRuntimeType(RuntimeError):
    """Report invalid type when parsing data from JSON."""


class InvalidStateError(RuntimeError):
    """Report invalid state which should not happen in code."""


class NotFoundError(ValueError):
    """Represent a missing resource."""


class ConflictError(RuntimeError):
    """Report a submission conflict error."""


class Timeout(Exception):
    """Represent a missing resource."""


class CertificationError(InvalidStateError):
    """Report Azure Marketplace certification failure."""


class InvalidSchema(RuntimeError):
    """Report when an invalid schema is returned from cloud provider API."""
