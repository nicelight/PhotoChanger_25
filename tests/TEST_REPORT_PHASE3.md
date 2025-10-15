# Phase 3 Test Report

## Summary
- ✅ `pytest -m unit` — passed (39 selected, 25 deselected)
- ✅ `pytest -m contract` — passed (25 selected, 39 deselected)

## Logs

### `pytest -m unit`
```
===================================================== test session starts ======================================================
platform linux -- Python 3.11.12, pytest-8.4.1, pluggy-1.6.0
rootdir: /workspace/PhotoChanger_25
configfile: pytest.ini
plugins: anyio-4.11.0
collected 64 items / 25 deselected / 39 selected

tests/unit/test_app_scaffolding.py .                                                                                     [  2%]
tests/unit/test_deadlines.py .........                                                                                   [ 25%]
tests/unit/test_imports.py .............................                                                                 [100%]

============================================== 39 passed, 25 deselected in 0.57s ===============================================
```

### `pytest -m contract`
```
===================================================== test session starts ======================================================
platform linux -- Python 3.11.12, pytest-8.4.1, pluggy-1.6.0
rootdir: /workspace/PhotoChanger_25
configfile: pytest.ini
plugins: anyio-4.11.0
collected 64 items / 39 deselected / 25 selected

tests/contract/test_admin.py .........                                                                                   [ 36%]
tests/contract/test_ingest.py ...                                                                                        [ 48%]
tests/contract/test_provider_mocks.py ........                                                                           [ 80%]
tests/contract/test_public_links.py ..                                                                                   [ 88%]
tests/contract/test_queue_worker.py ...                                                                                  [100%]

======================================================== warnings summary =======================================================
tests/contract/test_admin.py: 9 warnings
tests/contract/test_ingest.py: 3 warnings
tests/contract/test_public_links.py: 2 warnings
  /root/.pyenv/versions/3.11.12/lib/python3.11/site-packages/httpx/_client.py:680: DeprecationWarning: The 'app' shortcut is now deprecated. Use the explicit style 'transport=WSGITransport(app=...)' instead.
    warnings.warn(message, DeprecationWarning)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================================== 25 passed, 39 deselected, 14 warnings in 1.44s ========================================
```

## Outstanding Actions
- None. All contract and unit suites required for Phase 3 are green.
