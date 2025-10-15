# Provider mocks usage

`tests.mocks.providers` exposes deterministic doubles for Gemini and Turbotext
adapters.  The module documents available scenarios (success, timeout, error)
and is imported by `tests/conftest.py` to provide ready-to-use pytest fixtures
for contract and integration suites.  Use `MockProviderConfig` to switch
behaviour inside tests without modifying production code.
