"""Static deploy config checks (railway-deploy-readiness, T3). Paths resolve from the repo root."""

import json
import re
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
START_COMMAND = 'gunicorn "taskboard:create_app()"'


def _conf(monkeypatch, port=None):
    if port is None:
        monkeypatch.delenv("PORT", raising=False)
    else:
        monkeypatch.setenv("PORT", port)
    return runpy.run_path(str(ROOT / "gunicorn.conf.py"))


def _serve_recipe():
    lines = (ROOT / "Makefile").read_text().splitlines()
    for i, line in enumerate(lines):
        if re.match(r"^serve\s*:", line):
            recipe = [ln.strip() for ln in lines[i + 1 :] if ln.startswith("\t")]
            return recipe[0] if recipe else None
    return None


def test_deploy_t3_1_gunicorn_pinned_once():
    lines = [ln.strip() for ln in (ROOT / "requirements.txt").read_text().splitlines()]
    assert lines.count("gunicorn==23.0.0") == 1


def test_deploy_t3_3_conf_values_with_port(monkeypatch):
    conf = _conf(monkeypatch, "5099")
    assert conf["bind"] == "0.0.0.0:5099"
    assert conf["workers"] == 2
    assert conf["preload_app"] is True
    assert conf["accesslog"] == "-"


def test_deploy_t3_4_conf_default_port_when_unset(monkeypatch):
    assert _conf(monkeypatch)["bind"] == "0.0.0.0:5050"


def test_deploy_t3_5_conf_default_port_when_empty(monkeypatch):
    assert _conf(monkeypatch, "")["bind"] == "0.0.0.0:5050"


def test_deploy_t3_9_make_serve_target_wired():
    text = (ROOT / "Makefile").read_text()
    phony = [ln for ln in text.splitlines() if ln.startswith(".PHONY")]
    assert phony and "serve" in phony[0].split()
    assert _serve_recipe() == '$(BIN)/gunicorn "taskboard:create_app()"'


def test_deploy_t3_10_railway_json_exact():
    data = json.loads((ROOT / "railway.json").read_text())
    assert data == {
        "$schema": "https://railway.com/railway.schema.json",
        "deploy": {
            "startCommand": START_COMMAND,
            "healthcheckPath": "/health",
            "restartPolicyType": "ON_FAILURE",
        },
    }


def test_deploy_t3_11_railway_json_no_build_key():
    assert "build" not in json.loads((ROOT / "railway.json").read_text())


def test_deploy_t3_12_start_command_matches_make_serve():
    recipe = _serve_recipe()
    assert recipe is not None
    data = json.loads((ROOT / "railway.json").read_text())
    assert recipe.replace("$(BIN)/", "") == data["deploy"]["startCommand"]


def test_deploy_t3_13_python_version():
    assert (ROOT / ".python-version").read_text().strip() == "3.12"
