"""
Real-time move classifier for the five moves of CLUTCH SHOT.

The rules (all relative to the player's shoulder line):

  DRIBBLE   one hand BELOW the shoulders bouncing up and down
  LAYUP     exactly one hand ABOVE the shoulders (held a split second)
  SHOT      BOTH hands above the shoulders, held over 1 second
  SHOT FAKE both hands went up but came back below in under 1 second
  STEPBACK  the body moves backwards (away from the camera)

Unlike a slow multi-stage state machine, this classifier evaluates
every rule on every frame so moves chain instantly: a fake can flow
into a dribble into a stepback into a shot with no dead time. The only
intentional waits are the ones the rules themselves define (the 1 s
shot hold, and a 0.25 s confirmation so a layup isn't fired while the
second hand is still on its way up to a shot).

update() returns a LIST of events because two moves can legitimately
happen in the same frame (e.g. a stepback while dribbling).

Coordinate reminder: MediaPipe y is normalized with 0 at the TOP of the
frame, so "above the shoulders" means a SMALLER y value.
"""

from collections import deque

import config

# Event type names.
DRIBBLE = "dribble"
LAYUP = "layup"
SHOT = "shot"
SHOT_FAKE = "shot_fake"
STEPBACK = "stepback"


class MotionClassifier:
    """Turns a stream of pose frames into instant move events."""

    def __init__(self):
        self.reset()

    def reset(self):
        """Clear all temporal state (called on game restart)."""
        # --- shot / fake: the "raise episode" -------------------------
        # An episode starts when both hands first go up and ends when
        # both are back below the shoulders.
        self._episode_start = None    # when both hands FIRST went up
        self._both_up_since = None    # continuous both-up stretch start
        self._shot_fired = False      # shot already emitted this episode

        # --- layup -----------------------------------------------------
        self._one_up_since = None     # when exactly-one-hand-up started
        self._layup_fired = False     # blocks repeats until hand drops

        # --- dribble (tracked per hand) --------------------------------
        self._dribble = {
            "left": {"last_y": None, "dir": 0, "flip_y": None, "last_bounce": 0.0},
            "right": {"last_y": None, "dir": 0, "flip_y": None, "last_bounce": 0.0},
        }

        # --- stepback ---------------------------------------------------
        self._width_history = deque()  # (time, shoulder width) samples
        self._stepback_ready_at = 0.0  # cooldown gate

        self._prev_time = None
        # Snapshot for the UI (posture text + shot charge meter).
        self._status = {"posture": "NO PLAYER", "shot_progress": 0.0}

    # ------------------------------------------------------------------
    def status(self):
        """Live posture info for the UI: posture text and 0-1 progress
        of the current shot hold (drives the on-screen charge bar)."""
        return self._status

    # ------------------------------------------------------------------
    def update(self, joints, now):
        """
        Classify one frame.

        Args:
            joints: dict of joint name -> (x, y, visibility) from
                    PoseTracker.process(), or None if no player visible.
            now:    current time in seconds.

        Returns:
            list of event dicts, e.g. [{"type": "dribble", "hand": "left"}].
            Usually empty or one event; rarely two in the same frame.
        """
        if joints is None:
            # Player left the frame: drop transient motion state but keep
            # cooldowns so re-entering the frame can't spam events.
            self._episode_start = None
            self._both_up_since = None
            self._one_up_since = None
            for hand in self._dribble.values():
                hand["last_y"] = None
                hand["dir"] = 0
            self._width_history.clear()
            self._prev_time = now
            self._status = {"posture": "NO PLAYER", "shot_progress": 0.0}
            return []

        dt = (now - self._prev_time) if self._prev_time is not None else 0.0
        self._prev_time = now

        # ---- shared per-frame features --------------------------------
        # The shoulder line: average height of both shoulders.
        shoulder_level = (joints["left_shoulder"][1] + joints["right_shoulder"][1]) / 2.0
        up_cutoff = shoulder_level - config.HANDS_UP_MARGIN

        left_up = joints["left_wrist"][1] < up_cutoff
        right_up = joints["right_wrist"][1] < up_cutoff
        both_up = left_up and right_up
        both_down = not left_up and not right_up
        one_up = left_up != right_up

        events = []
        events += self._update_shot_and_fake(both_up, both_down, now)
        events += self._update_layup(one_up, both_down, left_up, now)
        events += self._update_dribble(joints, shoulder_level, dt, now)
        events += self._update_stepback(joints, now)

        # ---- UI snapshot ----------------------------------------------
        if both_up:
            posture = "BOTH HANDS UP"
            progress = min(1.0, (now - self._both_up_since) / config.SHOT_HOLD_TIME)
        elif one_up:
            posture = "ONE HAND UP"
            progress = 0.0
        else:
            posture = "HANDS DOWN"
            progress = 0.0
        if self._shot_fired:
            posture = "SHOT RELEASED"
        self._status = {"posture": posture, "shot_progress": progress}

        return events

    # ------------------------------------------------------------------
    # SHOT and SHOT FAKE share the "raise episode" bookkeeping
    # ------------------------------------------------------------------
    def _update_shot_and_fake(self, both_up, both_down, now):
        events = []

        if both_up:
            if self._episode_start is None:
                # Both hands just went up: a new raise episode begins.
                self._episode_start = now
                self._shot_fired = False
            if self._both_up_since is None:
                self._both_up_since = now

            # SHOT: both hands held up continuously for the full hold.
            held = now - self._both_up_since
            if not self._shot_fired and held >= config.SHOT_HOLD_TIME:
                events.append({"type": SHOT})
                self._shot_fired = True
        else:
            # The continuous hold is broken the moment either hand drops.
            self._both_up_since = None

            if both_down and self._episode_start is not None:
                # SHOT FAKE: the episode ended below the shoulders before
                # a shot could fire and within the fake window.
                quick = (now - self._episode_start) < config.FAKE_MAX_TIME
                if quick and not self._shot_fired:
                    events.append({"type": SHOT_FAKE})
                # Episode over either way; ready for the next raise.
                self._episode_start = None
                self._shot_fired = False

        return events

    # ------------------------------------------------------------------
    def _update_layup(self, one_up, both_down, left_up, now):
        events = []

        # No layup during a raise episode: dropping one hand out of a
        # two-hand raise is part of a shot/fake, not a layup.
        if one_up and self._episode_start is None:
            if self._one_up_since is None:
                self._one_up_since = now
            # The short confirmation filters out the instant where the
            # second hand is still rising toward a two-hand shot pose.
            confirmed = now - self._one_up_since >= config.LAYUP_CONFIRM_TIME
            if confirmed and not self._layup_fired:
                events.append({"type": LAYUP, "hand": "left" if left_up else "right"})
                self._layup_fired = True
        else:
            self._one_up_since = None
            if both_down:
                # The hand came back down: a new layup may start.
                self._layup_fired = False

        return events

    # ------------------------------------------------------------------
    def _update_dribble(self, joints, shoulder_level, dt, now):
        """
        A dribble "bounce" is a below-shoulder hand reversing its
        vertical direction after meaningful travel - i.e. pushing the
        ball down and riding it back up. Each reversal = one event.
        """
        events = []

        for side in ("left", "right"):
            hand = self._dribble[side]
            wrist_y = joints[f"{side}_wrist"][1]
            below_shoulder = wrist_y > shoulder_level

            if not below_shoulder:
                # Hand is up doing something else; restart its tracking.
                hand["last_y"] = None
                hand["dir"] = 0
                continue

            if hand["last_y"] is not None and dt > 0:
                speed = (wrist_y - hand["last_y"]) / dt  # + = moving down
                if speed > config.DRIBBLE_MIN_SPEED:
                    new_dir = 1
                elif speed < -config.DRIBBLE_MIN_SPEED:
                    new_dir = -1
                else:
                    new_dir = 0   # too slow to call a direction

                if new_dir != 0:
                    if hand["dir"] == 0:
                        hand["flip_y"] = wrist_y
                    elif new_dir != hand["dir"]:
                        # Direction reversed: did the hand travel enough
                        # since the LAST reversal to be a real bounce?
                        amplitude = abs(wrist_y - (hand["flip_y"] or wrist_y))
                        spaced = now - hand["last_bounce"] >= config.DRIBBLE_MIN_INTERVAL
                        if amplitude >= config.DRIBBLE_MIN_AMPLITUDE and spaced:
                            events.append({"type": DRIBBLE, "hand": side})
                            hand["last_bounce"] = now
                        hand["flip_y"] = wrist_y
                    hand["dir"] = new_dir

            hand["last_y"] = wrist_y

        return events

    # ------------------------------------------------------------------
    def _update_stepback(self, joints, now):
        """
        Moving away from the camera makes the whole body smaller on
        screen. Shoulder width is a stable size proxy, so a quick
        shrink of the shoulder line = the player stepped back.
        """
        events = []

        width = abs(joints["right_shoulder"][0] - joints["left_shoulder"][0])
        self._width_history.append((now, width))
        # Keep only the last second of samples.
        while self._width_history and now - self._width_history[0][0] > 1.0:
            self._width_history.popleft()

        if now >= self._stepback_ready_at:
            # Compare against the oldest sample inside the window.
            for t, old_width in self._width_history:
                if now - t >= config.STEPBACK_WINDOW:
                    if old_width > 0 and width < old_width * (1.0 - config.STEPBACK_SHRINK):
                        events.append({"type": STEPBACK})
                        self._stepback_ready_at = now + config.STEPBACK_COOLDOWN
                        self._width_history.clear()
                    break

        return events
