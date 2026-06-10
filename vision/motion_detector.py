"""
Shot-motion state machine (PHASE 2 - not yet implemented).

Will consume joint data from PoseTracker each frame and walk through:
    IDLE -> LOADING -> RISING -> RELEASED -> COOLDOWN
plus shot-fake detection (a rise that returns to neutral without the
elbow ever extending).

Thresholds live in config.py (KNEE_BEND_ANGLE, ELBOW_EXTENDED_ANGLE,
SHOT_COOLDOWN, FAKE_* values, ...).
"""
