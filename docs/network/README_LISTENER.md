# Morsewurst listener WebSocket protocol

This document describes how an external client can connect to the Morsewurst relay, join a room as a read-only listener, receive Morse traffic, and optionally filter traffic by a verified Operator Identity listener code.

The primary relay WebSocket URL is:

```text
wss://morsewurst.duckdns.org
```

Morsewurst Network traffic is room based. A client must always join exactly one room before it can receive traffic. An `operator_id` is not a global subscription target. It is only a filter applied to verified messages inside the room that the listener has already joined.

The relay intentionally does not provide a global "listen to this operator everywhere" API.

---

## 1. Core concepts

### 1.1 Relay

The relay is a WebSocket server that accepts Morsewurst Network clients and forwards Morse telemetry between clients in the same room.

The public relay endpoint is:

```text
wss://morsewurst.duckdns.org
```

Clients communicate with the relay using JSON text messages over WebSocket.

### 1.2 Room

A room is the routing boundary for Morsewurst traffic.

A listener receives only messages from the room it has joined. If the same operator transmits in another room, the listener will not receive those messages unless it also joins that other room in a separate WebSocket connection.

Room examples:

```text
default
10wpm
15wpm
20wpm
morsewurst
my-private-room
```

Room identifiers are normalized by the relay. External clients should use simple lowercase room names with letters, numbers, hyphens, dots or underscores.

Recommended external room id format:

```text
default
esp32-listener-test
cw-monitor-1
```

### 1.3 Public room

A public room does not require a room password.

A listener can join a public room by completing the normal handshake and sending an `auth` message with an empty proof.

### 1.4 Private room

A private room requires room authentication.

Operator Identity does not replace private room authentication. A valid `operator_id` is not a password, invite token or access token.

For a private room, the client must know the room password and send the correct HMAC proof during the `auth` step.

### 1.5 Client mode

The `client_mode` field tells the relay what kind of client is connecting.

Supported modes relevant to this document:

```text
operator
listener
```

An `operator` client may transmit Morse telemetry.

A `listener` client is read-only. It may receive traffic, but it must not transmit `key` or `tone` messages. If a listener sends `key` or `tone`, the relay ignores the message and may send a warning status message.

### 1.6 Operator Identity

Morsewurst Operator Identity is a persistent cryptographic identity created and managed by the Morsewurst desktop application.

It is based on an Ed25519 key pair.

The private key stays local to the Morsewurst user’s data folder. The public key is used to derive a short shareable listener code called `operator_id`.

An `operator_id` looks like this:

```text
MWOP-7K4M-9XQ2-VR8H-PD6N-4TZA
```

A listener may use this code to filter received room traffic to one verified operator.

### 1.7 Operator listener code

The listener code is the public, shareable identifier.

It is safe to share:

```text
MWOP-7K4M-9XQ2-VR8H-PD6N-4TZA
```

It is not safe to share an exported Operator Identity file, because the export contains the private key.

### 1.8 Verified operator traffic

A received message should be treated as cryptographically tied to an Operator Identity only when:

```json
"operator_verified": true
```

and the message contains the expected `operator_id`.

If `operator_verified` is `false`, missing, or not a boolean true value, the message must not be treated as verified operator traffic.

Old clients may still send valid Morsewurst traffic without Operator Identity. Such messages are allowed, but they are unverified.

---

## 2. Protocol versions

Morsewurst currently uses two separate version concepts.

### 2.1 WebSocket envelope version

The top-level WebSocket message envelope uses:

```json
"v": 5
```

Example:

```json
{
  "v": 5,
  "app": "morsewurst",
  "type": "client_hello"
}
```

External clients should send top-level `v: 5`.

Receivers should ignore unknown fields for forward compatibility.

### 2.2 Key telemetry version

The inner `key` telemetry payload remains V1.

Example:

```json
{
  "v": 5,
  "app": "morsewurst",
  "type": "key",
  "key": {
    "v": 1,
    "type": "key",
    "state": "down",
    "t": 123456789
  }
}
```

Do not treat `key.v` as the same thing as the top-level WebSocket envelope version.

Correct current version combination:

```text
top-level message v = 5
inner key.v        = 1
```

---

## 3. WebSocket transport

### 3.1 URL

Connect to:

```text
wss://morsewurst.duckdns.org
```

The connection uses WebSocket over TLS.

### 3.2 Message format

All application messages are JSON objects sent as WebSocket text frames.

The relay expects messages to decode into JSON objects. Arrays, strings, numbers and malformed JSON are invalid application messages.

### 3.3 Recommended WebSocket settings

For desktop, server, Python or Node.js clients:

```text
max message size: at least 512 KB
ping interval: 20 seconds
ping timeout: 60 seconds
```

For embedded devices such as ESP32, exact settings depend on the WebSocket library. The client should support:

```text
TLS/WSS
text frames
JSON parsing
periodic ping/pong or automatic WebSocket keepalive
reconnect after disconnect
```

### 3.4 Reconnection behavior

A listener should be prepared for disconnects.

Recommended behavior:

1. Close any old socket state.
2. Wait a short delay.
3. Reconnect to `wss://morsewurst.duckdns.org`.
4. Send a new `client_hello`.
5. Wait for a new `server_challenge`.
6. Send a new `auth`.
7. Wait for `welcome`.
8. Resume listening.

Do not reuse an old `nonce` or old private-room proof after reconnecting.

---

## 4. Common top-level message fields

Most Morsewurst WebSocket messages use these fields:

```json
{
  "v": 5,
  "app": "morsewurst",
  "type": "message_type",
  "ts_ms": 1781053947518
}
```

### 4.1 `v`

Top-level WebSocket protocol version.

Current value:

```json
5
```

### 4.2 `app`

Application identifier.

Current value:

```json
"morsewurst"
```

### 4.3 `type`

Message type.

Examples:

```text
client_hello
server_challenge
auth
welcome
status
key
tone
server_info_request
server_info
client_ping
server_pong
public_rooms_request
public_rooms
```

### 4.4 `ts_ms`

Timestamp in milliseconds.

Clients may include this when using helper-compatible message construction. Receivers should not rely on it as a security timestamp unless the specific message type defines that behavior.

---

## 5. Listener connection flow

A listener connects with this sequence:

```text
1. Open WebSocket connection.
2. Send client_hello with client_mode = "listener".
3. Receive server_challenge.
4. Send auth.
5. Receive welcome.
6. Read key and tone messages.
7. Optionally filter by operator_id.
```

Sequence diagram:

```text
Listener client                         Relay
      |                                  |
      | --- WebSocket connect -------->  |
      |                                  |
      | --- client_hello --------------> |
      |                                  |
      | <--- server_challenge ---------- |
      |                                  |
      | --- auth ----------------------> |
      |                                  |
      | <--- welcome ------------------- |
      |                                  |
      | <--- key / tone / status ------- |
      | <--- key / tone / status ------- |
      |                                  |
```

---

## 6. `client_hello`

The first application message sent by the client is `client_hello`.

A read-only listener must set:

```json
"client_mode": "listener"
```

### 6.1 Minimal public-room listener hello

```json
{
  "v": 5,
  "app": "morsewurst",
  "type": "client_hello",
  "room": "default",
  "room_name": "default",
  "callsign": "ESP32 Listener",
  "client_id": "listener-esp32-01",
  "client_mode": "listener",
  "client_version": "esp32-listener-1.0.0",
  "capabilities": {
    "listener_mode": true
  }
}
```

### 6.2 Recommended listener hello

```json
{
  "v": 5,
  "app": "morsewurst",
  "type": "client_hello",
  "room": "default",
  "room_name": "default",
  "callsign": "Workshop Speaker",
  "client_id": "listener-workshop-speaker-01",
  "client_mode": "listener",
  "client_version": "workshop-speaker-1.0.0",
  "installation_id": "listener-installation-8c7d2f91",
  "capabilities": {
    "key_events": false,
    "tone_events": false,
    "decoded_text": false,
    "audio_playback": true,
    "dynamic_private_rooms": true,
    "public_rooms": true,
    "server_info": true,
    "server_ping": true,
    "operator_identity": true,
    "listener_mode": true
  }
}
```

### 6.3 Field reference

| Field            |    Required | Description                                                  |
| ---------------- | ----------: | ------------------------------------------------------------ |
| `v`              |         yes | Top-level WebSocket envelope version. Use `5`.               |
| `app`            |         yes | Use `"morsewurst"`.                                          |
| `type`           |         yes | Use `"client_hello"`.                                        |
| `room`           |         yes | Room to join.                                                |
| `room_name`      | recommended | Human-readable room name. Can match `room`.                  |
| `callsign`       | recommended | Human-readable listener name shown to other clients or logs. |
| `client_id`      |         yes | Unique client identifier for this connection or device.      |
| `client_mode`    |         yes | Use `"listener"` for read-only listening.                    |
| `client_version` | recommended | Your client software name/version.                           |
| `capabilities`   |    optional | Object describing client capabilities.                       |

### 6.4 Client id recommendations

Use a stable but non-sensitive client id.

Good examples:

```text
listener-esp32-01
listener-workshop-speaker-01
listener-python-monitor-7f3a
```

Avoid hardware fingerprints such as raw MAC addresses, CPU serials or device-specific private identifiers.

If the device needs a persistent id, generate a random id once and store it locally.

Example generated id:

```text
listener-8c7d2f91b4a0
```

### 6.5 Listener mode rules

A listener client may send:

```text
client_hello
auth
client_ping
server_info_request
public_rooms_request
```

A listener client must not send:

```text
key
tone
```

If a listener sends `key` or `tone`, the relay treats the client as read-only and ignores the transmitted Morse telemetry.

---

## 7. `server_challenge`

After receiving `client_hello`, the relay sends `server_challenge`.

The challenge tells the client whether room authentication is required and provides a fresh nonce.

### 7.1 Public room challenge example

```json
{
  "v": 5,
  "app": "morsewurst",
  "type": "server_challenge",
  "room": "default",
  "server_id": "server-6b2e2d8d9f30",
  "nonce": "8f0e2b827f2d4ddfa34cbf6e08c7298b",
  "auth": "none",
  "auth_required": false,
  "room_access": "public",
  "room_exists": true,
  "can_create_private_room": false
}
```

### 7.2 Private room challenge example

```json
{
  "v": 5,
  "app": "morsewurst",
  "type": "server_challenge",
  "room": "secret-room",
  "server_id": "server-6b2e2d8d9f30",
  "nonce": "b03c7f0e62a841d9814f9c5e567b4ca1",
  "auth": "hmac-sha256-room-verifier-v1",
  "auth_required": true,
  "room_access": "private",
  "room_exists": true,
  "can_create_private_room": false
}
```

### 7.3 Challenge fields

| Field | Description |
|---|---|
| `type` | Always `"server_challenge"`. |
| `room` | Normalized room key used for authentication. |
| `server_id` | Relay server identifier. Used by Operator Identity authentication. |
| `nonce` | Fresh per-handshake nonce used for room authentication and Operator Identity authentication. |
| `auth` | `"none"` for public rooms or `"hmac-sha256-room-verifier-v1"` for private rooms. |
| `auth_required` | `false` for public rooms, `true` for private rooms. |
| `room_access` | `"public"` or `"private"`. |
| `room_exists` | Whether the requested room already exists. |
| `can_create_private_room` | Whether this handshake may create a new dynamic private room. |

A client must use the `nonce` from this challenge when sending `auth`.

A client must not reuse a proof from an earlier challenge.

---

## 8. `auth` for public rooms

For a public room, `auth_required` is `false`.

The listener sends `auth` with an empty proof.

```json
{
  "v": 5,
  "app": "morsewurst",
  "type": "auth",
  "room": "default",
  "client_id": "listener-esp32-01",
  "proof": ""
}
```

The relay then replies with `welcome`.

---

## 9. `auth` for private rooms

Private rooms require a password-based proof.

Operator listener codes do not grant access to private rooms.

### 9.1 Private room proof overview

The private-room proof uses two steps.

First, derive the room password verifier as a lowercase SHA-256 hex string:

```text
verifier_hex = sha256("morsewurst-room-v1|" + normalized_room + "|" + password).hexdigest()
```

Then compute the proof as a lowercase HMAC-SHA256 hex string. The HMAC key is the UTF-8 encoding of `verifier_hex`, not the raw SHA-256 digest bytes:

```text
proof = hmac_sha256(
    key = utf8(verifier_hex),
    message = utf8(normalized_room + "|" + client_id + "|" + nonce)
).hexdigest()
```

This hex-string key detail is important for external clients. If the HMAC key is the raw 32-byte SHA-256 digest instead of the verifier hex string encoded as UTF-8, the relay will reject the proof.

### 9.2 Important details

Use the normalized room value used by the relay challenge.

If the challenge contains a `room` value, use that value for the proof.

Use the exact `client_id` sent in `client_hello`.

Use the exact `nonce` from `server_challenge`.

Use the room password as entered by the user.

Do not send the password itself.

Do not reuse the proof after reconnecting.

### 9.3 Private room proof pseudocode

```text
room_for_auth = challenge.room
client_id = "listener-esp32-01"
nonce = challenge.nonce
password = "correct private room password"

verifier_input = "morsewurst-room-v1|" + room_for_auth + "|" + password
verifier_hex = sha256(verifier_input).hexdigest()

proof_input = room_for_auth + "|" + client_id + "|" + nonce
proof = hmac_sha256(utf8(verifier_hex), utf8(proof_input)).hexdigest()
```

### 9.4 Private room auth example

```json
{
  "v": 5,
  "app": "morsewurst",
  "type": "auth",
  "room": "secret-room",
  "client_id": "listener-esp32-01",
  "proof": "7b2c0f27f3a7f1c12ad3cc1bb78c3a8adff8cb4c83a8df96ce2f75d8be8a6402"
}
```

### 9.5 Creating a new dynamic private room

If the relay challenge says that the requested private room does not exist and may be created:

```json
{
  "room_exists": false,
  "can_create_private_room": true
}
```

the `auth` message must include `room_password_verifier` in addition to `proof`:

```json
{
  "v": 5,
  "app": "morsewurst",
  "type": "auth",
  "room": "new-private-room",
  "client_id": "listener-esp32-01",
  "proof": "a4cb9015ef2a7e04e26cf995332e88f9f8908d845e1e8dbab33a6c64bb59ec92",
  "room_password_verifier": "8b37c63db320d7a34db32bdbeca1cc58768d3fbe3767f87c78b4e8a9e3d4584d"
}
```

`room_password_verifier` is secret-equivalent for that private room. Do not log it, publish it or store it in insecure device logs.

### 9.6 Wrong password behavior

If the private-room password is wrong, the relay does not send a successful `welcome`.

The client may receive a status or failure message such as:

```json
{
  "v": 5,
  "app": "morsewurst",
  "type": "status",
  "level": "error",
  "code": "BAD_ROOM_PASSWORD",
  "text": "Private room password is incorrect."
}
```

External clients should display this as a clean join failure and close or retry.

Do not keep sending repeated auth attempts in a tight loop.

---

## 10. Operator Identity authentication

Operator Identity authentication is mainly for transmitting Morsewurst clients.

A read-only listener does not need an Operator Identity to listen.

A normal Morsewurst operator client may authenticate its Operator Identity during the handshake. The relay verifies the Ed25519 signature once per session. After successful verification, the relay adds trusted operator fields to relayed `key` and `tone` messages.

### 10.1 What a listener needs to know

A listener does not need the operator public key.

A listener does not need the operator signature.

A listener does not need to verify Ed25519 signatures for each message.

A listener should trust the relay-added operator fields only when:

```json
"operator_verified": true
```

### 10.2 What an operator client signs

An operator client signs a canonical JSON payload containing:

```json
{
  "purpose": "morsewurst-operator-auth-v1",
  "server_id": "server-6b2e2d8d9f30",
  "server_nonce": "8f0e2b827f2d4ddfa34cbf6e08c7298b",
  "room": "default",
  "client_id": "client-desktop-01",
  "operator_id": "MWOP-7K4M-9XQ2-VR8H-PD6N-4TZA",
  "operator_public_key": "base64url-ed25519-public-key",
  "signed_at_ms": 1781053947518
}
```

The canonical byte representation is JSON encoded with:

```text
UTF-8
sorted object keys
no extra whitespace
separators: "," and ":"
```

Equivalent Python representation:

```python
json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
```

### 10.3 Operator auth object

The operator client includes the resulting operator auth object inside the normal `auth` message.

```json
{
  "algorithm": "ed25519-operator-auth-v1",
  "operator_id": "MWOP-7K4M-9XQ2-VR8H-PD6N-4TZA",
  "operator_public_key": "base64url-ed25519-public-key",
  "signed_at_ms": 1781053947518,
  "signature": "base64url-ed25519-signature"
}
```

### 10.4 Auth message with Operator Identity

For a public room, the room proof may still be empty, but `operator_auth` can be present:

```json
{
  "v": 5,
  "app": "morsewurst",
  "type": "auth",
  "room": "default",
  "client_id": "client-desktop-01",
  "proof": "",
  "operator_auth": {
    "algorithm": "ed25519-operator-auth-v1",
    "operator_id": "MWOP-7K4M-9XQ2-VR8H-PD6N-4TZA",
    "operator_public_key": "K5g2Pa7o4CtbQf5eJwI5r9nYx3F3fYeqD7V7nq0HhHk",
    "signed_at_ms": 1781053947518,
    "signature": "A7F7mZ0oRZp9o0vN8LrM1o0b2iDqJf9mN7w7mAq2fXvQvJdJzq2VQ6fZ1k4oJ4r0mVg9e6y0SxQh1a9pQw6AA"
  }
}
```

For a private room, the same `operator_auth` can be included, but the room `proof` must still be valid.

```json
{
  "v": 5,
  "app": "morsewurst",
  "type": "auth",
  "room": "secret-room",
  "client_id": "client-desktop-01",
  "proof": "7b2c0f27f3a7f1c12ad3cc1bb78c3a8adff8cb4c83a8df96ce2f75d8be8a6402",
  "operator_auth": {
    "algorithm": "ed25519-operator-auth-v1",
    "operator_id": "MWOP-7K4M-9XQ2-VR8H-PD6N-4TZA",
    "operator_public_key": "K5g2Pa7o4CtbQf5eJwI5r9nYx3F3fYeqD7V7nq0HhHk",
    "signed_at_ms": 1781053947518,
    "signature": "A7F7mZ0oRZp9o0vN8LrM1o0b2iDqJf9mN7w7mAq2fXvQvJdJzq2VQ6fZ1k4oJ4r0mVg9e6y0SxQh1a9pQw6AA"
  }
}
```

### 10.5 Relay verification

The relay verifies:

1. `operator_auth` is an object.
2. `algorithm` is `"ed25519-operator-auth-v1"`.
3. `operator_id` has a valid `MWOP-...` format.
4. `operator_public_key` is a valid Ed25519 public key.
5. `operator_id` is derived from `operator_public_key`.
6. `signed_at_ms` is inside the accepted clock-skew window.
7. The signature is valid for the canonical payload.
8. The payload matches the current `server_id`, `nonce`, `room` and `client_id`.

If verification succeeds, the session becomes:

```json
"operator_verified": true
```

If verification fails, the client may still be able to join as an unverified client depending on room authentication and server policy, but the relay must not mark the session as verified.

---

## 11. `welcome`

After successful room authentication, the relay sends `welcome`.

### 11.1 Public listener welcome example

```json
{
  "v": 5,
  "app": "morsewurst",
  "type": "welcome",
  "room_key": "default",
  "room": "default",
  "room_name": "General",
  "room_id": "DEFAULT",
  "room_access": "public",
  "server_id": "server-6b2e2d8d9f30",
  "client_id": "listener-esp32-01",
  "client_mode": "listener",
  "operator_id": "",
  "operator_verified": false,
  "peers": []
}
```

### 11.2 Verified operator welcome example

```json
{
  "v": 5,
  "app": "morsewurst",
  "type": "welcome",
  "room_key": "default",
  "room": "default",
  "room_name": "General",
  "room_id": "DEFAULT",
  "room_access": "public",
  "server_id": "server-6b2e2d8d9f30",
  "client_id": "client-desktop-01",
  "client_mode": "operator",
  "operator_id": "MWOP-7K4M-9XQ2-VR8H-PD6N-4TZA",
  "operator_verified": true,
  "peers": [
    {
      "client_id": "listener-esp32-01",
      "callsign": "ESP32 Listener",
      "client_mode": "listener",
      "operator_id": "",
      "operator_verified": false
    }
  ]
}
```

A listener can start receiving messages after `welcome`.

---

## 12. Runtime traffic received by listeners

The most important runtime messages for a listener are:

```text
key
tone
status
```

A playback device will usually process `key` or `tone`.

A monitoring program may process both.

### 12.1 `key` messages

A `key` message represents a key down or key up event.

The top-level message uses protocol envelope V5.

The inner `key` object uses key telemetry V1.

Example key down:

```json
{
  "v": 5,
  "app": "morsewurst",
  "type": "key",
  "ts_ms": 1781053947518,
  "sender_id": "client-desktop-01",
  "sender_name": "Kasperi",
  "seq": 42,
  "stream_id": "stream-9f2e1c",
  "key": {
    "v": 1,
    "type": "key",
    "src": "straight",
    "state": "down",
    "t": 123456789,
    "el": ".",
    "unit": 60000,
    "wpm": 20.0
  },
  "operator_id": "MWOP-7K4M-9XQ2-VR8H-PD6N-4TZA",
  "operator_verified": true,
  "via_server_id": "server-6b2e2d8d9f30"
}
```

Example key up:

```json
{
  "v": 5,
  "app": "morsewurst",
  "type": "key",
  "ts_ms": 1781053947608,
  "sender_id": "client-desktop-01",
  "sender_name": "Kasperi",
  "seq": 43,
  "stream_id": "stream-9f2e1c",
  "key": {
    "v": 1,
    "type": "key",
    "src": "straight",
    "state": "up",
    "t": 123456879,
    "el": ".",
    "unit": 60000,
    "wpm": 20.0
  },
  "operator_id": "MWOP-7K4M-9XQ2-VR8H-PD6N-4TZA",
  "operator_verified": true,
  "via_server_id": "server-6b2e2d8d9f30"
}
```

### 12.2 Key field reference

Top-level fields:

| Field               | Description                                                       |
| ------------------- | ----------------------------------------------------------------- |
| `type`              | `"key"`                                                           |
| `sender_id`         | Sending client id.                                                |
| `sender_name`       | Sending client display name.                                      |
| `seq`               | Monotonic sequence number from the sender.                        |
| `stream_id`         | Identifier for the current transmit stream.                       |
| `key`               | Inner V1 key event.                                               |
| `operator_id`       | Server-trusted Operator Identity listener code, if verified.      |
| `operator_verified` | `true` only if relay verified Operator Identity for this session. |
| `via_server_id`     | Relay identifier that forwarded the message.                      |

Inner `key` fields:

| Field    | Required | Description                                                                          |
| -------- | -------: | ------------------------------------------------------------------------------------ |
| `v`      |      yes | Inner key telemetry version. Current value is `1`.                                   |
| `type`   |      yes | `"key"`                                                                              |
| `src`    |      yes | Key source, for example `"straight"` or `"iambic"`.                                  |
| `state`  |      yes | `"down"` or `"up"`.                                                                  |
| `t`      |      yes | Sender-side event timestamp in microseconds or equivalent monotonic telemetry units. |
| `el`     | optional | Morse element hint, `"."` or `"-"`.                                                  |
| `unit`   | optional | Estimated Morse unit duration.                                                       |
| `wpm`    | optional | Estimated words per minute.                                                          |
| `dit`    | optional | Optional keyer metadata.                                                             |
| `device` | optional | Optional simple device metadata.                                                     |
| `mode`   | optional | Optional input mode metadata.                                                        |
| `key`    | optional | Optional key name or key side metadata.                                              |
| `pin`    | optional | Optional hardware pin metadata.                                                      |

### 12.3 Interpreting key messages for playback

A device can play audio directly from `key.state`.

Basic algorithm:

```text
if message.type == "key":
    if operator filter is enabled:
        require message.operator_verified == true
        require message.operator_id == configured operator_id

    event = message.key

    if event.state == "down":
        start tone
    if event.state == "up":
        stop tone
```

For a very simple speaker device, `key` messages are usually easier than `tone` messages.

### 12.4 `tone` messages

A `tone` message represents a complete tone segment with start time, end time and duration.

Example:

```json
{
  "v": 5,
  "app": "morsewurst",
  "type": "tone",
  "ts_ms": 1781053947608,
  "sender_id": "client-desktop-01",
  "sender_name": "Kasperi",
  "seq": 44,
  "stream_id": "stream-9f2e1c",
  "tone": {
    "type": "tone",
    "t0": 123456789,
    "t1": 123456879,
    "dur": 90000.0,
    "src": "straight",
    "el": ".",
    "unit": 60000,
    "wpm": 20.0
  },
  "operator_id": "MWOP-7K4M-9XQ2-VR8H-PD6N-4TZA",
  "operator_verified": true,
  "via_server_id": "server-6b2e2d8d9f30"
}
```

### 12.5 Tone field reference

Top-level fields:

| Field               | Description                                                       |
| ------------------- | ----------------------------------------------------------------- |
| `type`              | `"tone"`                                                          |
| `sender_id`         | Sending client id.                                                |
| `sender_name`       | Sending client display name.                                      |
| `seq`               | Monotonic sequence number from the sender.                        |
| `stream_id`         | Identifier for the current transmit stream.                       |
| `tone`              | Inner tone event.                                                 |
| `operator_id`       | Server-trusted Operator Identity listener code, if verified.      |
| `operator_verified` | `true` only if relay verified Operator Identity for this session. |
| `via_server_id`     | Relay identifier that forwarded the message.                      |

Inner `tone` fields:

| Field    | Required | Description                                     |
| -------- | -------: | ----------------------------------------------- |
| `type`   |      yes | `"tone"`                                        |
| `t0`     |      yes | Tone start timestamp.                           |
| `t1`     |      yes | Tone end timestamp.                             |
| `dur`    |      yes | Tone duration.                                  |
| `src`    | optional | Source, for example `"straight"` or `"iambic"`. |
| `el`     | optional | Morse element hint, `"."` or `"-"`.             |
| `unit`   | optional | Estimated Morse unit duration.                  |
| `wpm`    | optional | Estimated words per minute.                     |
| `device` | optional | Optional simple device metadata.                |
| `mode`   | optional | Optional input mode metadata.                   |
| `key`    | optional | Optional key name or key side metadata.         |
| `pin`    | optional | Optional hardware pin metadata.                 |

### 12.6 Interpreting tone messages for playback

`tone` messages are useful for jitter-buffered playback.

Basic algorithm:

```text
if message.type == "tone":
    if operator filter is enabled:
        require message.operator_verified == true
        require message.operator_id == configured operator_id

    event = message.tone

    schedule tone start at event.t0
    schedule tone stop at event.t1
```

For embedded devices, a simplified implementation can ignore exact scheduling and play the tone immediately for `dur` microseconds or milliseconds after converting the unit correctly.

A more accurate implementation should keep a small jitter buffer before playback.

Recommended jitter buffer range:

```text
50 ms to 250 ms
```

For unreliable Wi-Fi or embedded playback:

```text
150 ms to 300 ms
```

---

## 13. Operator filtering

Operator filtering is client-side and room-local.

The relay forwards room traffic according to room membership. The listener decides which received messages it wants to handle.

### 13.1 No operator filter

A listener with no operator filter can process all verified traffic in the joined room:

```text
if message.type in {"key", "tone"}:
    if message.operator_verified == true:
        handle(message)
```

This ignores old unverified clients.

If you want to hear all traffic including old clients, do not require `operator_verified`.

### 13.2 Verified operator filter

A listener that wants only one operator should require both:

```text
message.operator_verified == true
message.operator_id == configured_operator_id
```

Example:

```text
configured_operator_id = "MWOP-7K4M-9XQ2-VR8H-PD6N-4TZA"

if message.type in {"key", "tone"}
   and message.operator_verified == true
   and message.operator_id == configured_operator_id:
       handle(message)
```

### 13.3 Do not use unverified operator ids

Do not accept this as verified:

```json
{
  "operator_id": "MWOP-7K4M-9XQ2-VR8H-PD6N-4TZA",
  "operator_verified": false
}
```

Do not accept this as verified:

```json
{
  "operator_id": "MWOP-7K4M-9XQ2-VR8H-PD6N-4TZA"
}
```

Only this is verified:

```json
{
  "operator_id": "MWOP-7K4M-9XQ2-VR8H-PD6N-4TZA",
  "operator_verified": true
}
```

### 13.4 Why filtering is client-side

The listener joins a room first.

The `operator_id` is then used to decide which messages inside that room are relevant.

This design preserves room privacy and avoids creating a global operator tracking API.

---

## 14. Security model

### 14.1 What the relay guarantees

For verified operator messages, the relay guarantees that:

1. The operator client completed the room handshake.
2. The operator client proved possession of the Ed25519 private key for its Operator Identity.
3. The public key corresponds to the advertised `operator_id`.
4. The signature matched the current server challenge.
5. The signature was fresh enough according to the relay timestamp tolerance.
6. The relay added the trusted `operator_id` and `operator_verified` fields.
7. Spoofed client-supplied operator fields in runtime messages were removed before broadcast.

### 14.2 What the relay does not guarantee

The relay does not guarantee that:

1. A specific real-world human is behind an `operator_id`.
2. An `operator_id` grants access to a private room.
3. A listener can follow an operator globally across all rooms.
4. Old unverified clients have a cryptographic identity.
5. Private-room passwords are replaced by Operator Identity.

### 14.3 Spoofing protection

Clients may try to send fake fields such as:

```json
{
  "operator_id": "MWOP-FAKE-FAKE-FAKE-FAKE-FAKE",
  "operator_verified": true,
  "operator_public_key": "fake",
  "operator_signature": "fake"
}
```

The relay removes client-supplied operator fields from runtime `key` and `tone` messages before adding its own trusted fields.

A listener should therefore treat only relay-forwarded fields as meaningful, and it should require:

```json
"operator_verified": true
```

### 14.4 Private-room security

Private rooms require the private-room password proof even when the connecting client has a valid Operator Identity.

The correct order is:

```text
1. Join requested room.
2. Relay checks whether room requires password.
3. Client sends room auth proof if required.
4. Relay verifies room access.
5. Relay verifies optional Operator Identity.
6. Relay marks session operator_verified only if Operator Identity verification succeeds.
```

Operator Identity must not be treated as private-room access.

---

## 15. Practical listener types

### 15.1 Room monitor

A room monitor listens to all traffic in one room.

Use case:

```text
Show all verified Morse activity in the default room.
```

Configuration:

```text
uri: wss://morsewurst.duckdns.org
room: default
client_mode: listener
operator filter: none
accept unverified: optional
```

### 15.2 Operator monitor

An operator monitor listens to one verified operator inside one room.

Use case:

```text
Follow Kasperi's verified Morse transmission in the default room.
```

Configuration:

```text
uri: wss://morsewurst.duckdns.org
room: default
client_mode: listener
operator filter: MWOP-7K4M-9XQ2-VR8H-PD6N-4TZA
require operator_verified: true
```

### 15.3 Speaker device

A speaker device joins a room and plays received Morse as audio.

Recommended input:

```text
key messages
```

Simple playback:

```text
key down = start oscillator
key up   = stop oscillator
```

Recommended tone frequency:

```text
600 Hz
```

A more advanced speaker may use `tone` messages with a jitter buffer.

### 15.4 Display device

A display device joins a room and shows incoming key state or operator identity.

Possible display fields:

```text
room_name
sender_name
operator_id
operator_verified
key.state
key.el
tone.dur
wpm
```

### 15.5 Logger

A logger joins a room and writes received traffic to a file.

Recommended behavior:

```text
record raw JSON messages
include local receive timestamp
include room name
include operator_id
include operator_verified
```

Do not log private room passwords.

Do not log exported Operator Identity files.

---

## 16. Minimal listener pseudocode

```text
uri = "wss://morsewurst.duckdns.org"
room = "default"
client_id = "listener-esp32-01"
callsign = "ESP32 Listener"
operator_filter = ""

connect websocket to uri

send:
{
  "v": 5,
  "app": "morsewurst",
  "type": "client_hello",
  "room": room,
  "room_name": room,
  "callsign": callsign,
  "client_id": client_id,
  "client_mode": "listener",
  "client_version": "custom-listener-1.0.0",
  "capabilities": {
    "listener_mode": true
  }
}

receive challenge

if challenge.type != "server_challenge":
    fail

if challenge.auth_required == true:
    proof = make_private_room_proof(password, challenge.room, client_id, challenge.nonce)
else:
    proof = ""

send:
{
  "v": 5,
  "app": "morsewurst",
  "type": "auth",
  "room": challenge.room,
  "client_id": client_id,
  "proof": proof
}

receive welcome

if welcome.type != "welcome":
    fail

loop forever:
    receive message

    if message.type not in {"key", "tone"}:
        continue

    if operator_filter is not empty:
        if message.operator_verified != true:
            continue
        if message.operator_id != operator_filter:
            continue

    handle message
```

---

## 17. Python listener example

This example listens to verified traffic in the `default` room and optionally filters one operator.

```python
import asyncio
import json
import hmac
import hashlib
import websockets

URI = "wss://morsewurst.duckdns.org"
ROOM = "default"
PASSWORD = ""
CLIENT_ID = "listener-python-01"
CALLSIGN = "Python Listener"
OPERATOR_FILTER = "MWOP-7K4M-9XQ2-VR8H-PD6N-4TZA"


def normalize_room_id(room: str) -> str:
    # External clients should preferably use already-normalized room ids.
    # This simple fallback covers the common room names used by listeners.
    return room.strip().lower().replace(" ", "-")


def room_password_verifier(password: str, room: str) -> str:
    room_id = normalize_room_id(room)
    text = "morsewurst-room-v1|" + room_id + "|" + (password or "")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def auth_proof_from_verifier(password_verifier: str, room: str, client_id: str, nonce: str) -> str:
    room_id = normalize_room_id(room)
    key = password_verifier.encode("utf-8")
    text = room_id + "|" + client_id + "|" + nonce
    return hmac.new(key, text.encode("utf-8"), hashlib.sha256).hexdigest()


def auth_proof(password: str, room: str, client_id: str, nonce: str) -> str:
    verifier = room_password_verifier(password, room)
    return auth_proof_from_verifier(verifier, room, client_id, nonce)


async def main() -> None:
    async with websockets.connect(URI, max_size=512_000, ping_interval=20, ping_timeout=60) as ws:
        hello = {
            "v": 5,
            "app": "morsewurst",
            "type": "client_hello",
            "room": ROOM,
            "room_name": ROOM,
            "callsign": CALLSIGN,
            "client_id": CLIENT_ID,
            "client_mode": "listener",
            "client_version": "python-listener-1.0.0",
            "capabilities": {
                "key_events": False,
                "tone_events": False,
                "decoded_text": False,
                "audio_playback": True,
                "dynamic_private_rooms": True,
                "public_rooms": True,
                "server_info": True,
                "server_ping": True,
                "operator_identity": True,
                "listener_mode": True
            }
        }

        await ws.send(json.dumps(hello, separators=(",", ":")))

        challenge = json.loads(await ws.recv())
        if challenge.get("type") != "server_challenge":
            raise RuntimeError(f"Expected server_challenge, got {challenge!r}")

        room_for_auth = str(challenge.get("room") or ROOM)
        nonce = str(challenge.get("nonce") or "")
        auth_required = bool(challenge.get("auth_required", True))

        proof = ""
        if auth_required:
            proof = auth_proof(PASSWORD, room_for_auth, CLIENT_ID, nonce)

        auth = {
            "v": 5,
            "app": "morsewurst",
            "type": "auth",
            "room": room_for_auth,
            "client_id": CLIENT_ID,
            "proof": proof
        }

        await ws.send(json.dumps(auth, separators=(",", ":")))

        welcome = json.loads(await ws.recv())
        if welcome.get("type") != "welcome":
            raise RuntimeError(f"Join failed: {welcome!r}")

        print("Joined:", welcome.get("room_name") or welcome.get("room"))

        async for raw in ws:
            message = json.loads(raw)

            if message.get("type") not in {"key", "tone"}:
                continue

            if OPERATOR_FILTER:
                if message.get("operator_verified") is not True:
                    continue
                if message.get("operator_id") != OPERATOR_FILTER:
                    continue

            print(json.dumps(message, ensure_ascii=False))


asyncio.run(main())
```

---

## 18. ESP32 listener design notes

An ESP32 listener should keep the implementation simple.

Recommended behavior:

```text
1. Connect to Wi-Fi.
2. Open WSS connection to wss://morsewurst.duckdns.org.
3. Send client_hello with client_mode = "listener".
4. Receive server_challenge.
5. Send auth.
6. Receive welcome.
7. Listen for key messages.
8. Start tone on key down.
9. Stop tone on key up.
10. Reconnect on disconnect.
```

### 18.1 Recommended ESP32 configuration

```text
room: default
client_mode: listener
callsign: ESP32 Speaker
client_id: listener-esp32-speaker-01
operator filter: optional
tone frequency: 600 Hz
```

### 18.2 ESP32 playback with key messages

A simple ESP32 playback loop can use this logic:

```text
on websocket text frame:
    parse JSON

    if type != "key":
        ignore

    if operator filter configured:
        if operator_verified != true:
            ignore
        if operator_id != configured operator id:
            ignore

    key = message.key

    if key.state == "down":
        start PWM tone at 600 Hz

    if key.state == "up":
        stop PWM tone
```

### 18.3 ESP32 playback with tone messages

A more advanced ESP32 listener may use `tone` messages.

Simplified logic:

```text
on tone message:
    duration = tone.dur

    start PWM tone at 600 Hz
    wait duration
    stop PWM tone
```

This is easier to implement but less responsive if the duration arrives only after a tone has completed. For live-feeling playback, `key` messages are usually better.

### 18.4 ESP32 TLS note

The endpoint uses WSS, so the ESP32 WebSocket client must support TLS.

Depending on the ESP32 library, you may need to provide:

```text
root CA certificate
TLS verification configuration
sufficient heap for TLS
automatic reconnect logic
```

Do not disable TLS verification in production devices unless the device is only an experimental local prototype.

---

## 19. Reference command-line listener

The project includes a reference listener:

```text
server/listen_room.py
```

Run it from the project root:

```bash
python server/listen_room.py --uri wss://morsewurst.duckdns.org --room default
```

Listen to one verified operator:

```bash
python server/listen_room.py --uri wss://morsewurst.duckdns.org --room default --operator-id MWOP-7K4M-9XQ2-VR8H-PD6N-4TZA
```

Join a private room:

```bash
python server/listen_room.py --uri wss://morsewurst.duckdns.org --room secret-room --password "correct horse battery staple"
```

Join a private room and filter one operator:

```bash
python server/listen_room.py --uri wss://morsewurst.duckdns.org --room secret-room --password "correct horse battery staple" --operator-id MWOP-7K4M-9XQ2-VR8H-PD6N-4TZA
```

The reference listener prints verified `key` and `tone` messages as JSON.

---

## 20. Server information and public rooms

Some external clients may want to inspect the relay before joining a room.

### 20.1 Server info request

```json
{
  "v": 5,
  "app": "morsewurst",
  "type": "server_info_request",
  "sender_id": "listener-python-01"
}
```

Expected response type:

```text
server_info
```

The exact fields may evolve. Clients should ignore unknown fields.

### 20.2 Public rooms request

```json
{
  "v": 5,
  "app": "morsewurst",
  "type": "public_rooms_request",
  "sender_id": "listener-python-01"
}
```

Expected response type:

```text
public_rooms
```

A response contains a list of public rooms. Private rooms are not listed as public rooms.

A client may use this to populate a UI room picker.

---

## 21. Status messages

The relay may send `status` messages.

Example:

```json
{
  "v": 5,
  "app": "morsewurst",
  "type": "status",
  "level": "warning",
  "code": "LISTENER_READ_ONLY",
  "text": "Listener mode is read-only."
}
```

Recommended handling:

```text
level == "debug"    -> optional log only
level == "info"     -> optional display
level == "warning"  -> display or log
level == "error"    -> display, then decide whether to reconnect or stop
```

Common situations:

| Situation                   | Likely behavior                                          |
| --------------------------- | -------------------------------------------------------- |
| Wrong private-room password | Join fails with an error status or non-welcome response. |
| Listener sends key/tone     | Relay ignores telemetry and may send a warning.          |
| Operator auth fails         | Session is not marked verified.                          |
| Old client transmits        | Messages may be unverified.                              |
| Connection stalls           | WebSocket ping timeout or disconnect.                    |

---

## 22. Handling verified and unverified traffic

A listener has three reasonable filtering modes.

### 22.1 Hear everything in the room

This mode accepts old clients and verified clients.

```text
if message.type in {"key", "tone"}:
    handle(message)
```

Use this for general room monitoring.

### 22.2 Hear only verified operators

This mode ignores old clients.

```text
if message.type in {"key", "tone"}
   and message.operator_verified == true:
       handle(message)
```

Use this when you want cryptographic identity assurance but do not care which verified operator is transmitting.

### 22.3 Hear one specific verified operator

This mode is the strictest.

```text
if message.type in {"key", "tone"}
   and message.operator_verified == true
   and message.operator_id == "MWOP-7K4M-9XQ2-VR8H-PD6N-4TZA":
       handle(message)
```

Use this for a speaker, display, logger or external device tied to one Morsewurst operator.

---

## 23. Message validation recommendations

External clients should validate at least these conditions before acting on a message.

### 23.1 Common validation

```text
message is a JSON object
message.app == "morsewurst"
message.v == 5 or message.v is a supported future-compatible version
message.type is a string
```

### 23.2 Key validation

```text
message.type == "key"
message.key is an object
message.key.v == 1
message.key.type == "key"
message.key.state is "down" or "up"
message.key.t is an integer
```

### 23.3 Tone validation

```text
message.type == "tone"
message.tone is an object
message.tone.type == "tone"
message.tone.t0 is an integer
message.tone.t1 is an integer
message.tone.dur is a number
message.tone.t1 >= message.tone.t0
```

### 23.4 Operator filter validation

```text
if filtering by operator:
    message.operator_verified must be true
    message.operator_id must exactly match configured operator_id
```

### 23.5 Unknown fields

Clients should ignore unknown fields.

This allows the protocol to grow without breaking external listeners.

---

## 24. Timing and playback recommendations

### 24.1 Key-based playback

Key-based playback is the most responsive for a live speaker.

Pros:

```text
low latency
simple start/stop model
works naturally with live key down/up
good for ESP32 speaker output
```

Cons:

```text
requires clean handling of network jitter
a lost key-up message can leave tone stuck unless guarded
```

Recommended safety guard:

```text
if tone has been on longer than a maximum duration, stop it automatically
```

Example maximum:

```text
2000 ms
```

### 24.2 Tone-based playback

Tone-based playback is useful for scheduled or buffered playback.

Pros:

```text
complete duration is known
easy to render or log
works well with jitter buffer
```

Cons:

```text
may feel less immediate
requires scheduling for accurate playback
```

### 24.3 Suggested audio values

Default tone frequency:

```text
600 Hz
```

Reasonable alternatives:

```text
500 Hz
700 Hz
800 Hz
```

Suggested volume behavior:

```text
fade in/out very slightly if possible
avoid clicks on speaker output
stop tone on disconnect
```

---

## 25. Error handling

A robust external listener should handle these cases.

### 25.1 Invalid JSON

Ignore and log:

```text
invalid JSON frame
```

### 25.2 Unexpected message before challenge

Fail the connection and reconnect:

```text
expected server_challenge
```

### 25.3 Auth failure

Display the error and stop or retry only after user action:

```text
wrong room password
unknown room
room full
join failed
```

### 25.4 WebSocket disconnect

Stop audio immediately.

Then reconnect with a fresh handshake.

### 25.5 Missing key-up

If using key-based playback, stop any active tone after a safety timeout.

### 25.6 Operator filter mismatch

Silently ignore the message.

### 25.7 Unverified operator message

If strict operator filtering is enabled, ignore the message.

---

## 26. Privacy notes

### 26.1 Do not expose private-room passwords

Never log or display private-room passwords in device logs.

### 26.2 Do not expose Operator Identity exports

An exported Operator Identity file contains the operator private key.

It must not be copied to listener devices.

A listener only needs the public `MWOP-...` operator listener code.

### 26.3 Do not use hardware fingerprinting

External devices should avoid using raw MAC addresses, CPU serial numbers or other hardware fingerprints as public `client_id` values.

Generate a random listener id and store it locally.

### 26.4 Operator id is public

The `operator_id` is designed to be shared.

It is not secret.

It is not a password.

It is not a private-room invite.

---

## 27. Complete public-room listener example

This is the full message flow for a read-only listener joining the public `default` room.

### 27.1 Client sends `client_hello`

```json
{
  "v": 5,
  "app": "morsewurst",
  "type": "client_hello",
  "room": "default",
  "room_name": "default",
  "callsign": "ESP32 Speaker",
  "client_id": "listener-esp32-speaker-01",
  "client_mode": "listener",
  "client_version": "esp32-speaker-1.0.0",
  "capabilities": {
    "listener_mode": true,
    "operator_filter": true
  }
}
```

### 27.2 Relay sends `server_challenge`

```json
{
  "v": 5,
  "app": "morsewurst",
  "type": "server_challenge",
  "room": "default",
  "room_id": "DEFAULT",
  "room_name": "General",
  "auth_required": false,
  "nonce": "8f0e2b827f2d4ddfa34cbf6e08c7298b",
  "server_id": "server-6b2e2d8d9f30",
  "client_id": "listener-esp32-speaker-01"
}
```

### 27.3 Client sends `auth`

```json
{
  "v": 5,
  "app": "morsewurst",
  "type": "auth",
  "room": "default",
  "client_id": "listener-esp32-speaker-01",
  "proof": ""
}
```

### 27.4 Relay sends `welcome`

```json
{
  "v": 5,
  "app": "morsewurst",
  "type": "welcome",
  "room": "default",
  "room_id": "DEFAULT",
  "room_name": "General",
  "client_id": "listener-esp32-speaker-01",
  "client_mode": "listener",
  "operator_verified": false
}
```

### 27.5 Relay forwards verified key traffic

```json
{
  "v": 5,
  "app": "morsewurst",
  "type": "key",
  "ts_ms": 1781053947518,
  "sender_id": "client-desktop-01",
  "sender_name": "Kasperi",
  "seq": 42,
  "stream_id": "stream-9f2e1c",
  "key": {
    "v": 1,
    "type": "key",
    "src": "straight",
    "state": "down",
    "t": 123456789,
    "el": ".",
    "unit": 60000,
    "wpm": 20.0
  },
  "operator_id": "MWOP-7K4M-9XQ2-VR8H-PD6N-4TZA",
  "operator_verified": true,
  "via_server_id": "server-6b2e2d8d9f30"
}
```

The listener starts the tone.

### 27.6 Relay forwards verified key-up traffic

```json
{
  "v": 5,
  "app": "morsewurst",
  "type": "key",
  "ts_ms": 1781053947608,
  "sender_id": "client-desktop-01",
  "sender_name": "Kasperi",
  "seq": 43,
  "stream_id": "stream-9f2e1c",
  "key": {
    "v": 1,
    "type": "key",
    "src": "straight",
    "state": "up",
    "t": 123456879,
    "el": ".",
    "unit": 60000,
    "wpm": 20.0
  },
  "operator_id": "MWOP-7K4M-9XQ2-VR8H-PD6N-4TZA",
  "operator_verified": true,
  "via_server_id": "server-6b2e2d8d9f30"
}
```

The listener stops the tone.

---

## 28. Complete private-room listener example

This is the full message flow for a read-only listener joining a private room.

### 28.1 Client sends `client_hello`

```json
{
  "v": 5,
  "app": "morsewurst",
  "type": "client_hello",
  "room": "secret-room",
  "room_name": "secret-room",
  "callsign": "Private Room Speaker",
  "client_id": "listener-private-speaker-01",
  "client_mode": "listener",
  "client_version": "private-speaker-1.0.0",
  "capabilities": {
    "listener_mode": true,
    "operator_filter": true
  }
}
```

### 28.2 Relay sends `server_challenge`

```json
{
  "v": 5,
  "app": "morsewurst",
  "type": "server_challenge",
  "room": "secret-room",
  "room_id": "A9KF-2P7Q",
  "room_name": "secret-room",
  "auth_required": true,
  "nonce": "b03c7f0e62a841d9814f9c5e567b4ca1",
  "server_id": "server-6b2e2d8d9f30",
  "client_id": "listener-private-speaker-01"
}
```

### 28.3 Client computes proof

```text
password = "correct horse battery staple"
room = "secret-room"
client_id = "listener-private-speaker-01"
nonce = "b03c7f0e62a841d9814f9c5e567b4ca1"

verifier_hex = sha256("morsewurst-room-v1|secret-room|correct horse battery staple").hexdigest()

proof = hmac_sha256(
    key = utf8(verifier_hex),
    message = utf8("secret-room|listener-private-speaker-01|b03c7f0e62a841d9814f9c5e567b4ca1")
).hexdigest()
```

Example result:

```text
7b2c0f27f3a7f1c12ad3cc1bb78c3a8adff8cb4c83a8df96ce2f75d8be8a6402
```

### 28.4 Client sends `auth`

```json
{
  "v": 5,
  "app": "morsewurst",
  "type": "auth",
  "room": "secret-room",
  "client_id": "listener-private-speaker-01",
  "proof": "7b2c0f27f3a7f1c12ad3cc1bb78c3a8adff8cb4c83a8df96ce2f75d8be8a6402"
}
```

### 28.5 Relay sends `welcome`

```json
{
  "v": 5,
  "app": "morsewurst",
  "type": "welcome",
  "room": "secret-room",
  "room_id": "A9KF-2P7Q",
  "room_name": "secret-room",
  "client_id": "listener-private-speaker-01",
  "client_mode": "listener",
  "operator_verified": false
}
```

After `welcome`, the listener receives traffic from that private room only.

---

## 29. Implementation checklist

Use this checklist when building an external listener.

### 29.1 Connection

```text
Connect to wss://morsewurst.duckdns.org
Use JSON text frames
Send client_hello
Wait for server_challenge
Send auth
Wait for welcome
```

### 29.2 Listener mode

```text
Set client_mode to "listener"
Do not send key messages
Do not send tone messages
Handle status messages
Reconnect cleanly on disconnect
```

### 29.3 Public rooms

```text
If auth_required is false, send proof = ""
```

### 29.4 Private rooms

```text
If auth_required is true, compute HMAC proof from room password
Use challenge.room
Use challenge.nonce
Use the same client_id that was sent in client_hello
Use the verifier hex string as the HMAC key bytes
Never send the password itself
For new dynamic private rooms, include room_password_verifier and keep it secret
```

### 29.5 Operator filtering

```text
Store configured MWOP code
Require operator_verified == true
Require operator_id exact match
Ignore unverified messages when filtering by operator
```

### 29.6 Playback

```text
For simple live speaker: use key messages
For buffered playback: use tone messages
Stop audio on disconnect
Use a safety timeout for stuck key-down state
```

### 29.7 Security

```text
Do not treat operator_id as room password
Do not log private room password
Do not copy Operator Identity export to listener devices
Do not trust operator_id unless operator_verified is true
Ignore unknown fields
```

---

## 30. Summary

To build a Morsewurst listener:

1. Connect to `wss://morsewurst.duckdns.org`.
2. Send `client_hello` with `client_mode: "listener"`.
3. Receive `server_challenge`.
4. Send `auth`.
5. Receive `welcome`.
6. Process `key` or `tone` messages from the joined room.
7. If following one operator, require both `operator_verified: true` and the exact `operator_id`.
8. Remember that `operator_id` is only a room-local filter, not a room password and not a global subscription.

For simple external playback devices, use `key` messages:

```text
key.state == "down" -> start tone
key.state == "up"   -> stop tone
```

For more accurate buffered playback, use `tone` messages with a jitter buffer.

The current protocol combination is:

```text
WebSocket envelope: v5
key telemetry:      V1
listener mode:      read-only
operator filter:    client-side and room-local
```