"""
CLUTCH SHOT - Central configuration file.

Every tunable value in the game lives here so gameplay can be balanced
without touching the logic code. Constants are grouped by the system
that uses them. All angle values are in DEGREES, all time values are in
SECONDS, and all probabilities are values between 0.0 and 1.0 unless
noted otherwise.
"""

# ==========================================================
# PLAYER SETTINGS
# ==========================================================

# Which arm the player shoots with. Must be "right" or "left".
# This decides which wrist/elbow/shoulder the motion detector watches.
DOMINANT_ARM = "right"

# ==========================================================
# GAME SETTINGS
# ==========================================================

# Total length of one game in seconds.
GAME_DURATION = 60

# When the boss defender enters, measured in seconds REMAINING.
# Example: 15 means the boss shows up for the last 15 seconds.
BOSS_ENTER_TIME_REMAINING = 15

# ==========================================================
# CAMERA / POSE DETECTION SETTINGS
# ==========================================================

# Index passed to cv2.VideoCapture. 0 is usually the built-in webcam.
# Try 1 or 2 if you have multiple cameras or a virtual camera installed.
CAMERA_INDEX = 0

# Requested capture resolution. The camera may pick the closest
# supported size; the game scales the frame anyway.
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480

# MediaPipe Pose confidence thresholds (0.0 - 1.0).
# Higher = fewer false detections but pose may drop out more often.
POSE_DETECTION_CONFIDENCE = 0.5
POSE_TRACKING_CONFIDENCE = 0.5

# MediaPipe model complexity: 0 = fastest, 1 = balanced, 2 = most accurate.
# 1 is a good default for laptops.
POSE_MODEL_COMPLEXITY = 1

# A landmark with visibility below this value is treated as "not visible".
# Used to decide whether we can trust the player's pose this frame.
MIN_LANDMARK_VISIBILITY = 0.5

# ==========================================================
# SHOT MOTION DETECTION (state machine thresholds)
# ==========================================================
# The detector watches the shooting-side elbow, wrist, knee and shoulder.
# Note on coordinates: MediaPipe y-values are NORMALIZED (0.0 = top of
# frame, 1.0 = bottom), so "moving up" means y is DECREASING.

# --- LOADING phase (player dips before the shot) ---
# Knee angle below this means the knees are considered "bent".
# A perfectly straight leg is ~180 degrees.
KNEE_BEND_ANGLE = 160

# Elbow angle below this during loading means the shooting arm is "cocked".
ELBOW_LOADED_ANGLE = 110

# --- RELEASED phase (the actual shot) ---
# Elbow angle above this at release counts as a fully extended arm.
ELBOW_EXTENDED_ANGLE = 150

# The shooting wrist must rise this far ABOVE the shoulder (in normalized
# screen units) for the motion to count as a release. Small value because
# y is normalized: 0.05 is about 5% of the frame height.
WRIST_ABOVE_SHOULDER_MARGIN = 0.0

# Minimum upward wrist speed (normalized units per second) during RISING.
# Filters out slow drifting of the arm.
MIN_WRIST_RISE_SPEED = 0.15

# --- COOLDOWN ---
# Seconds after a detected shot during which no new shot can start.
SHOT_COOLDOWN = 1.5

# ==========================================================
# SHOT FAKE DETECTION
# ==========================================================

# A fake = the wrist rose at least this much (normalized units) above its
# idle height, but the player came back down WITHOUT extending the elbow.
FAKE_MIN_WRIST_RISE = 0.08

# If the elbow exceeded this angle, it's a real shot attempt, not a fake.
FAKE_MAX_ELBOW_ANGLE = 140

# After a successful fake, the player has this many seconds to take the
# follow-up shot and earn the fake bonus.
FAKE_FOLLOWUP_WINDOW = 2.0

# ==========================================================
# FORM SCORE WEIGHTS (must sum to 1.0)
# ==========================================================
# The form score (0-100) is a weighted average of five components.

FORM_WEIGHT_ELBOW_EXTENSION = 0.30  # arm fully extended at release
FORM_WEIGHT_KNEE_BEND = 0.20        # used the legs before the shot
FORM_WEIGHT_VERTICAL_RISE = 0.20    # body/wrist rose during the shot
FORM_WEIGHT_BALANCE = 0.15          # shoulders/hips level, no leaning
FORM_WEIGHT_SMOOTHNESS = 0.15       # steady upward wrist movement

# Form score bands used for feedback messages and the bonus point.
FORM_EXCELLENT_THRESHOLD = 85   # +1 bonus point at or above this
FORM_GOOD_THRESHOLD = 70
FORM_DECENT_THRESHOLD = 50

# ==========================================================
# SHOT SUCCESS PROBABILITY
# ==========================================================

# Every shot starts from this probability before modifiers.
BASE_SHOT_PROBABILITY = 0.25

# form_bonus = form_score / FORM_BONUS_DIVISOR  (so 100 form = +0.5)
FORM_BONUS_DIVISOR = 200

# Defender pressure modifiers, keyed by pressure level name.
PRESSURE_MODIFIERS = {
    "OPEN": +0.15,
    "LIGHT_CONTEST": -0.05,
    "HEAVY_CONTEST": -0.20,
}

# Extra probability for the follow-up shot after a defender bites a fake.
FAKE_SHOT_BONUS = 0.10

# Final probability is clamped into this range so the game never feels
# impossible or automatic.
MIN_SHOT_PROBABILITY = 0.05
MAX_SHOT_PROBABILITY = 0.90

# ==========================================================
# SCORING (points)
# ==========================================================

POINTS_MADE_SHOT = 2        # any made shot
BONUS_OPEN_SHOT = 1         # made shot while OPEN
BONUS_AFTER_FAKE = 1        # made shot inside the fake follow-up window
BONUS_EXCELLENT_FORM = 1    # made shot with form >= FORM_EXCELLENT_THRESHOLD

# ==========================================================
# FATIGUE SYSTEM (0 - 100 scale)
# ==========================================================

FATIGUE_MAX = 100
FATIGUE_PER_SHOT = 12          # fatigue added on every shot ATTEMPT
FATIGUE_RECOVERY_PER_SEC = 4   # fatigue removed per second of rest

# How fatigue converts to a probability penalty:
# fatigue_penalty = (fatigue / 100) * FATIGUE_MAX_PENALTY
FATIGUE_MAX_PENALTY = 0.15

# ==========================================================
# UI / WINDOW SETTINGS
# ==========================================================

WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 720
TARGET_FPS = 30

# Basketball-themed color palette (RGB tuples for Pygame).
COLOR_BACKGROUND = (18, 18, 24)      # near-black court
COLOR_ACCENT = (255, 140, 0)         # basketball orange
COLOR_TEXT = (245, 245, 245)         # white
COLOR_TEXT_DIM = (160, 160, 160)     # gray for labels
COLOR_SUCCESS = (60, 200, 90)        # made shot green
COLOR_FAIL = (220, 60, 60)           # missed shot red
COLOR_WARNING = (250, 200, 60)       # contest warning yellow
