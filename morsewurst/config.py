# ============================================================
# morsewurst/config.py
# ============================================================

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "Morsewurst"
APP_VERSION = "0.99.3"

# ============================================================
# Update check
# ============================================================

UPDATE_CHECK_ENABLED = True
UPDATE_CHECK_ON_STARTUP = True
UPDATE_CHECK_STARTUP_DELAY_MS = 1500
UPDATE_CHECK_TIMEOUT_SECONDS = 5.0
UPDATE_MANIFEST_URL = "https://kasperikoski.github.io/morsewurst/latest.json"
UPDATE_DOWNLOAD_PAGE_URL = "https://github.com/kasperikoski/morsewurst/releases"

BASE_DIR = Path(__file__).resolve().parent.parent


def resource_path(relative_path: str) -> Path:
    base_path = Path(getattr(sys, "_MEIPASS", BASE_DIR))
    return base_path / relative_path


# ============================================================
# Data and assets
# ============================================================
SOUND_DIR = resource_path("Assets/sounds")

STARTUP_SCREEN_IMAGE = resource_path("Assets/img/startup_screen.png")
STARTUP_SCREEN_MIN_MS = 3000

# Network splash screen shown while the lobby connection is being prepared.
NETWORK_STARTUP_SCREEN_IMAGE = resource_path("Assets/img/network_startup_screen.png")
NETWORK_STARTUP_SCREEN_MIN_MS = 3000
NETWORK_STARTUP_READY_TIMEOUT_SECONDS = 12.0

APP_DATA_DIR = Path(os.environ.get("APPDATA", str(Path.home()))) / "Morsewurst"
DATA_DIR = APP_DATA_DIR / "data"
DB_PATH = DATA_DIR / "morsewurst.sqlite3"

DEBUG_DIR = DATA_DIR / "debug"
DEBUG_LATEST_SNAPSHOT_PATH = DEBUG_DIR / "latest_round_debug.json"
DEBUG_HISTORY_PATH = DEBUG_DIR / "debug_history.jsonl"


# ============================================================
# Sound settings
# ============================================================
DEFAULT_SOUND_ENABLED = True
DEFAULT_SOUND_PRACTICE_COMPLETE = True
DEFAULT_SOUND_SERIAL_CONNECTED = True
DEFAULT_SOUND_SERIAL_DISCONNECTED = True
DEFAULT_SOUND_LEVEL_UP = True

SOUND_FILES = {
    "practice_complete": SOUND_DIR / "practice_complete.wav",
    "serial_connected": SOUND_DIR / "serial_connected.wav",
    "serial_disconnected": SOUND_DIR / "serial_disconnected.wav",
    "level_up": SOUND_DIR / "level_up.wav",
}


# ============================================================
# Debug capture
# ============================================================
DEBUG_SNAPSHOT_ENABLED_DEFAULT = False
DEBUG_SNAPSHOT_SAVE_HISTORY_DEFAULT = True


# ============================================================
# Serial settings
# ============================================================
SERIAL_BAUDRATE = 115200
SERIAL_READ_TIMEOUT_SECONDS = 0.2

SERIAL_AUTO_CONNECT_DEFAULT = True
SERIAL_AUTO_CONNECT_INTERVAL_MS = 5000
SERIAL_AUTO_CONNECT_PROBE_SECONDS = 6.0
SERIAL_AUTO_CONNECT_DEVICE_APP = "morsewurst"
SERIAL_AUTO_CONNECT_DEVICE_NAME = "Morsewurst"
SERIAL_AUTO_CONNECT_MODE = "raw_timing"
SERIAL_AUTO_CONNECT_ACCEPT_PLAIN_HEARTBEAT = True


# ============================================================
# Keyboard Morse input
# ============================================================

# Whether computer keyboard Morse input is enabled by default.
KEYBOARD_MORSE_DEFAULT_ENABLED = False

# Tkinter keysym used as the virtual straight key.
# Common alternatives: "space", "Control_R", "Control_L", "F9", "F12".
KEYBOARD_MORSE_DEFAULT_KEY = "space"

# Common keyboard keys that can be used as a virtual straight key.
# The first value is shown to the user. The second value is Tkinter's keysym.
KEYBOARD_MORSE_KEY_OPTIONS = (
    ("Välilyönti", "space"),
    ("Enter", "Return"),
    ("Nuoli ylös", "Up"),
    ("Nuoli alas", "Down"),
    ("Nuoli vasemmalle", "Left"),
    ("Nuoli oikealle", "Right"),
    ("Oikea Ctrl", "Control_R"),
    ("Vasen Ctrl", "Control_L"),
    ("Oikea Shift", "Shift_R"),
    ("Vasen Shift", "Shift_L"),
    ("Alt Gr", "ISO_Level3_Shift"),
    ("Vasen Alt", "Alt_L"),
    ("F8", "F8"),
    ("F9", "F9"),
    ("F10", "F10"),
    ("F11", "F11"),
    ("F12", "F12"),
)

# Ignore accidental extremely short key taps below this duration.
KEYBOARD_MORSE_MIN_TONE_US = 1_000


# ============================================================
# UI layout
# ============================================================
TELEMETRY_DISPLAY_MAX_CHARS = 60
RAW_TELEMETRY_PIXELS_PER_UNIT = 8.0
RAW_TELEMETRY_MAX_CANVAS_WIDTH = 20000

UI_POLL_INTERVAL_MS = 40
TIMER_TICK_MS = 100

UI_WINDOW_GEOMETRY = "1280x880"
UI_MIN_WIDTH = 1280
UI_MIN_HEIGHT = 880
UI_RIGHT_WIDTH = 350
UI_TARGET_WRAP_LENGTH = 820
UI_TELEMETRY_WRAP_LENGTH = 740
UI_RAW_TELEMETRY_HEIGHT = 72
UI_SUMMARY_ROW_HEIGHT = 330
UI_GENERAL_INFO_WIDTH = 360

HISTORY_VISIBLE_ROWS = 10
PROBLEM_VISIBLE_ROWS = 8
DELETE_SESSIONS_VISIBLE_ROWS = 14
PROBLEM_CHARACTER_DISPLAY_LIMIT = 10_000


# ============================================================
# Challenge defaults
# ============================================================
DEFAULT_MIN_GROUPS = 1
DEFAULT_MAX_GROUPS = 3
DEFAULT_MIN_CHARS_PER_GROUP = 3
DEFAULT_MAX_CHARS_PER_GROUP = 7
DEFAULT_PRACTICE_ROUNDS = 10
DEFAULT_TARGET_WPM = 15

LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
NUMBERS = "0123456789"
PUNCTUATION = ".,?!/()&:;=+-_\"@$'"


# ============================================================
# WX-MOR practice mode
# ============================================================
DEFAULT_PRACTICE_WXMOR = False
DEFAULT_WXMOR_PROFILE = "auto"

WXMOR_PROFILE_OPTIONS = (
    "auto",
    "minimum",
    "basic",
    "compact",
    "extended",
)

WXMOR_SCENARIO_WEIGHTS = {
    "clear_cold": 1.0,
    "clear_summer": 1.0,
    "cloudy_dry": 1.2,
    "rain": 1.3,
    "fog": 0.8,
    "snow": 1.2,
    "heavy_snow": 0.7,
    "slippery": 0.7,
    "windy": 0.8,
    "good_visibility": 1.0,
}

WXMOR_LOCATIONS: list[str] = []


# ============================================================
# Problem character practice
# ============================================================
DEFAULT_PROBLEM_RECENT_ROUNDS = 500
DEFAULT_PROBLEM_CHAR_WEIGHT_PERCENT = 30
DEFAULT_PROBLEM_CHAR_LIMIT = 12
DEFAULT_PROBLEM_CHAR_CANDIDATE_LIMIT = 50


# ============================================================
# Effective WPM suggestion
# ============================================================
DEFAULT_EFFECTIVE_WPM_RECENT_ROUNDS = 1000
DEFAULT_EFFECTIVE_WPM_MIN_ACCURACY = 90
DEFAULT_EFFECTIVE_WPM_MIN_CLEANLINESS = 85
EFFECTIVE_WPM_MIN_ROUNDS_REQUIRED = 3
EFFECTIVE_WPM_MIN_WPM = 5
EFFECTIVE_WPM_MAX_WPM = 80


# ============================================================
# Profile-aware decoder defaults
# ============================================================
# These are internal guardrails. They are intentionally not exposed as many
# separate user-facing recognition controls.


# ------------------------------------------------------------
# Basic decoder output
# ------------------------------------------------------------

# Character used when a decoded Morse pattern cannot be recognized.
DECODER_UNKNOWN_CHAR = "�"


# ------------------------------------------------------------
# Absolute timing safety limits
# ------------------------------------------------------------

# Minimum allowed element unit duration in microseconds.
DECODER_MIN_ELEMENT_UNIT_US = 10_000.0

# Maximum allowed element unit duration in microseconds.
DECODER_MAX_ELEMENT_UNIT_US = 1_000_000.0

# Minimum allowed gap unit duration in microseconds.
DECODER_MIN_GAP_UNIT_US = 10_000.0

# Maximum allowed gap unit duration in microseconds.
DECODER_MAX_GAP_UNIT_US = 1_000_000.0


# ------------------------------------------------------------
# Morse timing ratios and gap thresholds
# ------------------------------------------------------------

# Target dash-to-dot ratio used by the decoder.
DECODER_DOT_DASH_RATIO_TARGET = 3.0

# Element length threshold in units for classifying a tone as a dash.
DECODER_DASH_THRESHOLD_UNITS = 2.0

# Generic letter gap threshold in element units.
DECODER_LETTER_GAP_UNITS = 3.0

# Generic word gap threshold in element units.
DECODER_WORD_GAP_UNITS = 7.0

# Straight-key letter gap threshold in element units.
DECODER_STRAIGHT_LETTER_GAP_UNITS = 3.0

# Straight-key word gap threshold in element units.
DECODER_STRAIGHT_WORD_GAP_UNITS = 7.0

# Iambic-keyer letter gap threshold in element units.
DECODER_IAMBIC_LETTER_GAP_UNITS = 3.0

# Iambic-keyer word gap threshold in element units.
DECODER_IAMBIC_WORD_GAP_UNITS = 7.0


# ------------------------------------------------------------
# Character completion and gap tolerance
# ------------------------------------------------------------

# Idle duration in element units after which a straight-key character is considered complete.
DECODER_STRAIGHT_COMPLETION_IDLE_UNITS = 7.0

# Idle duration in element units after which an iambic-keyer character is considered complete.
DECODER_IAMBIC_COMPLETION_IDLE_UNITS = 4.8

# Tolerance added around gap thresholds when classifying boundaries.
DECODER_GAP_TOLERANCE_UNITS = 0.15


# ------------------------------------------------------------
# Adaptive timing sample requirements
# ------------------------------------------------------------

# Minimum number of straight-key tone elements required for element timing estimation.
DECODER_STRAIGHT_ELEMENT_MIN_SAMPLES = 4

# Minimum number of straight-key gaps required for gap timing estimation.
DECODER_STRAIGHT_GAP_MIN_SAMPLES = 3

# Minimum number of iambic-keyer gaps required for gap timing estimation.
DECODER_IAMBIC_GAP_MIN_SAMPLES = 2

# Maximum gap length in units that can still be used for adaptive gap learning.
DECODER_MAX_GAP_FOR_LEARNING_UNITS = 30.0


# ------------------------------------------------------------
# Timing profile selection and quality gates
# ------------------------------------------------------------

# Whether timing profiles are enabled by default.
DECODER_USE_TIMING_PROFILE_DEFAULT = True

# Minimum number of source-specific target characters required for timing profile learning.
DECODER_PROFILE_MIN_TARGET_CHARS = 12

# Number of recent rounds considered when building a timing profile.
DECODER_PROFILE_RECENT_ROUNDS = 300

# Minimum accuracy required for a round to be considered for timing profile learning.
DECODER_PROFILE_MIN_ACCURACY = 90.0

# Minimum cleanliness required for a round to be considered for timing profile learning.
DECODER_PROFILE_MIN_CLEANLINESS = 85.0

# Minimum timing score required for a round to be considered for timing profile learning.
DECODER_PROFILE_MIN_TIMING_SCORE = 30.0

# Maximum allowed single element duration in units for timing profile learning eligibility.
DECODER_PROFILE_MAX_ELEMENT_UNITS = 12.0

# Maximum allowed single gap duration in units for timing profile learning eligibility.
DECODER_PROFILE_MAX_GAP_UNITS = 30.0

# Whether rounds with extreme element durations are rejected from timing profile learning.
DECODER_PROFILE_REJECT_EXTREME_ELEMENTS = True

# Whether rounds with extreme gap durations are rejected from timing profile learning.
DECODER_PROFILE_REJECT_EXTREME_GAPS = True


# ------------------------------------------------------------
# Timing profile activation requirements
# ------------------------------------------------------------

# Minimum number of qualified rounds required before a timing profile is trusted.
DECODER_PROFILE_MIN_ROUNDS_REQUIRED = 100

# Minimum timing profile confidence required before it can be used as a decoder seed.
DECODER_PROFILE_MIN_CONFIDENCE_FOR_SEED = 0.30

# Minimum straight-key gap unit to element unit ratio required for profile validity.
DECODER_STRAIGHT_GAP_MIN_ELEMENT_RATIO = 0.90

# Minimum iambic-keyer gap unit to element unit ratio required for profile validity.
DECODER_IAMBIC_GAP_MIN_ELEMENT_RATIO = 0.80

# Accepted profile rounds needed before displayed profile confidence reaches 100%.
DECODER_PROFILE_CONFIDENCE_FULL_ROUNDS = 300


# ------------------------------------------------------------
# Timing profile drift limits
# ------------------------------------------------------------

# Maximum allowed element unit change ratio when updating an existing timing profile.
DECODER_PROFILE_MAX_ELEMENT_CHANGE_RATIO = 0.10

# Maximum allowed gap unit change ratio when updating an existing timing profile.
DECODER_PROFILE_MAX_GAP_CHANGE_RATIO = 0.15


# ------------------------------------------------------------
# Timing profile outlier filtering
# ------------------------------------------------------------

# Allowed element unit outlier ratio when filtering timing profile samples.
DECODER_PROFILE_ELEMENT_OUTLIER_RATIO = 0.30

# Allowed gap unit outlier ratio when filtering timing profile samples.
DECODER_PROFILE_GAP_OUTLIER_RATIO = 0.40


# ------------------------------------------------------------
# Automatic round completion
# ------------------------------------------------------------

# Whether a round can be finished automatically after sufficient idle time.
DECODER_AUTO_FINISH_ON_IDLE = True

# Idle duration in element units required before automatic round completion.
DECODER_AUTO_FINISH_IDLE_UNITS = 14.0

# Minimum elapsed round time in seconds before automatic round completion is allowed.
DECODER_AUTO_FINISH_MIN_SECONDS = 2.0


# ============================================================
# Round score weights
# ============================================================
ROUND_SCORE_ACCURACY_WEIGHT = 0.60
ROUND_SCORE_CLEANLINESS_WEIGHT = 0.20
ROUND_SCORE_SPEED_WEIGHT = 0.10
ROUND_SCORE_TIMING_WEIGHT = 0.10

ROUND_NET_WPM_TIMING_MIN_FACTOR = 0.90
ROUND_NET_WPM_TIMING_MAX_FACTOR = 1.00


# ============================================================
# Timing quality scoring
# ============================================================
SKILL_RATING_CAP_BY_TARGET_WPM = True
DEFAULT_SKILL_RATING_RECENT_ROUNDS = 1000
SKILL_RATING_MODEL_VERSION = 1
SKILL_RATING_MIN_TARGET_CHARS = 12
SKILL_RATING_MIN_QUALIFIED_ROUNDS = 50
SKILL_RATING_QUALIFIED_MIN_ACCURACY = 90.0
SKILL_RATING_QUALIFIED_MIN_CLEANLINESS = 85.0
SKILL_RATING_CHARACTER_CONFIDENCE_K = 15.0
SKILL_RATING_COVERAGE_MIN_ATTEMPTS = 5
SKILL_RATING_SAMPLE_CONFIDENCE_K = 30.0
SKILL_RATING_MASTERY_ADJUSTMENT_MIN = 0.75
SKILL_RATING_MASTERY_ADJUSTMENT_MAX = 1.05
SKILL_RATING_TIMING_MIN_FACTOR = 0.85
SKILL_RATING_TIMING_MAX_FACTOR = 1.05
SKILL_RATING_TIMING_QUALITY_ENABLED = True
SKILL_RATING_TIMING_MIN_ELEMENTS = 8
SKILL_RATING_TIMING_MIN_DOTS = 3
SKILL_RATING_TIMING_MIN_DASHES = 3
SKILL_RATING_TIMING_MIN_GAPS = 3

STRAIGHT_RATIO_TARGET = 3.0
STRAIGHT_RATIO_ERROR_AT_ZERO = 1.50

SKILL_RATING_STRAIGHT_DOT_CONSISTENCY_WEIGHT = 0.25
SKILL_RATING_STRAIGHT_DASH_CONSISTENCY_WEIGHT = 0.25
SKILL_RATING_STRAIGHT_DASH_DOT_RATIO_WEIGHT = 0.30
SKILL_RATING_STRAIGHT_GAP_WEIGHT = 0.20
SKILL_RATING_IAMBIC_GAP_WEIGHT = 1.00
SKILL_RATING_STRAIGHT_TIMING_SOURCE_WEIGHT = 1.00
SKILL_RATING_IAMBIC_TIMING_SOURCE_WEIGHT = 0.60
SKILL_RATING_LETTER_GAP_WEIGHT = 0.75
SKILL_RATING_WORD_GAP_WEIGHT = 0.25
SKILL_RATING_TIMING_CONSISTENCY_CV_AT_ZERO = 0.70
SKILL_RATING_DASH_DOT_RATIO_TARGET = 3.0
SKILL_RATING_DASH_DOT_RATIO_ERROR_AT_ZERO = 1.50
SKILL_RATING_GAP_ERROR_AT_ZERO_UNITS = 3.0
SKILL_RATING_LETTER_GAP_MIN_UNITS = 2.0
SKILL_RATING_WORD_GAP_MIN_UNITS = 5.0
SKILL_RATING_IAMBIC_LETTER_GAP_UNITS = DECODER_IAMBIC_LETTER_GAP_UNITS
SKILL_RATING_IAMBIC_WORD_GAP_UNITS = DECODER_IAMBIC_WORD_GAP_UNITS
SKILL_RATING_STRAIGHT_LETTER_GAP_UNITS = DECODER_STRAIGHT_LETTER_GAP_UNITS
SKILL_RATING_STRAIGHT_WORD_GAP_UNITS = DECODER_STRAIGHT_WORD_GAP_UNITS

ROUND_TIMING_STRAIGHT_DOT_CONSISTENCY_WEIGHT = 0.20
ROUND_TIMING_STRAIGHT_DASH_CONSISTENCY_WEIGHT = 0.20
ROUND_TIMING_STRAIGHT_DASH_DOT_RATIO_WEIGHT = 0.25
ROUND_TIMING_STRAIGHT_GAP_WEIGHT = 0.35
ROUND_TIMING_IAMBIC_GAP_WEIGHT = 1.00

# Straight-key gap scoring inside the straight gap component.
ROUND_TIMING_STRAIGHT_INTRA_GAP_WEIGHT = 0.30
ROUND_TIMING_STRAIGHT_LETTER_GAP_WEIGHT = 0.55
ROUND_TIMING_STRAIGHT_WORD_GAP_WEIGHT = 0.15

# Iambic-keyer gap scoring. Intra-character gaps are not scored for iambic.
ROUND_TIMING_IAMBIC_LETTER_GAP_WEIGHT = 0.75
ROUND_TIMING_IAMBIC_WORD_GAP_WEIGHT = 0.25

ROUND_TIMING_STRAIGHT_SOURCE_WEIGHT = 1.00
ROUND_TIMING_IAMBIC_SOURCE_WEIGHT = 0.60
ROUND_TIMING_USE_TARGET_EXPECTATIONS = True

# ============================================================
# Network settings
# ============================================================

# Maximum number of queued outbound client messages before new messages are dropped.
CLIENT_SEND_QUEUE_MAX_MESSAGES = 500

# Maximum time allowed for sending one WebSocket message before reconnecting.
CLIENT_SEND_TIMEOUT_SECONDS = 5.0

# Maximum allowed local audio clock drift before the receive playback clock is reset.
NETWORK_AUDIO_CLOCK_DRIFT_RESET_SECONDS = 2.0

# Application pause length that is treated as sleep, resume, or a long UI freeze.
NETWORK_RESUME_RESET_GAP_SECONDS = 2.0

# Tone messages older than this are treated as stale after sleep, resume, or connection stalls.
NETWORK_STALE_TONE_DROP_MS = 5000