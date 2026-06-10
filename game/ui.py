"""
Pygame user interface for CLUTCH SHOT.

Layout (config.WINDOW_WIDTH x WINDOW_HEIGHT, default 1280x720):

    +------------------------------+------------------------------+
    |  CLUTCH SHOT        (title)  |   COURT: hoop + DEFENDER     |
    |                              |   (he shuffles, jumps,       |
    |   webcam view with skeleton  |    bites fakes, blocks)      |
    |                              |   action messages            |
    |  posture + shot charge bar   |   defender state             |
    +------------------------------+------------------------------+
    |  TIME | SCORE | FG | last attempt | deception | fatigue     |
    +-------------------------------------------------------------+

Everything is drawn with plain Pygame shapes - no image assets - in a
dark court theme with basketball-orange accents (colors in config.py).

The UI is read-only: it draws whatever GameManager, DefenderAI and the
MotionClassifier report, and never changes game state.
"""

import math
import time

import pygame

import config
from game.defender import BEATEN, CONTEST, GUARD, IN_AIR, RECOVER
from game.game_manager import STATE_GAME_OVER, STATE_START

# Webcam panel.
CAM_X, CAM_Y = 20, 90
CAM_W, CAM_H = 620, 460

# Court panel (the defender's side).
COURT_X = CAM_X + CAM_W + 20
COURT_W = config.WINDOW_WIDTH - COURT_X - 20
COURT_Y, COURT_H = CAM_Y, CAM_H

# Bottom HUD bar.
HUD_Y = COURT_Y + COURT_H + 46
HUD_H = config.WINDOW_HEIGHT - HUD_Y - 14

BALL_FLIGHT_TIME = 0.55   # seconds for the ball to fly to the rim
RESULT_FLASH_TIME = 0.6   # how long the result text flashes at the rim


class GameUI:
    """Draws every screen of the game onto a Pygame surface."""

    def __init__(self, screen):
        self.screen = screen
        self.font_huge = pygame.font.Font(None, 84)
        self.font_big = pygame.font.Font(None, 54)
        self.font_med = pygame.font.Font(None, 34)
        self.font_small = pygame.font.Font(None, 25)

    # ------------------------------------------------------------------
    # Small drawing helpers
    # ------------------------------------------------------------------
    def _text(self, text, font, color, x, y, center=False):
        surface = font.render(text, True, color)
        rect = surface.get_rect()
        if center:
            rect.center = (x, y)
        else:
            rect.topleft = (x, y)
        self.screen.blit(surface, rect)
        return rect

    def _panel(self, rect, border_color=None):
        pygame.draw.rect(self.screen, (30, 30, 40), rect, border_radius=10)
        if border_color:
            pygame.draw.rect(self.screen, border_color, rect, 2, border_radius=10)

    # ------------------------------------------------------------------
    # Frame entry point
    # ------------------------------------------------------------------
    def render(self, frame_rgb, manager, motion_status, body_visibility):
        """
        Draw one full frame.

        Args:
            frame_rgb: mirrored webcam image with skeleton, as an RGB
                numpy array, or None if the camera gave no frame.
            manager: the GameManager (read-only).
            motion_status: MotionClassifier.status() dict with "posture"
                and "shot_progress" (drives the charge bar).
            body_visibility: 0.0-1.0 from PoseTracker.
        """
        self.screen.fill(config.COLOR_BACKGROUND)

        self._draw_header(manager)
        self._draw_webcam(frame_rgb, motion_status, body_visibility)
        self._draw_court(manager)
        self._draw_hud(manager)

        if manager.state == STATE_START:
            self._draw_start_overlay(manager)
        elif manager.state == STATE_GAME_OVER:
            self._draw_end_overlay(manager)

        pygame.display.flip()

    # ------------------------------------------------------------------
    def _draw_header(self, manager):
        self._text("CLUTCH SHOT", self.font_big, config.COLOR_ACCENT, CAM_X, 22)
        self._text("BEAT THE DEFENDER", self.font_small,
                   config.COLOR_TEXT_DIM, CAM_X + 330, 40)
        self._text(f"DIFFICULTY: {manager.difficulty}", self.font_med,
                   config.COLOR_WARNING, COURT_X, 32)

        # Basketball icon.
        cx, cy, r = config.WINDOW_WIDTH - 50, 45, 22
        pygame.draw.circle(self.screen, config.COLOR_ACCENT, (cx, cy), r)
        pygame.draw.line(self.screen, config.COLOR_BACKGROUND, (cx - r, cy), (cx + r, cy), 2)
        pygame.draw.line(self.screen, config.COLOR_BACKGROUND, (cx, cy - r), (cx, cy + r), 2)

    # ------------------------------------------------------------------
    def _draw_webcam(self, frame_rgb, motion_status, body_visibility):
        """Live camera view plus the posture line and shot charge bar."""
        cam_rect = pygame.Rect(CAM_X, CAM_Y, CAM_W, CAM_H)
        pygame.draw.rect(self.screen, (0, 0, 0), cam_rect)

        if frame_rgb is not None:
            h, w = frame_rgb.shape[:2]
            surface = pygame.image.frombuffer(frame_rgb.tobytes(), (w, h), "RGB")
            surface = pygame.transform.smoothscale(surface, (CAM_W, CAM_H))
            self.screen.blit(surface, cam_rect)
        else:
            self._text("NO CAMERA SIGNAL", self.font_med, config.COLOR_FAIL,
                       cam_rect.centerx, cam_rect.centery, center=True)

        pygame.draw.rect(self.screen, config.COLOR_ACCENT, cam_rect, 3, border_radius=4)

        # Status strip: detected posture + tracking warning.
        strip_y = CAM_Y + CAM_H + 10
        self._text(motion_status["posture"], self.font_small,
                   config.COLOR_ACCENT, CAM_X, strip_y)
        if body_visibility < config.MIN_LANDMARK_VISIBILITY:
            self._text("STEP BACK - BODY NOT FULLY VISIBLE", self.font_small,
                       config.COLOR_FAIL, CAM_X + 230, strip_y)

        # Shot charge bar: fills while both hands are held up; the shot
        # releases automatically when it's full (1 second).
        bar = pygame.Rect(CAM_X + 380, strip_y + 2, CAM_W - 380, 14)
        pygame.draw.rect(self.screen, (60, 60, 70), bar, border_radius=7)
        progress = motion_status["shot_progress"]
        if progress > 0:
            fill = pygame.Rect(bar.x, bar.y, max(6, int(bar.width * progress)), bar.height)
            color = config.COLOR_SUCCESS if progress >= 1.0 else config.COLOR_ACCENT
            pygame.draw.rect(self.screen, color, fill, border_radius=7)

    # ------------------------------------------------------------------
    # The court scene
    # ------------------------------------------------------------------
    def _draw_court(self, manager):
        """Hoop at the top, YOU at the bottom, the defender in between."""
        court = pygame.Rect(COURT_X, COURT_Y, COURT_W, COURT_H)
        pygame.draw.rect(self.screen, config.COLOR_COURT, court, border_radius=6)

        cx = court.centerx

        # Court markings: the key and a free-throw arc.
        key = pygame.Rect(0, 0, 200, 190)
        key.midtop = (cx, court.y + 20)
        pygame.draw.rect(self.screen, config.COLOR_COURT_LINES, key, 2)
        pygame.draw.arc(self.screen, config.COLOR_COURT_LINES,
                        (cx - 100, key.bottom - 50, 200, 100), math.pi, 2 * math.pi, 2)

        # Backboard, rim and net.
        board = pygame.Rect(0, 0, 130, 12)
        board.midtop = (cx, court.y + 26)
        pygame.draw.rect(self.screen, (220, 220, 220), board, border_radius=3)
        rim_center = (cx, board.bottom + 14)
        rim_rect = pygame.Rect(0, 0, 56, 18)
        rim_rect.center = rim_center
        pygame.draw.ellipse(self.screen, config.COLOR_ACCENT, rim_rect, 4)
        for dx in (-22, -11, 0, 11, 22):   # net strands
            pygame.draw.line(self.screen, (200, 200, 200),
                             (cx + dx, rim_center[1] + 6),
                             (cx + dx * 0.45, rim_center[1] + 38), 1)

        # YOU: marker at the bottom of the court (the webcam player).
        you = (cx, court.bottom - 36)
        pygame.draw.circle(self.screen, config.COLOR_ACCENT, you, 14)
        self._text("YOU", self.font_small, config.COLOR_TEXT, you[0], court.bottom - 16,
                   center=True)

        self._draw_defender(manager.defender, you, rim_center)
        self._draw_ball_flight(manager, you, rim_center)

        # Action messages stacked at the top-left of the court.
        msg_y = court.y + 12
        for message in manager.active_messages()[:3]:
            self._text(message, self.font_med, config.COLOR_ACCENT,
                       court.x + 14, msg_y)
            msg_y += 32

        # Defender state line under the court.
        state_names = {
            GUARD: "guarding", IN_AIR: "IN THE AIR!", CONTEST: "contesting!",
            RECOVER: "recovering...", BEATEN: "off balance!",
        }
        defender = manager.defender
        label = (f"Defender: {state_names[defender.state]}   "
                 f"separation: {defender.separation:.1f}")
        self._text(label, self.font_small, config.COLOR_TEXT_DIM,
                   COURT_X, court.bottom + 10)

    # ------------------------------------------------------------------
    def _draw_defender(self, defender, you, rim_center):
        """
        A simple jointed figure between YOU and the rim.

        Separation pushes him farther from the player (he got left
        behind); his jump lifts the whole figure; his pose changes with
        his state (arms up in the air, slumped when beaten...).
        """
        # Position: starts right in front of YOU, drifts toward the rim
        # as separation grows, slides laterally as he follows dribbles.
        base_x = you[0] + defender.x * 110
        base_y = you[1] - 86 - defender.separation * 42
        base_y -= defender.jump * 46   # airborne lift

        beaten = defender.state == BEATEN
        lean = 18 if beaten else 0      # stumbling = whole body tilts

        color = config.COLOR_DEFENDER
        head = (int(base_x + lean), int(base_y - 52))
        hip = (int(base_x), int(base_y))
        shoulder = (int(base_x + lean * 0.7), int(base_y - 38))

        # Legs: spread while guarding, trailing in the air.
        if defender.jump > 0.3:
            legs = [(-10, 22), (12, 26)]
        else:
            legs = [(-14, 30), (14, 30)]
        for dx, dy in legs:
            pygame.draw.line(self.screen, color, hip, (hip[0] + dx, hip[1] + dy), 5)

        # Torso and head.
        pygame.draw.line(self.screen, color, hip, shoulder, 7)
        pygame.draw.circle(self.screen, color, head, 10)

        # Arms tell the story of his state.
        if defender.state in (IN_AIR, CONTEST):
            arms = [(-10, -34), (10, -34)]        # both straight up
        elif beaten:
            arms = [(-26, 14), (24, 18)]          # flailing low
        else:
            arms = [(-26, -2), (26, -2)]          # wide guard stance
        for dx, dy in arms:
            pygame.draw.line(self.screen, color, shoulder,
                             (shoulder[0] + dx, shoulder[1] + dy), 5)

    # ------------------------------------------------------------------
    def _draw_ball_flight(self, manager, you, rim_center):
        """Animate the ball from YOU to the rim after every attempt."""
        flight = manager.ball_flight
        if flight is None:
            return
        elapsed = time.time() - flight["start"]
        if elapsed > BALL_FLIGHT_TIME + RESULT_FLASH_TIME:
            return

        if flight["result"] == "BLOCKED":
            # The ball gets swatted: short hop up, then straight down.
            t = min(1.0, elapsed / BALL_FLIGHT_TIME)
            x = you[0] + (rim_center[0] - you[0]) * 0.25 * t
            y = you[1] - 90 * t * (1 - t) * 4 * 0.4 + 40 * t
            pygame.draw.circle(self.screen, config.COLOR_ACCENT, (int(x), int(y)), 8)
        elif elapsed <= BALL_FLIGHT_TIME:
            # Quadratic arc from the player's hands to the rim.
            t = elapsed / BALL_FLIGHT_TIME
            x = you[0] + (rim_center[0] - you[0]) * t
            straight_y = you[1] + (rim_center[1] - you[1]) * t
            y = straight_y - 110 * (4 * t * (1 - t))   # arc height
            pygame.draw.circle(self.screen, config.COLOR_ACCENT, (int(x), int(y)), 8)

        # Result flash at the rim once the ball arrives.
        if elapsed > BALL_FLIGHT_TIME:
            texts = {"MADE": ("SPLASH!", config.COLOR_SUCCESS),
                     "MISSED": ("RIM OUT", config.COLOR_FAIL),
                     "BLOCKED": ("BLOCKED", config.COLOR_FAIL)}
            text, color = texts[flight["result"]]
            self._text(text, self.font_med, color,
                       rim_center[0], rim_center[1] + 56, center=True)

    # ------------------------------------------------------------------
    # Bottom HUD bar
    # ------------------------------------------------------------------
    def _draw_hud(self, manager):
        bar = pygame.Rect(CAM_X, HUD_Y, config.WINDOW_WIDTH - 2 * CAM_X, HUD_H)
        self._panel(bar)
        y = HUD_Y + 8

        # Time and score, big.
        timer_color = config.COLOR_FAIL if manager.time_remaining <= 10 else config.COLOR_TEXT
        self._text("TIME", self.font_small, config.COLOR_TEXT_DIM, CAM_X + 16, y)
        self._text(f"{manager.time_remaining:04.1f}", self.font_huge, timer_color,
                   CAM_X + 16, y + 18)
        self._text("SCORE", self.font_small, config.COLOR_TEXT_DIM, CAM_X + 210, y)
        self._text(str(manager.score), self.font_huge, config.COLOR_ACCENT,
                   CAM_X + 210, y + 18)

        # Shooting stats.
        self._text(f"FG {manager.makes}/{manager.attempts} "
                   f"({manager.shooting_pct:.0f}%)", self.font_med,
                   config.COLOR_TEXT, CAM_X + 360, y + 6)
        if manager.last_probability is not None:
            result_color = (config.COLOR_SUCCESS if manager.last_result == "MADE"
                            else config.COLOR_FAIL)
            self._text(f"last: {manager.last_probability:.0%} {manager.last_result}",
                       self.font_med, result_color, CAM_X + 360, y + 42)

        # Deception pips: the live "how unpredictable are you" meter.
        self._text("DECEPTION", self.font_small, config.COLOR_TEXT_DIM, CAM_X + 640, y)
        level = manager.deception_level()
        for i in range(3):
            color = config.COLOR_WARNING if i < level else (60, 60, 70)
            pygame.draw.circle(self.screen, color, (CAM_X + 652 + i * 28, y + 38), 10)

        # Fatigue bar.
        self._text("FATIGUE", self.font_small, config.COLOR_TEXT_DIM, CAM_X + 800, y)
        fat_bg = pygame.Rect(CAM_X + 800, y + 30, 320, 16)
        pygame.draw.rect(self.screen, (60, 60, 70), fat_bg, border_radius=8)
        fraction = manager.fatigue.value / config.FATIGUE_MAX
        if fraction > 0:
            if fraction < 0.4:
                color = config.COLOR_SUCCESS
            elif fraction < 0.7:
                color = config.COLOR_WARNING
            else:
                color = config.COLOR_FAIL
            fill = pygame.Rect(fat_bg.x, fat_bg.y,
                               max(8, int(fat_bg.width * fraction)), fat_bg.height)
            pygame.draw.rect(self.screen, color, fill, border_radius=8)

    # ------------------------------------------------------------------
    # Overlays
    # ------------------------------------------------------------------
    def _overlay_box(self, height=520):
        dim = pygame.Surface((config.WINDOW_WIDTH, config.WINDOW_HEIGHT), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 185))
        self.screen.blit(dim, (0, 0))
        box = pygame.Rect(0, 0, 700, height)
        box.center = (config.WINDOW_WIDTH // 2, config.WINDOW_HEIGHT // 2)
        pygame.draw.rect(self.screen, (28, 28, 38), box, border_radius=16)
        pygame.draw.rect(self.screen, config.COLOR_ACCENT, box, 3, border_radius=16)
        return box

    def _draw_start_overlay(self, manager):
        box = self._overlay_box()
        cx = box.centerx
        self._text("CLUTCH SHOT", self.font_huge, config.COLOR_ACCENT,
                   cx, box.y + 60, center=True)
        self._text("Your moves (in front of the camera):", self.font_med,
                   config.COLOR_TEXT, cx, box.y + 125, center=True)

        lines = [
            "DRIBBLE    bounce a hand below your shoulders",
            "LAYUP      ONE hand up over your shoulder",
            "SHOT       BOTH hands up, hold 1 second",
            "SHOT FAKE  both hands up + down within 1 second",
            "STEPBACK   step away from the camera",
            "",
            "Chain different moves fast to fool the defender!",
        ]
        line_y = box.y + 165
        for line in lines:
            self._text(line, self.font_small, config.COLOR_TEXT_DIM, cx, line_y, center=True)
            line_y += 28

        # Difficulty selector.
        diff_y = box.bottom - 120
        self._text("DIFFICULTY:", self.font_med, config.COLOR_TEXT, cx - 220, diff_y)
        for i, name in enumerate(config.DIFFICULTY_PROFILES):
            selected = name == manager.difficulty
            color = config.COLOR_WARNING if selected else config.COLOR_TEXT_DIM
            self._text(f"{i + 1} {name}", self.font_med, color,
                       cx - 10 + i * 130, diff_y)

        self._text("PRESS SPACE TO START      Q TO QUIT", self.font_med,
                   config.COLOR_SUCCESS, cx, box.bottom - 50, center=True)

    def _draw_end_overlay(self, manager):
        box = self._overlay_box(height=560)
        cx = box.centerx
        self._text("FINAL BUZZER!", self.font_big, config.COLOR_ACCENT,
                   cx, box.y + 50, center=True)
        self._text(f"SCORE  {manager.score}", self.font_huge, config.COLOR_TEXT,
                   cx, box.y + 120, center=True)

        counts = manager.move_counts
        stats = [
            f"Makes / Attempts:  {manager.makes} / {manager.attempts}"
            f"   ({manager.shooting_pct:.0f}%)",
            f"Blocked by the defender:  {manager.blocks_against}",
            "",
            f"Shots {counts['shot']}   Layups {counts['layup']}   "
            f"Fakes {counts['shot_fake']}",
            f"Stepbacks {counts['stepback']}   Dribbles {counts['dribble']}",
            "",
            f"Difficulty:  {manager.difficulty}",
        ]
        line_y = box.y + 190
        for line in stats:
            self._text(line, self.font_med, config.COLOR_TEXT, cx, line_y, center=True)
            line_y += 38

        self._text("R - PLAY AGAIN      Q - QUIT", self.font_med,
                   config.COLOR_SUCCESS, cx, box.bottom - 45, center=True)
