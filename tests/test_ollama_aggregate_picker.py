"""Regression coverage for a Mac Ollama daemon serving local + cloud tags."""

from __future__ import annotations

import json
import urllib.request

import pytest

import api.config as config
import api.profiles as profiles


class _Response:
    def __init__(self, payload: dict):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    old_cfg = dict(config.cfg)
    old_mtime = config._cfg_mtime
    monkeypatch.setattr(profiles, "get_active_hermes_home", lambda: tmp_path)
    monkeypatch.setattr(
        config,
        "_base_url_points_at_local_server",
        lambda url: str(url).startswith("http://127.0.0.1:11434"),
    )
    monkeypatch.setattr(config, "_LIVE_REBUILD_BUDGET_SECONDS", 0.0)
    config.invalidate_models_cache()
    yield
    config.cfg.clear()
    config.cfg.update(old_cfg)
    config._cfg_mtime = old_mtime
    config.invalidate_models_cache()


def _write_config(tmp_path, monkeypatch) -> None:
    cfgfile = tmp_path / "config.yaml"
    cfgfile.write_text(
        """
model:
  provider: ollama
  default: glm-5.2:cloud
  base_url: http://127.0.0.1:11434/v1
providers:
  only_configured: true
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(config, "_get_config_path", lambda: cfgfile)
    config.reload_config()
    config.invalidate_models_cache()


def _install_catalog(monkeypatch) -> None:
    tags = {
        "models": [
            {
                "name": "glm-5.2:cloud",
                "remote_host": "https://ollama.com",
                "capabilities": ["completion", "tools"],
            },
            {
                "name": "gemini-3-flash-preview:latest",
                "remote_host": "https://ollama.com:443",
                "capabilities": ["completion", "vision"],
            },
            {
                "name": "gemma-4-26b:latest",
                "capabilities": ["completion", "tools"],
            },
            {
                "name": "nomic-embed-text:latest",
                "capabilities": ["embedding"],
            },
        ]
    }

    def _urlopen(request, **_kwargs):
        url = request.full_url if hasattr(request, "full_url") else str(request)
        if url.endswith("/api/tags"):
            return _Response(tags)
        if url.endswith("/v1/models"):
            return _Response({"data": [{"id": row["name"]} for row in tags["models"]]})
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr(urllib.request, "urlopen", _urlopen)


def test_picker_splits_one_ollama_endpoint_into_cloud_and_local(
    tmp_path,
    monkeypatch,
):
    _write_config(tmp_path, monkeypatch)
    _install_catalog(monkeypatch)

    result = config.get_available_models(force_refresh=True)
    groups = {group["provider_id"]: group for group in result["groups"]}

    assert result["active_provider"] == "ollama-cloud"
    assert set(groups) == {"ollama-cloud", "ollama-local"}
    assert groups["ollama-cloud"]["provider"] == "Ollama Cloud"
    assert groups["ollama-local"]["provider"] == "Ollama Local"
    assert {row["id"] for row in groups["ollama-cloud"]["models"]} == {
        "glm-5.2:cloud",
        "gemini-3-flash-preview:latest",
    }
    assert {
        row["id"].removeprefix("@ollama-local:")
        for row in groups["ollama-local"]["models"]
    } == {"gemma-4-26b:latest"}
    assert "custom" not in groups
    assert "nomic-embed-text:latest" not in json.dumps(result)
    assert result["configured_model_badges"]["glm-5.2:cloud"]["provider"] == "ollama-cloud"


@pytest.mark.parametrize("lane", ["ollama-cloud", "ollama-local"])
def test_both_picker_lanes_route_through_the_same_mac_ollama_endpoint(
    tmp_path,
    monkeypatch,
    lane,
):
    _write_config(tmp_path, monkeypatch)

    model, provider, base_url = config.resolve_model_provider(
        f"@{lane}:selected-model:latest"
    )

    assert model == "selected-model:latest"
    assert provider == "ollama"
    assert base_url == "http://127.0.0.1:11434/v1"
