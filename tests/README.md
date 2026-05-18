# Morsewurst pytest regression tests

This folder contains a first pytest-based regression suite for Morsewurst. It focuses on pure or lightweight code paths that can be tested without opening the Tkinter application.

Covered areas include challenge generation, text scoring normalization, adaptive decoding, adaptive timing, round scoring, timing profiles, WX-MOR generation and validation, network protocol message sanitation, network settings persistence, and jitter-buffer scheduling logic with a fake tone player.

## Install pytest

```bash
python -m pip install pytest
```

If you run the network-related tests in an environment that does not have the full project dependencies installed, `tests/conftest.py` provides a small fallback stub for `websockets` so the pure protocol tests can still import. Real network connection tests are intentionally not included in this first package.

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
  test_challenge.py
  test_jitter_buffer.py
  test_network_protocol.py
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

## Recommended Git usage

Commit these tests with the project. After each refactor, run `python -m pytest` before committing. This gives a quick signal if core behavior changed unexpectedly.

A sensible first commit message would be:

```text
Add pytest regression suite for core Morsewurst logic
```
