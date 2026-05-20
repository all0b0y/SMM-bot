from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENV_EXAMPLE = ROOT / ".env.example"

REQUIRED_KEYS = {
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
}

FORBIDDEN_SECRET_MARKERS = [
    "sk-or-",
    "sk-",
    "xoxb-",
    "bot:",
]


def parse_env(path: Path) -> dict[str, str]:
    values = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value
    return values


def test_env_example_contains_required_keys() -> None:
    values = parse_env(ENV_EXAMPLE)
    assert REQUIRED_KEYS <= values.keys()


def test_env_example_does_not_contain_real_secret_like_values() -> None:
    text = ENV_EXAMPLE.read_text(encoding="utf-8").lower()
    assert not any(marker in text for marker in FORBIDDEN_SECRET_MARKERS)
    values = parse_env(ENV_EXAMPLE)
    assert values["TELEGRAM_BOT_TOKEN"] == ""
    assert values["OPENROUTER_API_KEY"] == ""
