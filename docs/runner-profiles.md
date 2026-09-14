# Runner-owned profiles

Deployments using `HERMES_WEBUI_RUNTIME_ADAPTER=runner-local` may set
`HERMES_WEBUI_RUNNER_PROFILES=1` when their runner supports `GET /v1/profiles`.
The returned `profiles` array owns selectable identities, display labels,
readiness, and skill metadata. Each row requires a valid profile `name`.
The WebUI adds the profile's local model selection and configuration path.

This prevents incidental state directories from appearing as chat backends.
It also prevents Hermes gateway PID checks or local skill folders from being
presented as native runtime readiness or capability counts. `runtime_status`
appears on status indicators and in unavailable profile rows. When the runner
cannot be reached, listing fails explicitly rather than discovering unrelated
folders. Single-profile deployments and deployments without the flag retain
their existing discovery behavior.

Runtime session ownership remains with `StartRunRequest.profile`; this catalog
does not migrate, delete, or merge existing conversations.

Verification: `test_runner_profile_catalog.py` covers catalog authority and
unavailability; `test_profile_dropdown_fast_open.py` covers cached rendering
and selection using the real display-name helper.
