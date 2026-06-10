"""
GameManager: the rulebook of CLUTCH SHOT.

Owns one 60-second game: the clock, score, statistics, the defender,
the fatigue meter, the player's deception level, and the resolution of
every move the classifier reports:

    dribble   -> defender shuffles (and can get crossed at max deception)
    shot_fake -> defender may bite and leave his feet
    stepback  -> instant separation; a shot inside 2 s is worth 3
    shot      -> challenged by the defender, then one probability roll
    layup     -> same, but the defender protects the rim harder

"Deception" is how many DIFFERENT setup moves (dribble / fake /
stepback) the player chained in the last few seconds (0-3). It feeds
every defender reaction, so fooling him is genuinely about the
player's ability, not just dice.

This module never touches the camera or Pygame, so it runs headless in
tests. Game flow:

    START --SPACE--> PLAYING --clock hits 0--> GAME_OVER --R--> START
"""

import random
import time

import config
from game.defender import DefenderAI
from game.scoring import (
    BLOCKED,
    OPEN,
    FatigueSystem,
    attempt_probability,
    points_for,
)

# Game phases.
STATE_START = "START"
STATE_PLAYING = "PLAYING"
STATE_GAME_OVER = "GAME_OVER"

# Move names (mirror vision/motion_detector.py event types).
MOVES = ("dribble", "layup", "shot", "shot_fake", "stepback")


class GameManager:
    """Holds and advances all game state for one session."""

    def __init__(self, difficulty=config.DEFAULT_DIFFICULTY):
        self.difficulty = difficulty
        self.state = STATE_START
        self.reset()

    # ------------------------------------------------------------------
    def reset(self):
        """Fresh game state (keeps the chosen difficulty)."""
        self.time_remaining = float(config.GAME_DURATION)
        self.score = 0
        self.attempts = 0       # shots + layups
        self.makes = 0
        self.blocks_against = 0
        self.move_counts = {move: 0 for move in MOVES}

        self.fatigue = FatigueSystem()
        self.defender = DefenderAI(self.difficulty)

        # Recent setup moves for the deception level: (move type, time).
        self._recent_moves = []
        self._last_stepback = -999.0

        # "Last attempt" panel data for the HUD.
        self.last_probability = None
        self.last_result = None     # "MADE" / "MISSED" / "BLOCKED" / None

        # Ball-flight animation info for the UI: set on every attempt.
        # {"start": t, "kind": ..., "result": ..., "three": bool}
        self.ball_flight = None

        # Action messages: list of (text, expires_at_timestamp).
        self.messages = []

    def set_difficulty(self, difficulty):
        """Pick a difficulty (start screen). Swaps in a new defender."""
        self.difficulty = difficulty
        self.defender = DefenderAI(difficulty)

    def start(self):
        """Begin a new game from the start or end screen."""
        self.reset()
        self.state = STATE_PLAYING

    # ------------------------------------------------------------------
    # Stats / HUD helpers
    # ------------------------------------------------------------------
    @property
    def shooting_pct(self):
        """Field-goal percentage over shots + layups, 0-100."""
        if self.attempts == 0:
            return 0.0
        return 100.0 * self.makes / self.attempts

    def deception_level(self):
        """
        0-3: how many DIFFERENT setup moves (dribble, fake, stepback)
        the player used within the deception window. Chaining variety
        is what makes the defender guessable - this is the "player
        ability" input to every defender reaction.
        """
        cutoff = time.time() - config.DECEPTION_WINDOW
        kinds = {move for move, t in self._recent_moves if t >= cutoff}
        return len(kinds)

    def active_messages(self):
        """Messages that haven't expired yet, newest first."""
        now = time.time()
        return [text for text, expires in reversed(self.messages) if expires > now]

    def _say(self, text):
        """Queue an action message for the HUD."""
        self.messages.append((text, time.time() + config.MESSAGE_DURATION))
        if len(self.messages) > 20:
            self.messages = self.messages[-20:]

    def _remember_move(self, move, now):
        """Track a setup move for the deception level."""
        self._recent_moves.append((move, now))
        cutoff = now - config.DECEPTION_WINDOW
        self._recent_moves = [(m, t) for m, t in self._recent_moves if t >= cutoff]

    # ------------------------------------------------------------------
    # Per-frame update
    # ------------------------------------------------------------------
    def update(self, dt):
        """Advance the clock, fatigue recovery, and the defender."""
        now = time.time()
        # The defender keeps moving on every screen so the start screen
        # already shows him pacing in front of the rim.
        self.defender.update(dt, now)

        if self.state != STATE_PLAYING:
            return

        self.time_remaining -= dt
        self.fatigue.update(dt)

        if self.time_remaining <= 0:
            self.time_remaining = 0.0
            self.state = STATE_GAME_OVER

    # ------------------------------------------------------------------
    # Move events from the classifier
    # ------------------------------------------------------------------
    def handle_motion_event(self, event):
        """Route one classifier event to the right resolver."""
        if self.state != STATE_PLAYING or event is None:
            return
        now = time.time()
        kind = event["type"]
        self.move_counts[kind] += 1

        if kind == "dribble":
            self._remember_move("dribble", now)
            crossed = self.defender.on_dribble(
                event.get("hand", "right"), self.deception_level(), now
            )
            if crossed:
                self._say("CROSSED HIM OVER!")

        elif kind == "shot_fake":
            self._remember_move("shot_fake", now)
            if self.defender.on_fake(self.deception_level(), now):
                self._say("DEFENDER BIT ON THE FAKE!")
            else:
                self._say("He stays down...")

        elif kind == "stepback":
            self._remember_move("stepback", now)
            stumbled = self.defender.on_stepback(self.deception_level(), now)
            self._last_stepback = now
            self._say("STEPBACK - SPACE CREATED!")
            if stumbled:
                self._say("DEFENDER STUMBLES!")

        elif kind in ("shot", "layup"):
            self._resolve_attempt(kind, now)

    # ------------------------------------------------------------------
    def _resolve_attempt(self, kind, now):
        """
        Resolve a shot or layup, start to finish:

        1. is it a stepback three? (shot within the window of a stepback)
        2. the defender challenges: OPEN / CONTESTED / BLOCKED
        3. BLOCKED ends it right there - no probability roll
        4. otherwise ONE dice roll against attempt_probability()
        """
        deception = self.deception_level()
        separation = self.defender.separation
        is_three = kind == "shot" and (now - self._last_stepback) <= config.STEPBACK_SHOT_WINDOW

        contest = self.defender.challenge(kind, deception, now)

        self.attempts += 1
        # Probability uses the fatigue you shot WITH; the attempt's own
        # fatigue cost lands afterwards.
        fatigue_before = self.fatigue.value
        self.fatigue.add_shot()

        if contest == BLOCKED:
            self.blocks_against += 1
            self.last_result = "BLOCKED"
            self.last_probability = 0.0
            self._say("REJECTED AT THE RIM!" if kind == "layup" else "BLOCKED!")
        else:
            probability = attempt_probability(
                kind, contest, self.defender.profile["contest_penalty"],
                separation, fatigue_before, is_three,
            )
            made = random.random() < probability
            self.last_probability = probability

            if made:
                points = points_for(kind, is_three)
                self.score += points
                self.makes += 1
                self.last_result = "MADE"
                if kind == "layup":
                    self._say(f"LAYUP GOOD! +{points}")
                elif is_three:
                    self._say(f"STEPBACK THREE! +{points}")
                elif contest == OPEN:
                    self._say(f"WIDE OPEN - SHOT MADE! +{points}")
                else:
                    self._say(f"SHOT MADE! +{points}")
            else:
                self.last_result = "MISSED"
                self._say("LAYUP MISSED!" if kind == "layup" else "MISSED!")

        # Ball-flight animation cue for the UI.
        self.ball_flight = {
            "start": now,
            "kind": kind,
            "result": self.last_result,
            "three": is_three,
        }

        # Console log mirrors the HUD - handy for debugging.
        print(
            f"[{kind.upper():5}] contest={contest:<9} "
            f"prob={self.last_probability:.2f} sep={separation:.1f} "
            f"deception={deception} -> {self.last_result}"
        )
