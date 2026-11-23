"""Cross-network matchmaking agent for the Meridian Forum case."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("meridian-matchmaking")
except PackageNotFoundError:  # running from a checkout that was never installed
    __version__ = "0.0.0+unknown"
