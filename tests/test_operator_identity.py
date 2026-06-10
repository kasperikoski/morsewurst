from __future__ import annotations

import time

import pytest

from morsewurst.network.identity import (
    OperatorIdentityError,
    generate_operator_identity,
    is_valid_operator_id,
    normalize_operator_id,
    operator_id_from_public_key,
    sign_operator_challenge,
    verify_operator_challenge,
)


def test_operator_identity_creation_produces_valid_listener_code() -> None:
    identity = generate_operator_identity()

    assert identity.operator_id.startswith("MWOP-")
    assert is_valid_operator_id(identity.operator_id)
    assert normalize_operator_id(identity.operator_id.lower().replace("-", "")) == identity.operator_id


def test_operator_id_is_deterministic_from_public_key() -> None:
    identity = generate_operator_identity()

    assert operator_id_from_public_key(identity.operator_public_key) == identity.operator_id
    assert operator_id_from_public_key(identity.operator_public_key) == identity.operator_id


def test_listener_code_normalization_and_validation() -> None:
    identity = generate_operator_identity()
    loose = identity.operator_id.lower().replace("-", "")

    assert normalize_operator_id(loose) == identity.operator_id
    assert is_valid_operator_id(identity.operator_id)
    assert not is_valid_operator_id("MWOP-TOO-SHORT")


def test_operator_challenge_signature_verifies() -> None:
    identity = generate_operator_identity()
    auth = sign_operator_challenge(
        identity,
        server_id="server-1",
        server_nonce="nonce-1",
        room="default",
        client_id="client-1",
        signed_at_ms=int(time.time() * 1000),
    )

    verified_id = verify_operator_challenge(
        auth,
        server_id="server-1",
        server_nonce="nonce-1",
        room="default",
        client_id="client-1",
    )

    assert verified_id == identity.operator_id


def test_operator_challenge_signature_rejects_wrong_public_key() -> None:
    identity = generate_operator_identity()
    other = generate_operator_identity()
    auth = sign_operator_challenge(
        identity,
        server_id="server-1",
        server_nonce="nonce-1",
        room="default",
        client_id="client-1",
    )
    auth["operator_public_key"] = other.operator_public_key
    auth["operator_id"] = other.operator_id

    with pytest.raises(OperatorIdentityError):
        verify_operator_challenge(
            auth,
            server_id="server-1",
            server_nonce="nonce-1",
            room="default",
            client_id="client-1",
        )


def test_operator_challenge_signature_rejects_modified_challenge() -> None:
    identity = generate_operator_identity()
    auth = sign_operator_challenge(
        identity,
        server_id="server-1",
        server_nonce="nonce-1",
        room="default",
        client_id="client-1",
    )

    with pytest.raises(OperatorIdentityError):
        verify_operator_challenge(
            auth,
            server_id="server-1",
            server_nonce="different-nonce",
            room="default",
            client_id="client-1",
        )
