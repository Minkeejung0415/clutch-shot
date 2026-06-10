"""
Virtual defender system.

No machine learning here - each defender is a personality made of two
probabilities (defined in config.DEFENDER_PROFILES):

  - pressure_weights: how often it plays OPEN / LIGHT_CONTEST /
    HEAVY_CONTEST when it re-decides its stance
  - fake_bite_chance: how easily it jumps on a shot fake

The DefenderManager rotates regular defenders during the game and sends
in the BOSS_DEFENDER for the final stretch.
"""

import random

import config

# The three pressure stances, ordered from easiest to hardest to shoot over.
PRESSURE_LEVELS = ("OPEN", "LIGHT_CONTEST", "HEAVY_CONTEST")

# Regular rotation - the boss is excluded and enters on a timer instead.
ROTATION_TYPES = ("LAZY_DEFENDER", "AGGRESSIVE_GUARD", "DISCIPLINED_DEFENDER")


class Defender:
    """One defender with a fixed personality from config."""

    def __init__(self, type_name):
        self.type_name = type_name
        profile = config.DEFENDER_PROFILES[type_name]
        self.display_name = profile["display_name"]
        self._pressure_weights = profile["pressure_weights"]
        self._fake_bite_chance = profile["fake_bite_chance"]

    def roll_pressure(self):
        """Pick a pressure stance using this defender's weights."""
        levels = list(self._pressure_weights.keys())
        weights = list(self._pressure_weights.values())
        return random.choices(levels, weights=weights, k=1)[0]

    def bites_on_fake(self):
        """Dice roll: does this defender jump on the player's pump fake?"""
        return random.random() < self._fake_bite_chance

    @property
    def is_boss(self):
        return self.type_name == "BOSS_DEFENDER"


class DefenderManager:
    """
    Owns the defender currently on the court.

    Responsibilities:
    - rotate a new random regular defender every
      DEFENDER_ROTATION_INTERVAL seconds
    - re-roll the current defender's pressure stance every
      PRESSURE_REROLL_INTERVAL seconds
    - bring in the BOSS_DEFENDER when time_remaining drops below
      BOSS_ENTER_TIME_REMAINING (the boss then stays until the buzzer)
    - track the "defender bit on a fake" window, during which the next
      shot is treated as wide OPEN
    """

    def __init__(self):
        self.defender = Defender(random.choice(ROTATION_TYPES))
        self.pressure = self.defender.roll_pressure()
        self._rotation_timer = 0.0
        self._reroll_timer = 0.0
        self._boss_announced = False

        # > 0 means a defender recently bit on a fake; counts down in
        # update(). While positive, the next shot is OPEN + fake bonus.
        self.fake_window = 0.0

    # ------------------------------------------------------------------
    def update(self, dt, time_remaining):
        """
        Advance defender behavior by one frame.

        Returns a list of action-message strings for the UI (possibly
        empty), e.g. ["BOSS DEFENDER ENTERS!"].
        """
        messages = []
        self.fake_window = max(0.0, self.fake_window - dt)

        # Boss entrance overrides normal rotation for the endgame.
        if (
            not self._boss_announced
            and time_remaining <= config.BOSS_ENTER_TIME_REMAINING
        ):
            self.defender = Defender("BOSS_DEFENDER")
            self.pressure = self.defender.roll_pressure()
            self._boss_announced = True
            self._rotation_timer = 0.0
            self._reroll_timer = 0.0
            messages.append("BOSS DEFENDER ENTERS!")
            return messages

        # Regular defenders sub in and out on a timer (boss never leaves).
        if not self.defender.is_boss:
            self._rotation_timer += dt
            if self._rotation_timer >= config.DEFENDER_ROTATION_INTERVAL:
                self._rotation_timer = 0.0
                # Pick a different defender than the current one so the
                # rotation is always visible to the player.
                choices = [t for t in ROTATION_TYPES if t != self.defender.type_name]
                self.defender = Defender(random.choice(choices))
                messages.extend(self._set_pressure(self.defender.roll_pressure()))
                return messages

        # The defender periodically re-decides how tight to play.
        self._reroll_timer += dt
        if self._reroll_timer >= config.PRESSURE_REROLL_INTERVAL:
            self._reroll_timer = 0.0
            messages.extend(self._set_pressure(self.defender.roll_pressure()))

        return messages

    def _set_pressure(self, new_pressure):
        """Update the stance; announce it only when it actually changes."""
        messages = []
        if new_pressure != self.pressure:
            if new_pressure == "HEAVY_CONTEST":
                messages.append("HEAVY CONTEST!")
            elif new_pressure == "OPEN":
                messages.append("OPEN LOOK!")
        self.pressure = new_pressure
        return messages

    # ------------------------------------------------------------------
    def on_fake(self):
        """
        The player threw a pump fake. Roll whether the defender bites.

        Returns True if the defender bit (the fake window opens and the
        next shot inside it is treated as OPEN with a probability bonus).
        """
        if self.defender.bites_on_fake():
            self.fake_window = config.FAKE_FOLLOWUP_WINDOW
            return True
        return False

    def pressure_for_shot(self):
        """
        The stance that applies to a shot taken RIGHT NOW.

        Inside the fake window the defender is in the air / out of
        position, so the shot is wide open regardless of normal stance.
        """
        if self.fake_window > 0:
            return "OPEN"
        return self.pressure

    def consume_fake_window(self):
        """
        Spend the fake bonus on this shot (so one bite = one boosted
        shot). Returns True if a fake bonus was active.
        """
        if self.fake_window > 0:
            self.fake_window = 0.0
            return True
        return False
