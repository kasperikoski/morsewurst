# ============================================================
# morsewurst/network/identity.py
# ============================================================

from __future__ import annotations

import base64
import json
import os
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from morsewurst.network.protocol import normalize_room_id

try:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
    from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat
except Exception as exc:  # pragma: no cover - handled at runtime with a clear error
    InvalidSignature = None  # type: ignore[assignment]
    Ed25519PrivateKey = None  # type: ignore[assignment]
    Ed25519PublicKey = None  # type: ignore[assignment]
    Encoding = None  # type: ignore[assignment]
    NoEncryption = None  # type: ignore[assignment]
    PrivateFormat = None  # type: ignore[assignment]
    PublicFormat = None  # type: ignore[assignment]
    _CRYPTO_IMPORT_ERROR: Exception | None = exc
else:
    _CRYPTO_IMPORT_ERROR = None


OPERATOR_ID_PREFIX = "MWOP"
OPERATOR_ID_GROUPS = 5
OPERATOR_ID_GROUP_LENGTH = 4
OPERATOR_ID_BODY_LENGTH = OPERATOR_ID_GROUPS * OPERATOR_ID_GROUP_LENGTH
OPERATOR_ID_BITS = OPERATOR_ID_BODY_LENGTH * 5
OPERATOR_AUTH_ALGORITHM = "ed25519-operator-auth-v1"
OPERATOR_AUTH_PURPOSE = "morsewurst-operator-auth-v1"
OPERATOR_IDENTITY_FILE_VERSION = 1
OPERATOR_IDENTITY_FILENAME = "operator_identity.json"

# Crockford-style alphabet without easily confused I, L, O and U.
CROCKFORD_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_OPERATOR_ID_RE = re.compile(
    rf"^{OPERATOR_ID_PREFIX}-[0-9A-HJKMNP-TV-Z]{{4}}-[0-9A-HJKMNP-TV-Z]{{4}}-"
    rf"[0-9A-HJKMNP-TV-Z]{{4}}-[0-9A-HJKMNP-TV-Z]{{4}}-[0-9A-HJKMNP-TV-Z]{{4}}$"
)


class OperatorIdentityError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class OperatorIdentity:
    operator_id: str
    operator_public_key: str
    operator_private_key: str
    algorithm: str = OPERATOR_AUTH_ALGORITHM
    created_at_ms: int = 0

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "operator_id": self.operator_id,
            "operator_public_key": self.operator_public_key,
            "algorithm": self.algorithm,
        }

    def to_export_dict(self) -> dict[str, Any]:
        return {
            "app": "Morsewurst",
            "kind": "operator_identity",
            "version": OPERATOR_IDENTITY_FILE_VERSION,
            "warning": "This file contains the secret operator private key. Do not share it.",
            **asdict(self),
        }


def operator_identity_path() -> Path:
    try:
        import morsewurst.config as config
    except Exception as exc:  # pragma: no cover - defensive for minimal server installs
        raise OperatorIdentityError(
            "Operator Identity storage requires the Morsewurst desktop configuration. "
            "Pass an explicit path when using this module outside the desktop app."
        ) from exc

    return config.DATA_DIR / OPERATOR_IDENTITY_FILENAME


def _require_crypto() -> None:
    if _CRYPTO_IMPORT_ERROR is not None or Ed25519PrivateKey is None or Ed25519PublicKey is None:
        raise OperatorIdentityError(
            "Operator Identity requires the 'cryptography' package. Install dependencies first."
        ) from _CRYPTO_IMPORT_ERROR


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64url_decode(text: object, *, expected_length: int | None = None, field_name: str = "value") -> bytes:
    value = str(text or "").strip()
    if not value:
        raise OperatorIdentityError(f"Missing {field_name}.")

    padding = "=" * (-len(value) % 4)
    try:
        raw = base64.urlsafe_b64decode((value + padding).encode("ascii"))
    except Exception as exc:
        raise OperatorIdentityError(f"Invalid base64url {field_name}.") from exc

    if expected_length is not None and len(raw) != expected_length:
        raise OperatorIdentityError(f"Invalid {field_name} length.")

    return raw


def _crockford_encode_bits(value: int, *, length: int) -> str:
    chars: list[str] = []
    for index in range(length - 1, -1, -1):
        shift = index * 5
        chars.append(CROCKFORD_ALPHABET[(value >> shift) & 0b11111])
    return "".join(chars)


def _format_operator_id(body: str) -> str:
    groups = [body[index:index + OPERATOR_ID_GROUP_LENGTH] for index in range(0, len(body), OPERATOR_ID_GROUP_LENGTH)]
    return f"{OPERATOR_ID_PREFIX}-" + "-".join(groups)


def normalize_operator_id(value: object) -> str:
    text = str(value or "").strip().upper()
    text = text.replace(" ", "").replace("_", "-")

    if text.startswith(OPERATOR_ID_PREFIX):
        text = text[len(OPERATOR_ID_PREFIX):]

    body = text.replace("-", "")
    body = body.translate(str.maketrans({"I": "1", "L": "1", "O": "0"}))

    if len(body) != OPERATOR_ID_BODY_LENGTH:
        raise OperatorIdentityError("Operator listener code has an invalid length.")

    invalid = [ch for ch in body if ch not in CROCKFORD_ALPHABET]
    if invalid:
        raise OperatorIdentityError("Operator listener code contains invalid characters.")

    return _format_operator_id(body)


def is_valid_operator_id(value: object) -> bool:
    try:
        canonical = normalize_operator_id(value)
    except OperatorIdentityError:
        return False
    return bool(_OPERATOR_ID_RE.fullmatch(canonical))


def operator_id_from_public_key(operator_public_key: object) -> str:
    import hashlib

    public_raw = _b64url_decode(operator_public_key, expected_length=32, field_name="operator_public_key")
    digest = hashlib.sha256(public_raw).digest()
    value = int.from_bytes(digest, "big") >> (256 - OPERATOR_ID_BITS)
    body = _crockford_encode_bits(value, length=OPERATOR_ID_BODY_LENGTH)
    return _format_operator_id(body)


def _private_key_from_identity(identity: OperatorIdentity) -> Any:
    _require_crypto()
    private_raw = _b64url_decode(identity.operator_private_key, expected_length=32, field_name="operator_private_key")
    return Ed25519PrivateKey.from_private_bytes(private_raw)


def _public_key_from_text(operator_public_key: object) -> Any:
    _require_crypto()
    public_raw = _b64url_decode(operator_public_key, expected_length=32, field_name="operator_public_key")
    return Ed25519PublicKey.from_public_bytes(public_raw)


def generate_operator_identity() -> OperatorIdentity:
    _require_crypto()
    private_key = Ed25519PrivateKey.generate()
    private_raw = private_key.private_bytes(
        encoding=Encoding.Raw,
        format=PrivateFormat.Raw,
        encryption_algorithm=NoEncryption(),
    )
    public_key = private_key.public_key()
    public_raw = public_key.public_bytes(
        encoding=Encoding.Raw,
        format=PublicFormat.Raw,
    )
    public_text = _b64url_encode(public_raw)
    identity = OperatorIdentity(
        operator_id=operator_id_from_public_key(public_text),
        operator_public_key=public_text,
        operator_private_key=_b64url_encode(private_raw),
        created_at_ms=int(time.time() * 1000),
    )
    return validate_operator_identity(identity)


def validate_operator_identity(identity: OperatorIdentity) -> OperatorIdentity:
    if identity.algorithm != OPERATOR_AUTH_ALGORITHM:
        raise OperatorIdentityError("Unsupported operator identity algorithm.")

    operator_id = normalize_operator_id(identity.operator_id)
    derived_id = operator_id_from_public_key(identity.operator_public_key)
    if derived_id != operator_id:
        raise OperatorIdentityError("Operator listener code does not match the public key.")

    private_key = _private_key_from_identity(identity)
    public_raw_from_private = private_key.public_key().public_bytes(
        encoding=Encoding.Raw,
        format=PublicFormat.Raw,
    )
    public_raw = _b64url_decode(identity.operator_public_key, expected_length=32, field_name="operator_public_key")
    if public_raw_from_private != public_raw:
        raise OperatorIdentityError("Operator private key does not match the public key.")

    return OperatorIdentity(
        operator_id=operator_id,
        operator_public_key=identity.operator_public_key,
        operator_private_key=identity.operator_private_key,
        algorithm=identity.algorithm,
        created_at_ms=int(identity.created_at_ms or 0),
    )


def identity_from_data(data: dict[str, Any]) -> OperatorIdentity:
    if not isinstance(data, dict):
        raise OperatorIdentityError("Operator identity file must contain a JSON object.")

    if str(data.get("kind") or "operator_identity") != "operator_identity":
        raise OperatorIdentityError("File is not a Morsewurst operator identity file.")

    identity = OperatorIdentity(
        operator_id=str(data.get("operator_id") or ""),
        operator_public_key=str(data.get("operator_public_key") or ""),
        operator_private_key=str(data.get("operator_private_key") or ""),
        algorithm=str(data.get("algorithm") or OPERATOR_AUTH_ALGORITHM),
        created_at_ms=int(data.get("created_at_ms") or 0),
    )
    return validate_operator_identity(identity)


def load_operator_identity(path: Path | None = None) -> OperatorIdentity:
    target = path or operator_identity_path()
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise OperatorIdentityError("Operator identity file does not exist.") from exc
    except Exception as exc:
        raise OperatorIdentityError("Operator identity file could not be read.") from exc
    return identity_from_data(data)


def save_operator_identity(identity: OperatorIdentity, path: Path | None = None) -> Path:
    target = path or operator_identity_path()
    safe = validate_operator_identity(identity)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(json.dumps(safe.to_export_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(target)
    try:
        os.chmod(target, 0o600)
    except Exception:
        pass
    return target


def load_or_create_operator_identity(path: Path | None = None) -> OperatorIdentity:
    target = path or operator_identity_path()
    if target.exists():
        return load_operator_identity(target)
    identity = generate_operator_identity()
    save_operator_identity(identity, target)
    return identity


def export_operator_identity(identity: OperatorIdentity, export_path: Path) -> Path:
    target = Path(export_path)
    safe = validate_operator_identity(identity)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(safe.to_export_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def import_operator_identity_file(source_path: Path, destination_path: Path | None = None) -> OperatorIdentity:
    identity = load_operator_identity(Path(source_path))
    save_operator_identity(identity, destination_path or operator_identity_path())
    return identity


def _auth_payload(
    *,
    server_id: str,
    server_nonce: str,
    room: str,
    client_id: str,
    operator_id: str,
    operator_public_key: str,
    signed_at_ms: int,
) -> dict[str, Any]:
    return {
        "purpose": OPERATOR_AUTH_PURPOSE,
        "server_id": str(server_id or ""),
        "server_nonce": str(server_nonce or ""),
        "room": normalize_room_id(room),
        "client_id": str(client_id or "")[:80],
        "operator_id": normalize_operator_id(operator_id),
        "operator_public_key": str(operator_public_key or ""),
        "signed_at_ms": int(signed_at_ms or 0),
    }


def _canonical_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_operator_challenge(
    identity: OperatorIdentity,
    *,
    server_id: str,
    server_nonce: str,
    room: str,
    client_id: str,
    signed_at_ms: int | None = None,
) -> dict[str, Any]:
    safe = validate_operator_identity(identity)
    signed_at = int(signed_at_ms if signed_at_ms is not None else time.time() * 1000)
    payload = _auth_payload(
        server_id=server_id,
        server_nonce=server_nonce,
        room=room,
        client_id=client_id,
        operator_id=safe.operator_id,
        operator_public_key=safe.operator_public_key,
        signed_at_ms=signed_at,
    )
    signature = _private_key_from_identity(safe).sign(_canonical_bytes(payload))
    return {
        "algorithm": OPERATOR_AUTH_ALGORITHM,
        "operator_id": safe.operator_id,
        "operator_public_key": safe.operator_public_key,
        "signed_at_ms": signed_at,
        "signature": _b64url_encode(signature),
    }


def verify_operator_challenge(
    operator_auth: dict[str, Any],
    *,
    server_id: str,
    server_nonce: str,
    room: str,
    client_id: str,
    max_clock_skew_seconds: int | None = 600,
) -> str:
    _require_crypto()
    if not isinstance(operator_auth, dict):
        raise OperatorIdentityError("Operator auth must be an object.")

    if str(operator_auth.get("algorithm") or "") != OPERATOR_AUTH_ALGORITHM:
        raise OperatorIdentityError("Unsupported operator auth algorithm.")

    operator_id = normalize_operator_id(operator_auth.get("operator_id"))
    operator_public_key = str(operator_auth.get("operator_public_key") or "")
    derived_id = operator_id_from_public_key(operator_public_key)
    if not secrets_compare(derived_id, operator_id):
        raise OperatorIdentityError("Operator listener code does not match the public key.")

    try:
        signed_at_ms = int(operator_auth.get("signed_at_ms") or 0)
    except Exception as exc:
        raise OperatorIdentityError("Invalid operator auth timestamp.") from exc

    if max_clock_skew_seconds is not None:
        now_ms = int(time.time() * 1000)
        if signed_at_ms <= 0 or abs(now_ms - signed_at_ms) > int(max_clock_skew_seconds) * 1000:
            raise OperatorIdentityError("Operator auth timestamp is outside the allowed window.")

    payload = _auth_payload(
        server_id=server_id,
        server_nonce=server_nonce,
        room=room,
        client_id=client_id,
        operator_id=operator_id,
        operator_public_key=operator_public_key,
        signed_at_ms=signed_at_ms,
    )
    signature = _b64url_decode(operator_auth.get("signature"), expected_length=64, field_name="operator signature")

    try:
        _public_key_from_text(operator_public_key).verify(signature, _canonical_bytes(payload))
    except Exception as exc:
        if InvalidSignature is not None and isinstance(exc, InvalidSignature):
            raise OperatorIdentityError("Invalid operator auth signature.") from exc
        raise OperatorIdentityError("Operator auth signature could not be verified.") from exc

    return operator_id


def secrets_compare(left: str, right: str) -> bool:
    import hmac

    return hmac.compare_digest(str(left), str(right))
