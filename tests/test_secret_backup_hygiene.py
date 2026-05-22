from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_streamlit_secret_backups_are_ignored_by_git_and_docker():
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")

    assert ".streamlit/secrets.toml.bak.*" in gitignore
    assert ".streamlit/secrets.toml.bak.*" in dockerignore
