"""
CLUTCH SHOT - Central configuration file.

Every tunable value in the game lives here so gameplay can be balanced
without touching the logic code. Constants are grouped by the system
that uses them. All time values are in SECONDS; positions and distances
use MediaPipe's normalized coordinates (0.0-1.0 across the frame)
unless noted otherwise.
"""

# ==========================================================
# PLAYER SETTINGS
# ==========================================================

# Used by the --vision-check diagnostic overlay. The game itself watches
# BOTH hands (dribble/layup work with either hand).
DOMINANT_ARM = "right"

# ==========================================================
# GAME SETTINGS
# ==========================================================

# Total length of one game in seconds.
GAME_DURATION = 60

# Defender difficulty used until the player picks one on the start
# screen (keys 1/2/3). Must be a key of DIFFICULTY_PROFILES below.
DEFAULT_DIFFICULTY = "MEDIUM"

# ==========================================================
# CAMERA / POSE DETECTION SETTINGS
# ==========================================================

# Index passed to cv2.VideoCapture. 0 is usually the built-in webcam.
CAMERA_INDEX = 0
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480

# MediaPipe Pose confidence thresholds (0.0 - 1.0).
POSE_DETECTION_CONFIDENCE = 0.5
POSE_TRACKING_CONFIDENCE = 0.5

# MediaPipe model complexity: 0 = fastest, 1 = balanced, 2 = accurate.
# 0 keeps latency low, which matters for fast move chains.
POSE_MODEL_COMPLEXITY = 0

# A landmark with visibility below this is treated as "not visible".
MIN_LANDMARK_VISIBILITY = 0.5

# ==========================================================
# MOTION CLASSIFICATION
# ==========================================================
# The five moves are classified from hand height relative to the
# shoulder line plus short timing windows. y is normalized with 0 at
# the TOP of the frame, so "above the shoulder" means a SMALLER y.

# A wrist counts as "up" when it is this far above the shoulder line
# (average of both shoulders' y). Small margin filters jitter.
HANDS_UP_MARGIN = 0.02

# SHOT: both hands up, held continuously for this long.
SHOT_HOLD_TIME = 1.0

# SHOT FAKE: both hands went up but came back below the shoulders in
# less than this. (By definition the complement of SHOT_HOLD_TIME.)
FAKE_MAX_TIME = 1.0

# LAYUP: exactly one hand up for this long (the wait filters out the
# split second where the second hand is still on its way up to a shot).
LAYUP_CONFIRM_TIME = 0.25

# DRIBBLE: a below-shoulder hand reversing vertical direction.
DRIBBLE_MIN_SPEED = 0.25      # wrist speed (norm units/s) to count as moving
DRIBBLE_MIN_AMPLITUDE = 0.035  # vertical travel needed between reversals
DRIBBLE_MIN_INTERVAL = 0.12    # min seconds between two counted bounces

# STEPBACK: the body moves AWAY from the camera, detected as the
# shoulder width shrinking. Compare now vs ~STEPBACK_WINDOW seconds ago.
STEPBACK_WINDOW = 0.45
STEPBACK_SHRINK = 0.10        # width must shrink by 10%
STEPBACK_COOLDOWN = 1.0       # min seconds between stepbacks

# ==========================================================
# DECEPTION / COMBOS
# ==========================================================
# Chaining DIFFERENT setup moves (dribble, fake, stepback) within this
# window raises the player's "deception" level (0-3 distinct moves).
# Deception makes the defender easier to fool and harder to block with.
DECEPTION_WINDOW = 2.5

# A shot released within this many seconds of a stepback is a
# STEPBACK SHOT and is worth 3 points instead of 2.
STEPBACK_SHOT_WINDOW = 2.0

# ==========================================================
# DEFENDER AI
# ==========================================================
# One live defender guards the rim. His skill comes entirely from the
# difficulty profile; whether he falls for moves also depends on the
# player's deception level.
#
# Profile fields:
#   bite_base             chance to jump at a shot fake (deception 0)
#   bite_deception_bonus  extra bite chance per deception level
#   stumble_chance        chance a setup move at max deception makes him
#                         stumble (off-balance, can't contest)
#   block_shot            base chance to BLOCK a jump shot he contests
#   block_layup           base chance to BLOCK a layup at the rim
#   contest_penalty       probability taken off a contested attempt
#   closing_speed         separation units recovered per second
#   recover_time          seconds off-balance after landing from a jump
#   shuffle_speed         lateral movement speed (court units/s, visual)
DIFFICULTY_PROFILES = {
    "EASY": {
        "bite_base": 0.55, "bite_deception_bonus": 0.15, "stumble_chance": 0.35,
        "block_shot": 0.08, "block_layup": 0.18, "contest_penalty": 0.15,
        "closing_speed": 0.45, "recover_time": 1.3, "shuffle_speed": 1.2,
    },
    "MEDIUM": {
        "bite_base": 0.35, "bite_deception_bonus": 0.12, "stumble_chance": 0.20,
        "block_shot": 0.15, "block_layup": 0.30, "contest_penalty": 0.22,
        "closing_speed": 0.75, "recover_time": 0.9, "shuffle_speed": 1.8,
    },
    "HARD": {
        "bite_base": 0.16, "bite_deception_bonus": 0.10, "stumble_chance": 0.10,
        "block_shot": 0.24, "block_layup": 0.42, "contest_penalty": 0.30,
        "closing_speed": 1.10, "recover_time": 0.6, "shuffle_speed": 2.6,
    },
}

# How long the defender hangs in the air after biting a fake, and how
# long his contest jump lasts. While airborne he cannot defend.
DEFENDER_AIR_TIME = 0.55
DEFENDER_CONTEST_TIME = 0.45
DEFENDER_BEATEN_TIME = 0.8     # stumble duration after getting crossed

# Separation (distance the player creates, in abstract "steps").
STEPBACK_SEPARATION = 1.0      # one stepback buys one step of space
MAX_SEPARATION = 2.5
OPEN_SEPARATION = 1.6          # at this much space a jump shot is OPEN
BLOCK_SEPARATION_PENALTY = 0.08  # block chance lost per step of space
BLOCK_DECEPTION_PENALTY = 0.04   # block chance lost per deception level

# ==========================================================
# ATTEMPT RESOLUTION (make / miss / block)
# ==========================================================

LAYUP_BASE_PROB = 0.80    # layups are easy... if they don't get blocked
SHOT_BASE_PROB = 0.62     # neutral jump shot
OPEN_BONUS = 0.15         # defender airborne / beaten / too far away
THREE_PENALTY = 0.12      # stepback threes are longer shots
SEPARATION_PROB_BONUS = 0.05   # per step of space (capped at 2 steps)

# Final make probability is clamped into this range.
MIN_SHOT_PROBABILITY = 0.05
MAX_SHOT_PROBABILITY = 0.95

# ==========================================================
# POINTS
# ==========================================================

POINTS_LAYUP = 2
POINTS_SHOT = 2
POINTS_STEPBACK_SHOT = 3

# ==========================================================
# FATIGUE SYSTEM (0 - 100 scale)
# ==========================================================

FATIGUE_MAX = 100
FATIGUE_PER_SHOT = 12          # fatigue added per shot/layup attempt
FATIGUE_RECOVERY_PER_SEC = 4   # fatigue removed per second of rest

# fatigue_penalty = (fatigue / 100) * FATIGUE_MAX_PENALTY
FATIGUE_MAX_PENALTY = 0.15

# ==========================================================
# UI / WINDOW SETTINGS
# ==========================================================

WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 720
TARGET_FPS = 30

# How long an action message ("BLOCKED!", ...) stays on screen.
MESSAGE_DURATION = 2.2

# Basketball-themed color palette (RGB tuples for Pygame).
COLOR_BACKGROUND = (18, 18, 24)      # near-black
COLOR_ACCENT = (255, 140, 0)         # basketball orange
COLOR_TEXT = (245, 245, 245)         # white
COLOR_TEXT_DIM = (160, 160, 160)     # gray for labels
COLOR_SUCCESS = (60, 200, 90)        # made shot green
COLOR_FAIL = (220, 60, 60)           # missed/blocked red
COLOR_WARNING = (250, 200, 60)       # yellow
COLOR_COURT = (52, 38, 28)           # hardwood floor
COLOR_COURT_LINES = (110, 90, 70)    # court markings
COLOR_DEFENDER = (200, 50, 60)       # defender's jersey
