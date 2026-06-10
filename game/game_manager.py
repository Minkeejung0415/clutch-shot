"""
GameManager: the rulebook of CLUTCH SHOT.

Owns everything about one 60-second game: the clock, score, statistics,
the defender on the court, the fatigue meter, and the resolution of
every shot and fake. It consumes events from the MotionDetector and
produces state for the UI to draw - it never touches the camera or
Pygame itself, so it can be tested headlessly.

Game flow:
    START  --SPACE-->  PLAYING  --timer hits 0-->  GAME_OVER  --R--> START
"""

import random
import time

import config
from game.defender import DefenderManager
from game.scoring import (
    FatigueSystem,
    compute_form_score,
    form_label,
    points_for_made_shot,
    shot_probability,
)

# Game phases.
STATE_START = "START"
STATE_PLAYING = "PLAYING"
STATE_GAME_OVER = "GAME_OVER"


class GameManager:
    """Holds and advances all game state for one session."""

    def __init__(self):
        self.state = STATE_START
        self.reset()

    # ------------------------------------------------------------------
    def reset(self):
        """Fresh game state (called on construction and on restart)."""
        self.time_remaining = float(config.GAME_DURATION)
        self.score = 0
        self.attempts = 0
        self.makes = 0
        self.form_scores = []          # every attempt's form score
        self.fatigue = FatigueSystem()
        self.defenders = DefenderManager()

        # "Last shot" panel data for the dashboard.
        self.last_form_score = None
        self.last_probability = None
        self.last_result = None        # "MADE" / "MISSED" / None

        # Action messages: list of (text, expires_at_timestamp).
        self.messages = []

    def start(self):
        """Begin a new game from the start or end screen."""
        self.reset()
        self.state = STATE_PLAYING

    # ------------------------------------------------------------------
    # Stats helpers the UI reads
    # ------------------------------------------------------------------
    @property
    def shooting_pct(self):
        """Field-goal percentage, 0-100."""
        if self.attempts == 0:
            return 0.0
        return 100.0 * self.makes / self.attempts

    @property
    def average_form(self):
        if not self.form_scores:
            return 0.0
        return sum(self.form_scores) / len(self.form_scores)

    @property
    def best_form(self):
        return max(self.form_scores) if self.form_scores else 0.0

    def active_messages(self):
        """Messages that haven't expired yet, newest first."""
        now = time.time()
        return [text for text, expires in reversed(self.messages) if expires > now]

    def _say(self, text):
        """Queue an action message for the dashboard."""
        self.messages.append((text, time.time() + config.MESSAGE_DURATION))
        # Keep the list from growing forever during a long session.
        if len(self.messages) > 20:
            self.messages = self.messages[-20:]

    # ------------------------------------------------------------------
    # Per-frame update
    # ------------------------------------------------------------------
    def update(self, dt):
        """Advance the clock, fatigue recovery, and defender behavior."""
        if self.state != STATE_PLAYING:
            return

        self.time_remaining -= dt
        self.fatigue.update(dt)

        # Defenders rotate / change stance / announce the boss.
        for message in self.defenders.update(dt, self.time_remaining):
            self._say(message)

        if self.time_remaining <= 0:
            self.time_remaining = 0.0
            self.state = STATE_GAME_OVER

    # ------------------------------------------------------------------
    # Motion events from the detector
    # ------------------------------------------------------------------
    def handle_motion_event(self, event):
        """Route a MotionDetector event to the right resolver."""
        if self.state != STATE_PLAYING or event is None:
            return
        if event["type"] == "shot":
            self._resolve_shot(event["metrics"])
        elif event["type"] == "fake":
            self._resolve_fake()

    def _resolve_fake(self):
        """The player pump-faked: see if the defender leaves their feet."""
        if self.defenders.on_fake():
            self._say("DEFENDER BIT ON THE FAKE!")
        else:
            self._say(f"{self.defenders.defender.display_name} stays down...")

    def _resolve_shot(self, metrics):
        """
        Score one detected shot, start to finish:

        1. form score from the raw motion measurements
        2. effective pressure (forced OPEN if the defender bit a fake)
        3. final probability = base + form + pressure - fatigue + fake
        4. ONE random roll decides make or miss
        5. points + bonuses on a make, fatigue on every attempt
        """
        form = compute_form_score(metrics)

        # The fake window is spent by this shot whether it goes in or not.
        pressure = self.defenders.pressure_for_shot()
        fake_active = self.defenders.consume_fake_window()

        probability = shot_probability(form, pressure, self.fatigue.value, fake_active)
        made = random.random() < probability

        # Book-keeping shared by makes and misses.
        self.attempts += 1
        self.form_scores.append(form)
        self.fatigue.add_shot()
        self.last_form_score = form
        self.last_probability = probability

        if form >= config.FORM_EXCELLENT_THRESHOLD:
            self._say("GREEN RELEASE!")

        if made:
            self.makes += 1
            points, bonuses = points_for_made_shot(pressure, fake_active, form)
            self.score += points
            self.last_result = "MADE"
            if bonuses:
                self._say(f"SHOT MADE! +{points} ({', '.join(bonuses)})")
            else:
                self._say(f"SHOT MADE! +{points}")
        else:
            self.last_result = "MISSED"
            self._say("MISSED!")

        # Console log mirrors the dashboard - handy for debugging.
        print(
            f"[SHOT] form={form:5.1f} ({form_label(form)})  "
            f"pressure={pressure:<13}  prob={probability:.2f}  "
            f"fatigue={self.fatigue.value:5.1f}  -> {self.last_result}"
        )
