"""Networking helpers.

Prefer IPv4 when the host has no working IPv6 route (common on dev
machines/VMs). boto3, httpx and friends honour ``socket.getaddrinfo`` order
and try the first address first; with a broken IPv6 path, transfers to
dual-stack S3 endpoints select IPv6 and hang. Enabling this shim forces the
IPv4 family for every socket in the process.
"""

import socket
from collections.abc import Callable

_original_getaddrinfo: Callable = socket.getaddrinfo


def prefer_ipv4() -> None:
    """Make all outbound resolution return IPv4 addresses only.

    Idempotent: safe to call from multiple code paths.
    """
    if socket.getaddrinfo is _original_getaddrinfo:

        def getaddrinfo_v4(host, port, family=0, type=0, proto=0, flags=0):
            return _original_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)

        socket.getaddrinfo = getaddrinfo_v4
