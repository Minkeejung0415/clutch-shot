"""
Shot-motion state machine.

Watches the player's joints frame by frame and decides when a SHOT or a
SHOT FAKE happened. The states mirror a real jump shot:

    IDLE      standing normally
    LOADING   knees bend / shooting elbow cocks (the "dip")
    RISING    wrist and elbow drive upward
    RELEASED  wrist above the shoulder with the arm extended -> SHOT!
    COOLDOWN  short lockout so one motion only counts once

A FAKE is a rise that comes back DOWN without the elbow ever extending:
the player pumped the ball but didn't let it go.

The detector only RECOGNIZES motion; it does not score it. When a shot
is detected it returns an event carrying the raw measurements
(release elbow angle, deepest knee bend, wrist rise, balance samples)
and game/scoring.py turns those into a 0-100 form score.

Coordinate reminder: MediaPipe y is normalized with 0 at the TOP of the
frame, so "the wrist moved up" means its y value DECREASED.
"""

import config
from vision.biomechanics import calculate_angle, midpoint, tilt_degrees

# State names as constants so typos fail loudly instead of silently.
IDLE = "IDLE"
LOADING = "LOADING"
RISING = "RISING"
RELEASED = "RELEASED"
COOLDOWN = "COOLDOWN"


class MotionDetector:
    """Turns a stream of pose frames into SHOT / FAKE events."""

    def __init__(self):
        # Which side of the body to watch ("right" or "left").
        self.side = config.DOMINANT_ARM

        self.state = IDLE
        self._state_since = 0.0       # timestamp of the last state change
        self._cooldown_length = config.SHOT_COOLDOWN

        # Slow-moving baseline of the wrist height while standing still.
        # Wrist rise during a shot is measured against this.
        self._idle_wrist_y = None

        # Previous-frame values for measuring movement speed.
        self._prev_wrist_y = None
        self._prev_time = None

        self._reset_motion_data()

    # ------------------------------------------------------------------
    # Per-attempt measurement buffers
    # ------------------------------------------------------------------
    def _reset_motion_data(self):
        """Clear the measurements collected during one shot attempt."""
        self._min_knee_angle = 180.0   # deepest knee bend seen (LOADING+)
        self._max_elbow_angle = 0.0    # most extended the elbow got
        self._peak_wrist_rise = 0.0    # highest the wrist got above idle
        self._rise_up_frames = 0       # RISING frames where wrist moved up
        self._rise_total_frames = 0    # all RISING frames (for smoothness)
        self._tilt_samples = []        # body tilt during the motion
        self._start_hip_x = None       # hip x when the attempt began
        self._max_hip_drift = 0.0      # biggest sideways slide of the hips

    def _change_state(self, new_state, now):
        self.state = new_state
        self._state_since = now

    # ------------------------------------------------------------------
    # Main entry point - call once per frame
    # ------------------------------------------------------------------
    def update(self, joints, now):
        """
        Advance the state machine by one frame.

        Args:
            joints: dict of joint name -> (x, y, visibility) from
                    PoseTracker.process(), or None if no player visible.
            now:    current time in seconds (e.g. time.time()).

        Returns:
            None, or an event dict:
              {"type": "shot", "metrics": {...}}  - a completed shot
              {"type": "fake"}                    - a detected shot fake
        """
        # COOLDOWN ticks down even if the player leaves the frame.
        if self.state == COOLDOWN:
            if now - self._state_since >= self._cooldown_length:
                self._change_state(IDLE, now)
            return None

        if joints is None:
            # Lost the player mid-motion: abandon the attempt safely.
            if self.state != IDLE:
                self._change_state(IDLE, now)
            self._prev_wrist_y = None
            self._prev_time = None
            return None

        # ---- Measure everything we need this frame -------------------
        side = self.side
        wrist = joints[f"{side}_wrist"]
        elbow = joints[f"{side}_elbow"]
        shoulder = joints[f"{side}_shoulder"]

        # Elbow angle: shoulder -> elbow -> wrist (180 = straight arm).
        elbow_angle = calculate_angle(shoulder, elbow, wrist)
        # Knee angle on the shooting side: hip -> knee -> ankle.
        knee_angle = calculate_angle(
            joints[f"{side}_hip"], joints[f"{side}_knee"], joints[f"{side}_ankle"]
        )
        # Balance inputs: how level the shoulders/hips are, and how far
        # the body center slides sideways during the motion.
        shoulder_tilt = tilt_degrees(joints["left_shoulder"], joints["right_shoulder"])
        hip_tilt = tilt_degrees(joints["left_hip"], joints["right_hip"])
        hip_center = midpoint(joints["left_hip"], joints["right_hip"])

        # Upward wrist speed in normalized units/second (positive = up).
        wrist_speed_up = 0.0
        if self._prev_wrist_y is not None and self._prev_time is not None:
            dt = now - self._prev_time
            if dt > 0:
                wrist_speed_up = (self._prev_wrist_y - wrist[1]) / dt
        self._prev_wrist_y = wrist[1]
        self._prev_time = now

        event = None

        # ---- State transitions ---------------------------------------
        if self.state == IDLE:
            # Keep a slowly-updating baseline of the standing wrist
            # height (exponential moving average so brief twitches
            # don't drag it around).
            if self._idle_wrist_y is None:
                self._idle_wrist_y = wrist[1]
            else:
                self._idle_wrist_y = 0.9 * self._idle_wrist_y + 0.1 * wrist[1]

            # The shot starts when the player "loads": knees bend, the
            # shooting elbow cocks, or the wrist suddenly drives upward
            # (catches quick shooters who barely dip).
            loading = (
                knee_angle < config.KNEE_BEND_ANGLE
                or elbow_angle < config.ELBOW_LOADED_ANGLE
                or wrist_speed_up > config.MIN_WRIST_RISE_SPEED
            )
            if loading:
                self._reset_motion_data()
                self._start_hip_x = hip_center[0]
                self._min_knee_angle = knee_angle
                self._change_state(LOADING, now)

        elif self.state == LOADING:
            # Record the deepest dip - that's the knee-bend form factor.
            self._min_knee_angle = min(self._min_knee_angle, knee_angle)

            if wrist_speed_up > config.MIN_WRIST_RISE_SPEED:
                # The wrist took off: the shot is going up.
                self._change_state(RISING, now)
            elif now - self._state_since > config.LOADING_TIMEOUT:
                # Loaded up but never shot - just shifting weight.
                self._change_state(IDLE, now)

        elif self.state == RISING:
            # Keep collecting form measurements while the arm rises.
            self._min_knee_angle = min(self._min_knee_angle, knee_angle)
            self._max_elbow_angle = max(self._max_elbow_angle, elbow_angle)
            self._tilt_samples.append((shoulder_tilt + hip_tilt) / 2.0)

            self._rise_total_frames += 1
            if wrist_speed_up > 0:
                self._rise_up_frames += 1

            if self._idle_wrist_y is not None:
                rise = self._idle_wrist_y - wrist[1]
                self._peak_wrist_rise = max(self._peak_wrist_rise, rise)
            if self._start_hip_x is not None:
                drift = abs(hip_center[0] - self._start_hip_x)
                self._max_hip_drift = max(self._max_hip_drift, drift)

            # --- RELEASE check: wrist above the shoulder, arm extended,
            # and the player actually bent their knees at some point.
            wrist_above_shoulder = (
                wrist[1] < shoulder[1] - config.WRIST_ABOVE_SHOULDER_MARGIN
            )
            arm_extended = elbow_angle >= config.ELBOW_EXTENDED_ANGLE
            used_legs = self._min_knee_angle < config.SHOT_REQUIRED_KNEE_ANGLE

            if wrist_above_shoulder and arm_extended and used_legs:
                event = {
                    "type": "shot",
                    "metrics": self._build_shot_metrics(elbow_angle),
                }
                self._cooldown_length = config.SHOT_COOLDOWN
                self._change_state(COOLDOWN, now)

            # --- FAKE check: the wrist clearly rose, is now coming back
            # DOWN, and the elbow never extended -> pump fake.
            elif (
                wrist_speed_up < -config.MIN_WRIST_RISE_SPEED / 2
                and self._peak_wrist_rise >= config.FAKE_MIN_WRIST_RISE
                and self._max_elbow_angle <= config.FAKE_MAX_ELBOW_ANGLE
            ):
                event = {"type": "fake"}
                # Short cooldown so the follow-up shot can come right away.
                self._cooldown_length = config.FAKE_COOLDOWN
                self._change_state(COOLDOWN, now)

            elif now - self._state_since > config.RISING_TIMEOUT:
                # Arm hovered without releasing - not a real attempt.
                self._change_state(IDLE, now)

        return event

    # ------------------------------------------------------------------
    def _build_shot_metrics(self, release_elbow_angle):
        """Package the raw measurements scoring.py needs for this shot."""
        # Smoothness: what fraction of the rise was actually upward
        # movement. A clean stroke goes straight up (close to 1.0).
        if self._rise_total_frames > 0:
            smoothness = self._rise_up_frames / self._rise_total_frames
        else:
            smoothness = 0.0

        # Average body tilt during the motion (0 = perfectly level).
        if self._tilt_samples:
            avg_tilt = sum(self._tilt_samples) / len(self._tilt_samples)
        else:
            avg_tilt = 0.0

        return {
            "release_elbow_angle": release_elbow_angle,
            "min_knee_angle": self._min_knee_angle,
            "wrist_rise": self._peak_wrist_rise,
            "avg_tilt": avg_tilt,
            "hip_drift": self._max_hip_drift,
            "smoothness": smoothness,
        }
