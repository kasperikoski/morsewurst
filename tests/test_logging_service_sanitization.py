from __future__ import annotations

from morsewurst.core.logging_service import sanitize_context


def test_sanitize_context_masks_additional_sensitive_and_identifier_keys() -> None:
    sanitized = sanitize_context(
        {
            "installation_id": "install-abcdef1234567890",
            "sender_id": "sender-abcdef1234567890",
            "stream_id": "stream-abcdef1234567890",
            "private_key": "super-secret-key",
            "credential": "super-secret-credential",
            "nested": {
                "api_secret": "super-secret",
                "safe": "visible",
            },
        }
    )

    assert str(sanitized["installation_id"]).startswith("instal…")
    assert sanitized["installation_id"] != "install-abcdef1234567890"
    assert str(sanitized["sender_id"]).startswith("sender…")
    assert sanitized["sender_id"] != "sender-abcdef1234567890"
    assert str(sanitized["stream_id"]).startswith("stream…")
    assert sanitized["stream_id"] != "stream-abcdef1234567890"
    assert sanitized["private_key"] == "[masked]"
    assert sanitized["credential"] == "[masked]"
    assert sanitized["nested"] == {
        "api_secret": "[masked]",
        "safe": "visible",
    }
