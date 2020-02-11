"""
ariston.exceptions
This module contains the set of amcrest's exceptions.

"""

class AristonError(Exception):
    """General Ariston error occurred."""

class CommError(AristonError):
    """A communication error occurred."""

class LoginError(AristonError):
    """A login error occurred."""
