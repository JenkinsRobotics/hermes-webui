from api import routes
from api.runner_client import RunnerClientError


class _RunnerSchedules:
    def __init__(self):
        self.calls = []

    def scheduler_status(self):
        self.calls.append(("status", None))
        return {"configured": True, "running": True, "owner": "jaeger"}

    def list_schedules(self, query):
        self.calls.append(("list", query))
        return {"jobs": []}

    def create_schedule(self, body):
        self.calls.append(("create", body))
        return {"ok": True, "job": body}

    def mutate_schedule(self, action, body):
        self.calls.append((action, body))
        return {"ok": True, "job_id": body.get("job_id")}


def _capture_json(_handler, payload, status=200, **_kwargs):
    return {"payload": payload, "status": status}


def test_runner_schedule_forward_uses_jaeger_and_never_hermes_state(monkeypatch):
    client = _RunnerSchedules()
    monkeypatch.setenv("HERMES_WEBUI_RUNTIME_ADAPTER", "runner-local")
    monkeypatch.setattr(routes, "_runtime_runner_client_factory", lambda: client)
    monkeypatch.setattr(routes, "j", _capture_json)

    assert routes._runner_schedule_forward(None, "status")["payload"]["owner"] == "jaeger"
    assert routes._runner_schedule_forward(None, "list", query="all_profiles=1")["payload"] == {"jobs": []}
    assert routes._runner_schedule_forward(
        None,
        "create",
        body={"name": "morning", "prompt": "Brief me", "schedule": "0 9 * * *"},
    )["payload"]["ok"] is True
    assert routes._runner_schedule_forward(
        None,
        "pause",
        body={"job_id": "morning"},
    )["payload"] == {"ok": True, "job_id": "morning"}
    assert client.calls == [
        ("status", None),
        ("list", "all_profiles=1"),
        ("create", {"name": "morning", "prompt": "Brief me", "schedule": "0 9 * * *"}),
        ("pause", {"job_id": "morning"}),
    ]


def test_runner_schedule_failure_is_bounded_and_does_not_fall_through(monkeypatch):
    monkeypatch.setenv("HERMES_WEBUI_RUNTIME_ADAPTER", "runner-local")
    monkeypatch.setattr(
        routes,
        "_runtime_runner_client_factory",
        lambda: (_ for _ in ()).throw(RunnerClientError("offline")),
    )
    monkeypatch.setattr(routes, "j", _capture_json)

    result = routes._runner_schedule_forward(None, "list")
    assert result["status"] == 503
    assert "scheduler unavailable" in result["payload"]["error"].lower()


def test_legacy_mode_keeps_hermes_scheduler(monkeypatch):
    monkeypatch.setenv("HERMES_WEBUI_RUNTIME_ADAPTER", "legacy-direct")
    assert routes._runner_schedule_forward(None, "list") is None


def test_tasks_panel_checks_runtime_scheduler_status():
    source = (routes.api_config.get_static_root() / "panels.js").read_text(encoding="utf-8")
    start = source.index("async function loadCronGatewayNotice()")
    end = source.index("async function loadCrons", start)
    body = source[start:end]
    assert "/api/runtime/scheduler/status" in body
    assert "/api/gateway/status" not in body
