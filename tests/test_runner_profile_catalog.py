import pytest


@pytest.fixture(scope='session', autouse=True)
def test_server():
    # Pure catalog tests do not need the integration server fixture.
    yield


def test_runner_catalog_owns_names_status_and_skills(monkeypatch, tmp_path):
    from api import profiles
    from api.runner_client import HttpRunnerClient
    monkeypatch.setenv('HERMES_WEBUI_RUNTIME_ADAPTER', 'runner-local')
    monkeypatch.setenv('HERMES_WEBUI_RUNNER_PROFILES', '1')
    monkeypatch.setenv('HERMES_WEBUI_RUNNER_BASE_URL', 'http://runner.invalid')
    monkeypatch.setattr(profiles, '_is_isolated_profile_mode', lambda: False)
    monkeypatch.setattr(profiles, 'get_active_profile_name', lambda: 'openclaw')
    monkeypatch.setattr(profiles, 'get_hermes_home_for_profile', lambda name: tmp_path / name)
    monkeypatch.setattr(profiles, '_build_profile_rows_fast', lambda: pytest.fail('must not discover incidental directories'))
    expected = [{'name': name, 'display_name': label, 'gateway_running': True,
                 'total_skills': None, 'enabled_skills': None, 'visible': True}
                for name, label in [('default', 'Hermes Agent'), ('jaeger', 'Jaeger AI'),
                                    ('openclaw', 'OpenClaw'), ('roundtable', 'Roundtable')]]
    monkeypatch.setattr(HttpRunnerClient, '_get', lambda self, path: {'profiles': expected})
    rows = profiles.list_profiles_api()
    assert [p['name'] for p in rows] == [p['name'] for p in expected]
    assert rows[2]['is_active']
    assert all(p['gateway_running'] and p['total_skills'] is None for p in rows)


def test_runner_unavailable_does_not_fall_back_to_folder_profiles(monkeypatch):
    from api import profiles
    from api.runner_client import HttpRunnerClient, RunnerClientError
    monkeypatch.setenv('HERMES_WEBUI_RUNTIME_ADAPTER', 'runner-local')
    monkeypatch.setenv('HERMES_WEBUI_RUNNER_PROFILES', '1')
    monkeypatch.setenv('HERMES_WEBUI_RUNNER_BASE_URL', 'http://runner.invalid')
    monkeypatch.setattr(profiles, '_is_isolated_profile_mode', lambda: False)
    def offline(*a): raise RunnerClientError('offline')
    monkeypatch.setattr(HttpRunnerClient, '_get', offline)
    with pytest.raises(RunnerClientError, match='offline'):
        profiles.list_profiles_api()
