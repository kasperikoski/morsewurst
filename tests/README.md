# Morsewurst pytest regression tests

This folder contains a pytest-based regression suite for Morsewurst. It focuses on pure or lightweight code paths where possible, and also includes local WebSocket relay integration tests that start a temporary relay server during the test run.

Covered areas include i18n service (language selection), language flag asset validation, challenge generation, text scoring normalization, adaptive decoding, adaptive timing, round scoring, timing profiles, WX-MOR generation and validation, database WPM source calculations, uncapped PARIS WPM display values, capped skill-rating evidence, strict full-character-set level coverage, keying/tone-event history totals, per-key-source practice speed suggestions, statistics WPM source series, structured app logging helpers, app logging context summaries, logging-service JSONL output, sensitive context masking, network protocol message sanitation, network settings persistence, public room client-side handling, user profile storage, legacy data migration into the default profile, per-profile data directory selection, profile creation, activation, renaming, deletion, backup handling and profile registry recovery, jitter-buffer scheduling logic with a fake tone player, network manager client-side behaviour, network UI package/import structure, and real local WebSocket relay behaviour including room joins, private rooms, ping/server-info handling, tone broadcast, slow-client protection, relay cleanup and logging.

## Install test dependencies

For the basic regression tests:

```bash
python -m pip install pytest
```

For the relay integration tests, install the real `websockets` package as well:

```bash
python -m pip install pytest websockets
```

If you run the network-related tests in an environment that does not have the full project dependencies installed, `tests/conftest.py` provides a small fallback stub for `websockets` so the pure protocol tests can still import. The relay integration tests require the real `websockets` package and are skipped if it is not available.


## Where to place the files

Copy `pytest.ini` into the project root, next to the `morsewurst/` package folder.

Copy the whole `tests/` folder into the project root.

Expected layout:

```text
morsewurst/
pytest.ini
tests/
  __init__.py
  conftest.py
  test_adaptive_decoder.py
  test_adaptive_timing.py
  test_app_logging.py
  test_challenge.py
  test_database_wpm_sources.py
  test_i18n_service.py
  test_jitter_buffer.py
  test_logging_service.py
  test_logging_service_sanitization.py
  test_network_manager.py
  test_network_protocol.py
  test_network_public_rooms_manager.py
  test_network_relay_integration.py
  test_network_relay_privacy.py
  test_network_ui_imports.py
  test_profile_store.py
  test_scoring.py
  test_settings_store.py
  test_timing_profile.py
  test_wxmor.py
  README.md
```

## Run all tests

```bash
python -m pytest
```

## Run one test file

```bash
python -m pytest tests/test_adaptive_decoder.py
```

## Run one named test

```bash
python -m pytest tests/test_network_protocol.py::test_tone_event_sanitization_and_validation
```
