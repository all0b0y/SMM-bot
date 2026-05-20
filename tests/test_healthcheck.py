from scripts.healthcheck import collect_health, parse_env_example


def test_healthcheck_imports_and_reports_ok_contract() -> None:
    report = collect_health()

    assert report["status"] == "ok"
    assert report["files"][".env.example"] is True
    assert report["env_example"]["TELEGRAM_BOT_TOKEN"] is True
    assert "OPENROUTER_API_KEY" in report["runtime_env_present"]


def test_parse_env_example_ignores_comments(tmp_path) -> None:
    env_file = tmp_path / ".env.example"
    env_file.write_text("# comment\nAPP_ENV=local\n\nOPENROUTER_API_KEY=\n", encoding="utf-8")

    assert parse_env_example(env_file) == {
        "APP_ENV": "local",
        "OPENROUTER_API_KEY": "",
    }
