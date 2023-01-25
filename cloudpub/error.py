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


class Timeout(Exception):
    """Represent a missing resource."""
