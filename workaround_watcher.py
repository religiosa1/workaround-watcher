#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml"]
# ///
"""Remind about temporary workarounds once their preconditions say they can go.

Reads a YAML list of entries, evaluates each entry's `when` condition and sends
a desktop notification for every entry whose condition holds.
"""

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("workaround-watcher: PyYAML is missing (Arch: pacman -S python-yaml)")

PACMAN_LOCK = Path("/var/lib/pacman/db.lck")
PACMAN_LOCK_TIMEOUT = 30 * 60

# Maps operator name to a predicate over vercmp's result (installed vs target).
OPERATORS = {
    "ge": lambda cmp: cmp >= 0,
    "gt": lambda cmp: cmp > 0,
    "le": lambda cmp: cmp <= 0,
    "lt": lambda cmp: cmp < 0,
    "eq": lambda cmp: cmp == 0,
}


def default_config() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
    return Path(base) / "workarounds.yaml"


def installed_version(pkg: str) -> str | None:
    result = subprocess.run(["pacman", "-Q", pkg], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return None
    return result.stdout.split()[1]


def vercmp(a: str, b: str) -> int:
    """pacman's own version comparison: -1, 0 or 1."""
    result = subprocess.run(["vercmp", a, b], capture_output=True, text=True, check=True)
    return int(result.stdout)


def condition_met(when) -> bool:
    if not isinstance(when, dict):
        raise TypeError("`when` must be a mapping")
    operators = dict(when)
    pkg = operators.pop("pkg", None)
    # TODO: other condition kinds (cmd exit code, file exists, hostname) go here.
    if pkg is None:
        raise ValueError("only `pkg` conditions are supported")
    unknown = operators.keys() - OPERATORS.keys()
    if unknown:
        raise ValueError(f"unknown operators: {', '.join(sorted(unknown))}")
    if not operators:
        raise ValueError(f"`pkg: {pkg}` needs at least one of {', '.join(OPERATORS)}")

    version = installed_version(pkg)
    if version is None:
        return False
    return all(OPERATORS[op](vercmp(version, target)) for op, target in operators.items())


def wait_for_pacman() -> None:
    """Triggered mid-transaction by the .path unit; let pacman finish first."""
    deadline = time.monotonic() + PACMAN_LOCK_TIMEOUT
    while PACMAN_LOCK.exists() and time.monotonic() < deadline:
        time.sleep(2)


def notify(title: str, body: str, desktop: bool, urgency: str = "critical") -> None:
    print(f"{title}\n{body}\n", flush=True)
    if desktop and shutil.which("notify-send"):
        subprocess.run(
            ["notify-send", "-u", urgency, "-a", "workaround-watcher", title, body],
            check=False,
        )


def format_body(entry: dict) -> str:
    body = str(entry.get("desc", "")).strip()
    see = entry.get("see") or []
    if see:
        body += "\n\n" + "\n".join(see)
    return body


def load_entries(path: Path) -> list:
    # BaseLoader keeps every scalar a string, so `6.10` doesn't become the float 6.1.
    entries = yaml.load(path.read_text(), Loader=yaml.BaseLoader) or []
    if not isinstance(entries, list):
        raise TypeError("config root must be a list of entries")
    return entries


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-c", "--config", type=Path, default=default_config())
    parser.add_argument("--no-notify", action="store_true", help="print to stdout only")
    args = parser.parse_args()
    desktop = not args.no_notify

    wait_for_pacman()

    try:
        entries = load_entries(args.config)
    except (OSError, yaml.YAMLError, TypeError) as err:
        notify("workaround-watcher: bad config", f"{args.config}: {err}", desktop)
        return 1

    errors = 0
    for index, entry in enumerate(entries):
        name = entry.get("name", f"entry #{index}") if isinstance(entry, dict) else f"entry #{index}"
        try:
            if not isinstance(entry, dict):
                raise TypeError("entry must be a mapping")
            if "when" not in entry:
                raise ValueError("entry has no `when` key")
            if condition_met(entry["when"]):
                notify(f"Workaround: {name}", format_body(entry), desktop)
        except (ValueError, TypeError, OSError, subprocess.CalledProcessError) as err:
            # Surfaced on the desktop too: a silently broken entry is a lost reminder.
            notify(f"workaround-watcher: bad entry '{name}'", str(err), desktop, urgency="normal")
            errors += 1
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
