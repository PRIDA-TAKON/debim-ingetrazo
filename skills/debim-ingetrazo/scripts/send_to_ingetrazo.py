#!/usr/bin/env python3
"""
CLI utility to probe and live-stream .debim manifests into IngeTrazo via the debim-ingetrazo Agent Bridge (Port 8482).
Requires standard Python 3 with zero external dependencies.

Usage:
  python send_to_ingetrazo.py --probe
  python send_to_ingetrazo.py --file project.debim.yaml
  cat project.debim.yaml | python send_to_ingetrazo.py
"""

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path


DEFAULT_URL = "http://127.0.0.1:8482"


def probe_listener(url: str = DEFAULT_URL, timeout: float = 3.0) -> bool:
    """Check if the IngeTrazo Agent Bridge listener is online."""
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                body = resp.read().decode("utf-8")
                try:
                    info = json.loads(body)
                    print(f"[*] IngeTrazo Agent Bridge is ONLINE at {url}")
                    print(f"    Service: {info.get('service')}")
                    print(f"    Received models count: {info.get('received_count', 0)}")
                except Exception:
                    print(f"[*] IngeTrazo responded (HTTP 200) from {url}")
                return True
            else:
                print(f"[!] Unexpected response from {url}: HTTP {resp.status}")
                return False
    except urllib.error.URLError as e:
        print(f"[-] Cannot connect to IngeTrazo Agent Bridge at {url}: {e.reason}")
        print("    Ensure IngeTrazo is running with debim-ingetrazo extension loaded.")
        return False
    except Exception as e:
        print(f"[-] Error connecting to {url}: {e}")
        return False


def send_manifest(content: str, url: str = DEFAULT_URL, timeout: float = 8.0) -> bool:
    """Send raw debim manifest text to the IngeTrazo listener."""
    data = content.encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "text/plain; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp_body = resp.read().decode("utf-8")
            try:
                result = json.loads(resp_body)
                status = result.get("status", "unknown")
                model_name = result.get("model_name", "unnamed")
                print(f"[+] Successfully sent to IngeTrazo! Status: {status}")
                print(f"    Active Model: {model_name}")
                if "model_dict" in result:
                    model = result.get("model_dict", {}).get("model", {})
                    children = model.get("children", [])
                    print(f"    Storeys: {len(children)}")
            except Exception:
                print(f"[+] Successfully sent to IngeTrazo (HTTP {resp.status})")
            return True
    except urllib.error.URLError as e:
        print(f"[-] Failed to deliver manifest to {url}: {e.reason}")
        return False
    except Exception as e:
        print(f"[-] Request error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Stream .debim manifests into IngeTrazo via Agent Bridge"
    )
    parser.add_argument(
        "-p", "--probe", action="store_true", help="Probe if IngeTrazo Agent Bridge is online"
    )
    parser.add_argument(
        "-f", "--file", type=str, help="Path to .debim or .debim.yaml file to send"
    )
    parser.add_argument(
        "-u", "--url", type=str, default=DEFAULT_URL, help=f"Agent Bridge URL (default: {DEFAULT_URL})"
    )
    args = parser.parse_args()

    if args.probe:
        success = probe_listener(args.url)
        sys.exit(0 if success else 1)

    content = ""
    if args.file:
        path = Path(args.file)
        if not path.is_file():
            print(f"[-] Error: File not found: {args.file}", file=sys.stderr)
            sys.exit(1)
        content = path.read_text(encoding="utf-8")
    elif not sys.stdin.isatty():
        content = sys.stdin.read()
    else:
        parser.print_help()
        sys.exit(1)

    if not content.strip():
        print("[-] Error: Manifest content is empty", file=sys.stderr)
        sys.exit(1)

    success = send_manifest(content, args.url)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
