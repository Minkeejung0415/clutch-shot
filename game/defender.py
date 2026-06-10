"""
The live defender.

One animated defender stands between the player and the rim and reacts
to every move the classifier detects:

  - DRIBBLE   he shuffles laterally to stay in front of the ball; a
              dribble thrown at max deception can cross him over
  - SHOT FAKE he may leave his feet (bite) - while airborne and while
              recovering from the landing he cannot defend anything
  - STEPBACK  the player buys separation; the defender closes it back
              down over time at his profile's closing speed
  - SHOT /    if he is on his feet and close enough he leaps to
    LAYUP     contest: either he BLOCKS it outright (one dice roll) or
              the attempt is merely CONTESTED (probability penalty)

Whether he falls for anything is driven by exactly two inputs, as the
design demands: the difficulty profile (config.DIFFICULTY_PROFILES) and
the player's deception level (how well they chained setup moves).

The class also exposes everything the UI needs to draw him: lateral
position, jump height, current state, and separation.
"""

import random

import config
from game.scoring import BLOCKED, CONTESTED, OPEN

# Defender states (also used by the UI to pick the pose to draw).
GUARD = "GUARD"          # on his feet, defending
IN_AIR = "IN_AIR"        # jumped at a fake - helpless until he lands
CONTEST = "CONTEST"      # leaping at a real shot/layup
RECOVER = "RECOVER"      # just landed, regaining balance
BEATEN = "BEATEN"        # crossed over / stumbling


class DefenderAI:
    """A single defender whose skill comes from a difficulty profile."""

    def __init__(self, difficulty=config.DEFAULT_DIFFICULTY):
        self.difficulty = difficulty
        self.profile = config.DIFFICULTY_PROFILES[difficulty]

        self.state = GUARD
        self._state_until = 0.0   # when the current timed state ends

        # Visual/positional state the UI reads every frame.
        self.x = 0.0              # lateral position, -1 (left) .. +1 (right)
        self._x_target = 0.0      # where he's shuffling toward
        self.jump = 0.0           # 0 grounded .. 1 top of his jump
        self.separation = 0.0     # space the player has, in "steps"

    # ------------------------------------------------------------------
    def update(self, dt, now):
        """Advance timers, jump animation, shuffling, and closeouts."""
        # Timed states expire into the next logical state.
        if self.state in (IN_AIR, CONTEST) and now >= self._state_until:
            # He landed: briefly off-balance before guarding again.
            self.state = RECOVER
            self._state_until = now + self.profile["recover_time"]
        elif self.state in (RECOVER, BEATEN) and now >= self._state_until:
            self.state = GUARD

        # Jump height eases toward 1 in the air, back to 0 on the ground.
        target_jump = 1.0 if self.state in (IN_AIR, CONTEST) else 0.0
        self.jump += (target_jump - self.jump) * min(1.0, 12.0 * dt)

        # Lateral shuffle toward wherever the ball pulled him.
        max_step = self.profile["shuffle_speed"] * dt
        delta = self._x_target - self.x
        self.x += max(-max_step, min(max_step, delta))

        # A defender on his feet works to erase the player's separation.
        if self.state == GUARD:
            self.separation = max(
                0.0, self.separation - self.profile["closing_speed"] * dt
            )

    # ------------------------------------------------------------------
    # Reactions to the player's setup moves
    # ------------------------------------------------------------------
    def on_dribble(self, hand, deception, now):
        """
        Follow the ball side to side. A dribble thrown while the player
        is at full deception can shake him completely (a crossover).

        Returns True if the defender stumbled.
        """
        # Mirror view: the player's right-hand dribble pulls the
        # defender toward the screen's right side.
        self._x_target = 0.6 if hand == "right" else -0.6

        if self.state == GUARD and deception >= 3:
            if random.random() < self.profile["stumble_chance"]:
                self.state = BEATEN
                self._state_until = now + config.DEFENDER_BEATEN_TIME
                return True
        return False

    def on_fake(self, deception, now):
        """
        The player pump-faked. A defender already in the air, recovering
        or beaten can't bite again. Bite chance rises with deception.

        Returns True if he bit (left his feet).
        """
        if self.state != GUARD:
            return False
        chance = (
            self.profile["bite_base"]
            + deception * self.profile["bite_deception_bonus"]
        )
        if random.random() < chance:
            self.state = IN_AIR
            self._state_until = now + config.DEFENDER_AIR_TIME
            return True
        return False

    def on_stepback(self, deception, now):
        """
        The player stepped back: instant separation. At high deception
        the sudden move can also make the defender stumble.

        Returns True if he stumbled.
        """
        self.separation = min(
            config.MAX_SEPARATION, self.separation + config.STEPBACK_SEPARATION
        )
        if self.state == GUARD and deception >= 2:
            if random.random() < self.profile["stumble_chance"]:
                self.state = BEATEN
                self._state_until = now + config.DEFENDER_BEATEN_TIME
                return True
        return False

    # ------------------------------------------------------------------
    # Challenging a real attempt
    # ------------------------------------------------------------------
    def challenge(self, kind, deception, now):
        """
        The player released a shot or went up for a layup. Decide how
        the defense affects it.

        Returns one of scoring.OPEN / CONTESTED / BLOCKED:
          OPEN      he physically can't contest (airborne from a fake,
                    recovering, beaten, or - for jump shots - left too
                    far behind by stepbacks)
          BLOCKED   he contested AND won his block dice roll
          CONTESTED he got a hand up but didn't get the ball
        """
        if self.state != GUARD:
            return OPEN
        if kind == "shot" and self.separation >= config.OPEN_SEPARATION:
            return OPEN

        # He leaps to contest (visual: the UI sees CONTEST and animates).
        self.state = CONTEST
        self._state_until = now + config.DEFENDER_CONTEST_TIME

        base = self.profile["block_layup"] if kind == "layup" else self.profile["block_shot"]
        block_chance = (
            base
            - self.separation * config.BLOCK_SEPARATION_PENALTY
            - deception * config.BLOCK_DECEPTION_PENALTY
        )
        if random.random() < max(0.0, block_chance):
            return BLOCKED
        return CONTESTED
