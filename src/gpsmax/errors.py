# gpsmax/errors

"""
gpsmax.errors

Central exception hierarchy for GPSmax.

Rationale:
  - Scripts & modules should raise specific, meaningful errors.
  - Callers can catch GPSmaxError (broad) or specific subclasses (narrow).
"""


class GPSmaxError(RuntimeError):
    """Base class for all GPSmax runtime errors."""


# ---- Device / MTP errors -----------------------

class DeviceError(GPSmaxError):
    """Errors related to device discovery or access."""

class NoMtpDeviceError(DeviceError):
    """No MTP device/mount could be found (nothing connected or mounted)."""

class MtpDiscoveryError(DeviceError):
    """MTP is present but could not be resolved to a usable GVFS mount."""


# ---- Normalization / Selection errors ----------

class NormalizeError(GPSmaxError):
    """Errors in the normalization pipeline."""

class FzfNotFoundError(NormalizeError):
    """fzf is required but not available on PATH."""

class InvalidGpxError(NormalizeError):
    """GPX file could not be parsed or did not contain expected data structures."""


# ---- SQLite / DB errors ------------------------

class DatabaseError(GPSmaxError):
    """Errors interacting with the SQLite database."""
