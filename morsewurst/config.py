# ============================================================
# morsewurst/config.py
# ============================================================

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "Morsewurst"
APP_VERSION = "0.99.12.1"

# ============================================================
# Update check
# ============================================================

UPDATE_CHECK_ENABLED = True
UPDATE_CHECK_ON_STARTUP = True
UPDATE_CHECK_STARTUP_DELAY_MS = 1500
UPDATE_CHECK_TIMEOUT_SECONDS = 5.0
UPDATE_MANIFEST_URL = "https://kasperikoski.github.io/morsewurst/latest.json"
UPDATE_DOWNLOAD_PAGE_URL = "https://kasperikoski.fi/morsewurst"

BASE_DIR = Path(__file__).resolve().parent.parent


def resource_path(relative_path: str) -> Path:
    base_path = Path(getattr(sys, "_MEIPASS", BASE_DIR))
    return base_path / relative_path


# ============================================================
# Data and assets
# ============================================================
SOUND_DIR = resource_path("assets/sounds")

STARTUP_SCREEN_IMAGE = resource_path("assets/img/startup_screen.png")
STARTUP_SCREEN_MIN_MS = 3000

NETWORK_STARTUP_SCREEN_IMAGE = resource_path("assets/img/network_startup_screen.png")
NETWORK_STARTUP_SCREEN_MIN_MS = 3000
NETWORK_STARTUP_READY_TIMEOUT_SECONDS = 12.0

LANGUAGE_FLAG_DIR = resource_path("assets/img/flags")
LANGUAGE_FLAG_ICON_SUBSAMPLE = 1
LANGUAGE_FLAG_SPACING_PX = 8

APP_DATA_DIR = Path(os.environ.get("APPDATA", str(Path.home()))) / "Morsewurst"

# Global application data root. This remains stable even when the active
# user profile changes.
BASE_DATA_DIR = APP_DATA_DIR / "data"

PROFILES_DIR = BASE_DATA_DIR / "profiles"
PROFILE_REGISTRY_PATH = BASE_DATA_DIR / "profiles.json"
BACKUP_DIR = BASE_DATA_DIR / "Backups"

# Active profile data directory. This is changed during startup by the
# profile system before the database, UI settings or network settings are read.
DATA_DIR = BASE_DATA_DIR
DB_PATH = DATA_DIR / "morsewurst.sqlite3"

DEBUG_DIR = DATA_DIR / "debug"
DEBUG_LATEST_SNAPSHOT_PATH = DEBUG_DIR / "latest_round_debug.json"
DEBUG_HISTORY_PATH = DEBUG_DIR / "debug_history.jsonl"


def set_active_data_dir(data_dir: Path) -> None:
    """Set the active per-profile data directory for this process."""

    global DATA_DIR
    global DB_PATH
    global DEBUG_DIR
    global DEBUG_LATEST_SNAPSHOT_PATH
    global DEBUG_HISTORY_PATH

    DATA_DIR = Path(data_dir)
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
# Logging
# ============================================================
LOG_DIRNAME = "logs"
LOG_MAX_BYTES = 2 * 1024 * 1024
LOG_BACKUP_COUNT = 50


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

# Live telemetry throttling.
# These values affect only how often the UI redraws live information.
# They do not change adaptive decoding thresholds or final round scoring.
LIVE_TELEMETRY_REFRESH_MS = 100
LIVE_RESULT_REFRESH_MS = 300

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

# Koch receive-practice layout.
# The receive-practice window has its own geometry because it contains a wide
# copy area, comparison output, recent sessions and a right-side skill/problem
# summary stack. The geometry can be overridden by the user's saved UI settings.
UI_KOCH_WINDOW_GEOMETRY = "1260x1000"
UI_KOCH_WINDOW_MIN_WIDTH = 1200
UI_KOCH_WINDOW_MIN_HEIGHT = 920

# The right panel has a fixed width for the practice actions, receive-skill
# summary and difficult-character stack. The left practice area expands into the
# remaining space, so this is the main value to tune when adjusting the layout.
UI_KOCH_RIGHT_PANEL_WIDTH = 360

# Settings window.
UI_SETTINGS_WINDOW_GEOMETRY = "880x780"
UI_SETTINGS_WINDOW_MIN_WIDTH = 880
UI_SETTINGS_WINDOW_MIN_HEIGHT = 780

UI_MAX_SERIAL_EVENTS_PER_POLL = 8
UI_SERIAL_POLL_BACKLOG_DELAY_MS = 1

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
# Koch receive practice mode
# ============================================================
DEFAULT_KOCH_SEQUENCE = "classic"
DEFAULT_KOCH_MODE = "guided"
DEFAULT_KOCH_STAGE_INDEX = 2
DEFAULT_KOCH_TARGET_CHARS = 30
# Hard safety cap for generated receive-practice length. The time-aware
# alignment used by scoring is intentionally rich, so very long drills should
# be split into multiple sessions instead of one massive O(n*m) comparison.
DEFAULT_KOCH_MAX_TARGET_CHARS = 1000
DEFAULT_KOCH_MIN_TARGET_CHARS_ABSOLUTE = 30
DEFAULT_KOCH_MIN_TARGET_CHARS_ACTIVE_FACTOR = 1.50
DEFAULT_KOCH_CHARACTER_WPM = 20
DEFAULT_KOCH_EFFECTIVE_WPM = 15
DEFAULT_KOCH_TONE_HZ = 600
DEFAULT_KOCH_VOLUME_PERCENT = 70

# Rendered Koch playback sample rate. 8 kHz is intentionally used because
# Koch receive drills use narrow-band Morse tones plus deliberately lo-fi
# background noise. Keeping this low makes temporary WAV rendering much faster.
DEFAULT_KOCH_AUDIO_SAMPLE_RATE = 8_000

# Quiet generated radio-style background noise for Koch receive playback.
# This is rendered directly into the same temporary WAV as the Morse tones, so
# it does not require extra asset files or parallel audio playback. Keep the
# default volume low: the noise is meant to add atmosphere, not mask copying.
DEFAULT_KOCH_BACKGROUND_NOISE_ENABLED = True
DEFAULT_KOCH_BACKGROUND_NOISE_VOLUME_PERCENT = 5
DEFAULT_KOCH_BACKGROUND_NOISE_FADE_MS = 750
DEFAULT_KOCH_BACKGROUND_NOISE_LEAD_IN_MS = 750
DEFAULT_KOCH_BACKGROUND_NOISE_LOW_PASS_HZ = 3200
DEFAULT_KOCH_BACKGROUND_NOISE_HIGH_PASS_HZ = 250
DEFAULT_KOCH_BACKGROUND_NOISE_SEED = None

# Advanced radio-noise dynamics. These affect only the generated background
# noise, not the Morse tone itself. Keep the defaults subtle: the goal is to
# make the receiver sound alive without making copy practice unfair.
DEFAULT_KOCH_BACKGROUND_NOISE_FLUTTER_PERCENT = 10
DEFAULT_KOCH_BACKGROUND_NOISE_FLUTTER_SPEED_HZ = 0.45
DEFAULT_KOCH_BACKGROUND_NOISE_DRIFT_PERCENT = 18
DEFAULT_KOCH_BACKGROUND_NOISE_DRIFT_SPEED_HZ = 0.18
DEFAULT_KOCH_BACKGROUND_NOISE_BURST_CHANCE_PER_SECOND = 0.25
DEFAULT_KOCH_BACKGROUND_NOISE_BURST_STRENGTH_PERCENT = 70
DEFAULT_KOCH_BACKGROUND_NOISE_BURST_DECAY_MS = 180
DEFAULT_KOCH_BACKGROUND_NOISE_CRACKLE_CHANCE_PER_SECOND = 1.2
DEFAULT_KOCH_BACKGROUND_NOISE_CRACKLE_STRENGTH_PERCENT = 18
DEFAULT_KOCH_BACKGROUND_NOISE_DROPOUT_CHANCE_PER_SECOND = 0.08
DEFAULT_KOCH_BACKGROUND_NOISE_DROPOUT_DEPTH_PERCENT = 35
DEFAULT_KOCH_BACKGROUND_NOISE_DROPOUT_DECAY_MS = 650

DEFAULT_KOCH_PASS_ACCURACY = 90.0
DEFAULT_KOCH_PASS_CLEANLINESS = 85.0
DEFAULT_KOCH_NEW_CHAR_MIN_ATTEMPTS = 8
# In guided Koch receive practice, five consecutive pass-eligible failures on
# the same sequence and stage step the current practice stage down by one. The
# unlocked stage is not reduced, so the user can recover without losing access
# to already opened characters.
DEFAULT_KOCH_GUIDED_DEMOTE_AFTER_FAILURES = 5
DEFAULT_KOCH_GUIDED_MIN_STAGE = 2
DEFAULT_KOCH_NEW_CHAR_MIN_ACCURACY = 80.0
DEFAULT_KOCH_AUTO_SCORE_DELAY_MS = 1500
DEFAULT_KOCH_COUNTDOWN_SECONDS = 5
KOCH_RATING_FULL_SET_LEVEL_AT_20_WPM = 50.0
KOCH_RATING_FULL_SET_LEVEL_AT_40_WPM = 100.0
KOCH_RATING_MAX_LEVEL = 100.0

# Rolling Koch receive-skill model. This applies only to Koch receive practice,
# not to the main Morse sending skill rating.
KOCH_SKILL_MODEL_VERSION = 2
DEFAULT_KOCH_SKILL_RECENT_ROUNDS = 1000
DEFAULT_KOCH_SKILL_MIN_SESSIONS = 30
KOCH_SKILL_REFERENCE_CHARACTER_WPM = 20.0
KOCH_SKILL_REFERENCE_EFFECTIVE_WPM = 20.0
KOCH_SKILL_REFERENCE_TARGET_CHARS = 100.0
KOCH_SKILL_REFERENCE_ACCURACY = 90.0
KOCH_SKILL_REFERENCE_CLEANLINESS = 85.0
KOCH_SKILL_CHARACTER_WPM_EXPONENT = 0.35
KOCH_SKILL_EFFECTIVE_WPM_EXPONENT = 0.65
KOCH_SKILL_CLEANLINESS_BASE_FACTOR = 0.55
KOCH_SKILL_LENGTH_EXPONENT = 0.15
KOCH_SKILL_LENGTH_MIN_FACTOR = 0.75
KOCH_SKILL_LENGTH_MAX_FACTOR = 1.08

# Default long-term target distribution for generated practice characters.
# The values are weights used by the character mix bar. Active groups are
# scaled visually to fill the bar, and inactive groups are ignored by the
# challenge generator.
DEFAULT_CHARACTER_MIX_LETTERS_PERCENT = 70
DEFAULT_CHARACTER_MIX_NUMBERS_PERCENT = 25
DEFAULT_CHARACTER_MIX_PUNCTUATION_PERCENT = 5

CHARACTER_MIX_COLORS = {
    "letters": "#f2b8b5",
    "numbers": "#f7df8e",
    "punctuation": "#a7c7e7",
}


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

# Full-character-set coverage affects only the visible level/title progression.
# It does not change raw skill WPM, scoring, WPM values, character mastery or
# stored round data.

# Minimum total appearances in high-quality rounds before a full-charset character can count.
SKILL_RATING_FULL_CHARSET_MIN_ATTEMPTS = 15
# Minimum number of high-quality rounds containing the character before it can count.
SKILL_RATING_FULL_CHARSET_MIN_ROUNDS = 15
# Minimum character-specific accuracy within high-quality rounds before the character can count.
SKILL_RATING_FULL_CHARSET_MIN_ACCURACY = 75.0
SKILL_RATING_CHARSET_SCOPE_MIN_FACTOR = 0.70
SKILL_RATING_CHARSET_SCOPE_MAX_FACTOR = 1.00

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
# Network radio channel noise
# ============================================================
# Local-only receiver ambience for network rooms. This is never sent over the
# network and is mixed into the same local TonePlayer stream as received Morse.
NETWORK_RADIO_NOISE_ENABLED_DEFAULT = True
NETWORK_RADIO_NOISE_VOLUME_PERCENT_DEFAULT = 5
NETWORK_RADIO_NOISE_PROFILE_DEFAULT = "radio"
# The noise profile controls movement and interference. The tone preset controls
# the perceived brightness of the channel by selecting the band-pass filter.
NETWORK_RADIO_NOISE_TONE_DEFAULT = "low"
NETWORK_RADIO_NOISE_FADE_IN_MS = 700
NETWORK_RADIO_NOISE_FADE_OUT_MS = 700

NETWORK_RADIO_NOISE_TONE_NORMAL_LOW_PASS_HZ = 3200
NETWORK_RADIO_NOISE_TONE_NORMAL_HIGH_PASS_HZ = 250
NETWORK_RADIO_NOISE_TONE_LOW_LOW_PASS_HZ = 1800
NETWORK_RADIO_NOISE_TONE_LOW_HIGH_PASS_HZ = 100
NETWORK_RADIO_NOISE_TONE_DEEP_LOW_PASS_HZ = 950
NETWORK_RADIO_NOISE_TONE_DEEP_HIGH_PASS_HZ = 40

# Base profile used by the live network noise bed. Keep this a little quieter
# than Koch by default because network rooms may stay open for a long time.
NETWORK_RADIO_NOISE_LOW_PASS_HZ = 3200
NETWORK_RADIO_NOISE_HIGH_PASS_HZ = 250
NETWORK_RADIO_NOISE_SEED = None
NETWORK_RADIO_NOISE_FLUTTER_PERCENT = 8
NETWORK_RADIO_NOISE_FLUTTER_SPEED_HZ = 0.38
NETWORK_RADIO_NOISE_DRIFT_PERCENT = 14
NETWORK_RADIO_NOISE_DRIFT_SPEED_HZ = 0.14
NETWORK_RADIO_NOISE_BURST_CHANCE_PER_SECOND = 0.12
NETWORK_RADIO_NOISE_BURST_STRENGTH_PERCENT = 45
NETWORK_RADIO_NOISE_BURST_DECAY_MS = 190
NETWORK_RADIO_NOISE_CRACKLE_CHANCE_PER_SECOND = 0.65
NETWORK_RADIO_NOISE_CRACKLE_STRENGTH_PERCENT = 11
NETWORK_RADIO_NOISE_DROPOUT_CHANCE_PER_SECOND = 0.04
NETWORK_RADIO_NOISE_DROPOUT_DEPTH_PERCENT = 22
NETWORK_RADIO_NOISE_DROPOUT_DECAY_MS = 700

# Strong local transmit ducking approximates real transceiver behaviour: while
# sending, the receiver noise floor is heavily muted and the operator hears the
# sidetone instead. Remote receive ducking is gentler so incoming Morse still
# feels like it is riding over a live channel rather than muting it completely.
NETWORK_RADIO_NOISE_TX_DUCKING_ENABLED = True
NETWORK_RADIO_NOISE_TX_DUCKING_DEPTH_PERCENT = 85
NETWORK_RADIO_NOISE_TX_DUCKING_ATTACK_MS = 60
NETWORK_RADIO_NOISE_TX_DUCKING_RELEASE_MS = 500
NETWORK_RADIO_NOISE_TX_DUCKING_HOLD_MS = 350

NETWORK_RADIO_NOISE_RX_DUCKING_ENABLED = False
NETWORK_RADIO_NOISE_RX_DUCKING_DEPTH_PERCENT = 45
NETWORK_RADIO_NOISE_RX_DUCKING_ATTACK_MS = 80
NETWORK_RADIO_NOISE_RX_DUCKING_RELEASE_MS = 450
NETWORK_RADIO_NOISE_RX_DUCKING_HOLD_MS = 250

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