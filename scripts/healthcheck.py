from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = [
    "docs/main-info-about-projects.md",
    "docs/structur-ai-agents-team.md",
    "docs/structur-data.md",
    ".env.example",
    "pyproject.toml",
]

REQUIRED_ENV_KEYS = [
    "APP_ENV",
    "LOG_LEVEL",
    "DEFAULT_LANGUAGE",
    "TELEGRAM_BOT_TOKEN",
    "OPENROUTER_API_KEY",
    "OPENROUTER_BASE_URL",
    "OPENROUTER_DEFAULT_MODEL",
    "POSTGRES_DSN",
    "QUALITY_MODE",
    "IDEAS_COUNT",
    "SCRIPTS_COUNT",
]

OPTIONAL_IMPORTS = [
    "pytest",
    "fastapi",
    "pydantic",
]


def parse_env_example(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def collect_health() -> dict[str, Any]:
    env_example = parse_env_example(ROOT / ".env.example")
    file_status = {name: (ROOT / name).exists() for name in REQUIRED_FILES}
    env_contract = {key: key in env_example for key in REQUIRED_ENV_KEYS}
    runtime_env_present = {key: bool(os.getenv(key)) for key in REQUIRED_ENV_KEYS}
    optional_imports = {
        module: importlib.util.find_spec(module) is not None for module in OPTIONAL_IMPORTS
    }

    failures = []
    missing_files = [name for name, exists in file_status.items() if not exists]
    missing_env_keys = [key for key, exists in env_contract.items() if not exists]
    if missing_files:
        failures.append({"type": "missing_files", "items": missing_files})
    if missing_env_keys:
        failures.append({"type": "missing_env_example_keys", "items": missing_env_keys})
    if sys.version_info < (3, 11):
        failures.append(
            {
                "type": "python_version",
                "message": "Python 3.11+ is required for the local test contour",
            }
        )

    return {
        "status": "ok" if not failures else "fail",
        "python": sys.version.split()[0],
        "root": str(ROOT),
        "files": file_status,
        "env_example": env_contract,
        "runtime_env_present": runtime_env_present,
        "optional_imports": optional_imports,
        "failures": failures,
    }


def print_human(report: dict[str, Any]) -> None:
    print(f"status: {report['status']}")
    print(f"python: {report['python']}")
    print(f"root: {report['root']}")
    print("files:")
    for name, exists in report["files"].items():
        print(f"  {'ok' if exists else 'missing'} {name}")
    print("env example keys:")
    for key, exists in report["env_example"].items():
        print(f"  {'ok' if exists else 'missing'} {key}")
    print("runtime env presence:")
    for key, present in report["runtime_env_present"].items():
        print(f"  {'set' if present else 'unset'} {key}")
    print("optional imports:")
    for module, available in report["optional_imports"].items():
        print(f"  {'ok' if available else 'missing'} {module}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run local MVP health checks.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    report = collect_health()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print_human(report)
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
