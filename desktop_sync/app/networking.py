from __future__ import annotations

import re
import socket
import subprocess
from collections import OrderedDict
import json

from .models import CandidateAddress


IPV4_PATTERN = re.compile(r"(?<![\d.])((?:\d{1,3}\.){3}\d{1,3})(?![\d.])")
VIRTUAL_ADAPTER_KEYWORDS = (
    "loopback",
    "vethernet",
    "virtual",
    "vmware",
    "hyper-v",
    "wsl",
    "docker",
    "npcap",
    "wireguard",
    "singbox",
    "clash",
    "tun",
    "tap",
)


def list_candidate_addresses() -> list[CandidateAddress]:
    candidates: "OrderedDict[str, CandidateAddress]" = OrderedDict()

    def add_candidate(address: str, label: str) -> None:
        if (
            not address
            or address.startswith("127.")
            or address.startswith("169.254.")
            or address == "0.0.0.0"
            or _should_skip_adapter(label, address)
        ):
            return
        if address not in candidates:
            candidates[address] = CandidateAddress(
                address=address,
                label=label,
                is_recommended=_looks_like_overlay_network(label, address),
            )

    _load_candidates_from_powershell(add_candidate)
    if not candidates:
        _load_candidates_from_ipconfig(add_candidate)

    if not candidates:
        try:
            hostname = socket.gethostname()
            for item in socket.getaddrinfo(hostname, None, family=socket.AF_INET):
                add_candidate(item[4][0], "Hostname resolution")
        except OSError:
            pass

    return list(candidates.values())


def _looks_like_overlay_network(label: str, address: str) -> bool:
    lowered = label.lower()
    return "tailscale" in lowered or "zerotier" in lowered or address.startswith("100.")


def _should_skip_adapter(label: str, address: str) -> bool:
    lowered = label.lower()
    if _looks_like_overlay_network(label, address):
        return False
    return any(keyword in lowered for keyword in VIRTUAL_ADAPTER_KEYWORDS)


def _load_candidates_from_powershell(add_candidate) -> None:
    try:
        command = (
            "Get-NetIPAddress -AddressFamily IPv4 | "
            "Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' } | "
            "Select-Object InterfaceAlias,IPAddress | ConvertTo-Json -Compress"
        )
        output = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            check=False,
            encoding="utf-8",
            errors="ignore",
        ).stdout.strip()
        if not output:
            return
        parsed = json.loads(output)
        records = parsed if isinstance(parsed, list) else [parsed]
        for record in records:
            address = record.get("IPAddress", "")
            label = record.get("InterfaceAlias", "Detected adapter")
            add_candidate(address, label)
    except (OSError, json.JSONDecodeError, AttributeError):
        return


def _load_candidates_from_ipconfig(add_candidate) -> None:
    try:
        output = subprocess.run(
            ["ipconfig"],
            capture_output=True,
            text=True,
            check=False,
            encoding="utf-8",
            errors="ignore",
        ).stdout
        current_label = "Detected adapter"
        for raw_line in output.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if raw_line and not raw_line.startswith(" "):
                current_label = line.rstrip(":")
                continue
            if "ipv4" not in line.lower():
                continue
            for match in IPV4_PATTERN.finditer(line):
                add_candidate(match.group(1), current_label)
    except OSError:
        return
