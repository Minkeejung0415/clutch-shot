"""
Pygame user interface for CLUTCH SHOT.

Layout (config.WINDOW_WIDTH x WINDOW_HEIGHT, default 1280x720):

    +--------------------------------+---------------------------+
    |  CLUTCH SHOT          (title)  |        DASHBOARD          |
    |                                |  timer / score / stats    |
    |   webcam view with             |  defender + mini court    |
    |   pose skeleton                |  last shot info           |
    |                                |  fatigue bar              |
    |   detector state strip         |  action messages          |
    +--------------------------------+---------------------------+

Everything is drawn with plain Pygame shapes - no image assets - in a
dark court theme with basketball-orange accents (colors in config.py).

The UI is read-only: it draws whatever GameManager and MotionDetector
report and never changes game state.
"""

import pygame

import config
from game.game_manager import STATE_GAME_OVER, STATE_START
from game.scoring import form_label

# Where the webcam view lives on screen.
CAM_X, CAM_Y = 20, 90
CAM_W, CAM_H = 620, 465

# Where the dashboard column starts.
DASH_X = CAM_X + CAM_W + 20
DASH_W = config.WINDOW_WIDTH - DASH_X - 20

# Colors of the pressure chips on the dashboard.
PRESSURE_COLORS = {
    "OPEN": config.COLOR_SUCCESS,
    "LIGHT_CONTEST": config.COLOR_WARNING,
    "HEAVY_CONTEST": config.COLOR_FAIL,
}


class GameUI:
    """Draws every screen of the game onto a Pygame surface."""

    def __init__(self, screen):
        self.screen = screen
        # pygame's bundled default font keeps the project asset-free.
        self.font_huge = pygame.font.Font(None, 96)
        self.font_big = pygame.font.Font(None, 56)
        self.font_med = pygame.font.Font(None, 36)
        self.font_small = pygame.font.Font(None, 26)

    # ------------------------------------------------------------------
    # Small drawing helpers
    # ------------------------------------------------------------------
    def _text(self, text, font, color, x, y, center=False):
        """Render text at (x, y); center=True centers it on that point."""
        surface = font.render(text, True, color)
        rect = surface.get_rect()
        if center:
            rect.center = (x, y)
        else:
            rect.topleft = (x, y)
        self.screen.blit(surface, rect)
        return rect.bottom

    def _panel(self, rect, border=False):
        """A slightly lighter rounded box that groups dashboard content."""
        pygame.draw.rect(self.screen, (30, 30, 40), rect, border_radius=10)
        if border:
            pygame.draw.rect(self.screen, config.COLOR_ACCENT, rect, 2, border_radius=10)

    # ------------------------------------------------------------------
    # Frame entry point
    # ------------------------------------------------------------------
    def render(self, frame_rgb, manager, detector_state, body_visibility):
        """
        Draw one full frame.

        Args:
            frame_rgb: the mirrored webcam image with the skeleton
                already drawn, as an RGB numpy array (h, w, 3), or None
                if the camera produced no frame.
            manager: the GameManager (read-only).
            detector_state: current MotionDetector state name.
            body_visibility: 0.0-1.0 from PoseTracker.
        """
        self.screen.fill(config.COLOR_BACKGROUND)

        self._draw_header()
        self._draw_webcam(frame_rgb, detector_state, body_visibility)
        self._draw_dashboard(manager)

        # Overlays sit on top of the live view so the player can line
        # themselves up in the camera before pressing SPACE.
        if manager.state == STATE_START:
            self._draw_start_overlay()
        elif manager.state == STATE_GAME_OVER:
            self._draw_end_overlay(manager)

        pygame.display.flip()

    # ------------------------------------------------------------------
    def _draw_header(self):
        """Title bar with a little basketball icon."""
        self._text("CLUTCH SHOT", self.font_big, config.COLOR_ACCENT, CAM_X, 22)
        self._text("AI DEFENDER BASKETBALL CHALLENGE", self.font_small,
                   config.COLOR_TEXT_DIM, CAM_X + 330, 40)

        # Basketball icon: orange circle with seam lines.
        cx, cy, r = config.WINDOW_WIDTH - 50, 45, 22
        pygame.draw.circle(self.screen, config.COLOR_ACCENT, (cx, cy), r)
        pygame.draw.line(self.screen, config.COLOR_BACKGROUND, (cx - r, cy), (cx + r, cy), 2)
        pygame.draw.line(self.screen, config.COLOR_BACKGROUND, (cx, cy - r), (cx, cy + r), 2)
        pygame.draw.arc(self.screen, config.COLOR_BACKGROUND,
                        (cx - r - 10, cy - r, r * 2, r * 2), -1.1, 1.1, 2)
        pygame.draw.arc(self.screen, config.COLOR_BACKGROUND,
                        (cx - r + 10, cy - r, r * 2, r * 2), 2.0, 4.2, 2)

    # ------------------------------------------------------------------
    def _draw_webcam(self, frame_rgb, detector_state, body_visibility):
        """The live camera view plus the motion-detector status strip."""
        cam_rect = pygame.Rect(CAM_X, CAM_Y, CAM_W, CAM_H)
        pygame.draw.rect(self.screen, (0, 0, 0), cam_rect)

        if frame_rgb is not None:
            h, w = frame_rgb.shape[:2]
            # numpy frame -> pygame surface, scaled to fit the panel.
            surface = pygame.image.frombuffer(frame_rgb.tobytes(), (w, h), "RGB")
            surface = pygame.transform.smoothscale(surface, (CAM_W, CAM_H))
            self.screen.blit(surface, cam_rect)
        else:
            self._text("NO CAMERA SIGNAL", self.font_med, config.COLOR_FAIL,
                       cam_rect.centerx, cam_rect.centery, center=True)

        pygame.draw.rect(self.screen, config.COLOR_ACCENT, cam_rect, 3, border_radius=4)

        # Status strip under the camera: detector state + visibility.
        strip_y = CAM_Y + CAM_H + 12
        self._text(f"MOTION: {detector_state}", self.font_small,
                   config.COLOR_ACCENT, CAM_X, strip_y)

        if body_visibility < config.MIN_LANDMARK_VISIBILITY:
            warning = "STEP BACK - BODY NOT FULLY VISIBLE"
            self._text(warning, self.font_small, config.COLOR_FAIL, CAM_X + 220, strip_y)
        else:
            self._text(f"TRACKING OK ({body_visibility:.0%})", self.font_small,
                       config.COLOR_SUCCESS, CAM_X + 220, strip_y)

    # ------------------------------------------------------------------
    def _draw_dashboard(self, manager):
        """The whole right-hand column of game information."""
        y = 90

        # --- Timer and score, side by side, big ----------------------
        self._panel(pygame.Rect(DASH_X, y, DASH_W, 96))
        # Timer turns red for the final 10 seconds.
        timer_color = config.COLOR_FAIL if manager.time_remaining <= 10 else config.COLOR_TEXT
        self._text("TIME", self.font_small, config.COLOR_TEXT_DIM, DASH_X + 20, y + 10)
        self._text(f"{manager.time_remaining:04.1f}", self.font_huge, timer_color,
                   DASH_X + 20, y + 26)
        self._text("SCORE", self.font_small, config.COLOR_TEXT_DIM, DASH_X + 320, y + 10)
        self._text(str(manager.score), self.font_huge, config.COLOR_ACCENT,
                   DASH_X + 320, y + 26)
        y += 108

        # --- Shooting stats line --------------------------------------
        self._panel(pygame.Rect(DASH_X, y, DASH_W, 44))
        stats = (f"ATTEMPTS {manager.attempts}    MAKES {manager.makes}    "
                 f"FG {manager.shooting_pct:.0f}%")
        self._text(stats, self.font_med, config.COLOR_TEXT, DASH_X + 20, y + 8)
        y += 56

        # --- Defender panel with mini court ---------------------------
        panel = pygame.Rect(DASH_X, y, DASH_W, 150)
        self._panel(panel, border=manager.defenders.defender.is_boss)
        defender = manager.defenders.defender
        name_color = config.COLOR_FAIL if defender.is_boss else config.COLOR_TEXT
        self._text("DEFENDER", self.font_small, config.COLOR_TEXT_DIM, DASH_X + 20, y + 10)
        self._text(defender.display_name, self.font_med, name_color, DASH_X + 20, y + 34)

        # Pressure chip, colored by how tight the defense is.
        pressure = manager.defenders.pressure_for_shot()
        chip_color = PRESSURE_COLORS[pressure]
        chip = pygame.Rect(DASH_X + 20, y + 78, 230, 34)
        pygame.draw.rect(self.screen, chip_color, chip, border_radius=8)
        self._text(pressure.replace("_", " "), self.font_small, (10, 10, 10),
                   chip.centerx, chip.centery, center=True)

        if manager.defenders.fake_window > 0:
            self._text(f"DEFENDER IN THE AIR! {manager.defenders.fake_window:.1f}s",
                       self.font_small, config.COLOR_SUCCESS, DASH_X + 20, y + 120)

        self._draw_mini_court(DASH_X + DASH_W - 180, y + 12, pressure)
        y += 162

        # --- Last shot panel -------------------------------------------
        self._panel(pygame.Rect(DASH_X, y, DASH_W, 88))
        self._text("LAST SHOT", self.font_small, config.COLOR_TEXT_DIM, DASH_X + 20, y + 10)
        if manager.last_form_score is not None:
            form = manager.last_form_score
            self._text(f"FORM {form:.0f} ({form_label(form)})", self.font_med,
                       config.COLOR_TEXT, DASH_X + 20, y + 38)
            self._text(f"PROB {manager.last_probability:.0%}", self.font_med,
                       config.COLOR_TEXT, DASH_X + 280, y + 38)
            result_color = (config.COLOR_SUCCESS if manager.last_result == "MADE"
                            else config.COLOR_FAIL)
            self._text(manager.last_result or "", self.font_med, result_color,
                       DASH_X + 450, y + 38)
        else:
            self._text("Take your first shot!", self.font_med,
                       config.COLOR_TEXT_DIM, DASH_X + 20, y + 38)
        y += 100

        # --- Fatigue bar -----------------------------------------------
        self._panel(pygame.Rect(DASH_X, y, DASH_W, 58))
        self._text("FATIGUE", self.font_small, config.COLOR_TEXT_DIM, DASH_X + 20, y + 8)
        bar_bg = pygame.Rect(DASH_X + 20, y + 32, DASH_W - 40, 16)
        pygame.draw.rect(self.screen, (60, 60, 70), bar_bg, border_radius=8)
        fill_fraction = manager.fatigue.value / config.FATIGUE_MAX
        if fill_fraction > 0:
            fill = pygame.Rect(bar_bg.x, bar_bg.y,
                               max(8, int(bar_bg.width * fill_fraction)), bar_bg.height)
            # Bar shifts green -> yellow -> red as fatigue climbs.
            if fill_fraction < 0.4:
                bar_color = config.COLOR_SUCCESS
            elif fill_fraction < 0.7:
                bar_color = config.COLOR_WARNING
            else:
                bar_color = config.COLOR_FAIL
            pygame.draw.rect(self.screen, bar_color, fill, border_radius=8)
        y += 70

        # --- Action messages (newest on top) ---------------------------
        self._text("ACTION", self.font_small, config.COLOR_TEXT_DIM, DASH_X + 4, y)
        message_y = y + 26
        for message in manager.active_messages()[:3]:
            self._text(message, self.font_med, config.COLOR_ACCENT, DASH_X + 4, message_y)
            message_y += 34

    # ------------------------------------------------------------------
    def _draw_mini_court(self, x, y, pressure):
        """
        A tiny top-down half court: orange dot = shooter, red dot =
        defender. The defender's distance from the shooter visualizes
        the current pressure level.
        """
        court = pygame.Rect(x, y, 160, 120)
        pygame.draw.rect(self.screen, (45, 35, 28), court, border_radius=6)
        # Three-point arc around the (off-screen, top) basket.
        pygame.draw.arc(self.screen, (90, 75, 60),
                        (x + 10, y - 60, 140, 160), 3.34, 6.08, 2)

        shooter = (x + 80, y + 95)
        # Defender stands closer when the contest is tighter.
        gap = {"OPEN": 55, "LIGHT_CONTEST": 32, "HEAVY_CONTEST": 14}[pressure]
        defender_pos = (x + 80, y + 95 - gap)

        pygame.draw.circle(self.screen, config.COLOR_ACCENT, shooter, 9)
        pygame.draw.circle(self.screen, config.COLOR_FAIL, defender_pos, 9)
        # Defender's contesting arms when playing tight defense.
        if pressure == "HEAVY_CONTEST":
            pygame.draw.line(self.screen, config.COLOR_FAIL,
                             defender_pos, (defender_pos[0] - 12, defender_pos[1] - 12), 3)
            pygame.draw.line(self.screen, config.COLOR_FAIL,
                             defender_pos, (defender_pos[0] + 12, defender_pos[1] - 12), 3)

    # ------------------------------------------------------------------
    # Overlays
    # ------------------------------------------------------------------
    def _overlay_box(self):
        """Dim the screen and return a centered panel rect to draw in."""
        dim = pygame.Surface((config.WINDOW_WIDTH, config.WINDOW_HEIGHT), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 185))
        self.screen.blit(dim, (0, 0))
        box = pygame.Rect(0, 0, 640, 460)
        box.center = (config.WINDOW_WIDTH // 2, config.WINDOW_HEIGHT // 2)
        pygame.draw.rect(self.screen, (28, 28, 38), box, border_radius=16)
        pygame.draw.rect(self.screen, config.COLOR_ACCENT, box, 3, border_radius=16)
        return box

    def _draw_start_overlay(self):
        box = self._overlay_box()
        cx = box.centerx
        self._text("CLUTCH SHOT", self.font_huge, config.COLOR_ACCENT,
                   cx, box.y + 70, center=True)
        self._text(f"{config.GAME_DURATION} seconds. Score as much as you can.",
                   self.font_med, config.COLOR_TEXT, cx, box.y + 140, center=True)

        lines = [
            "Stand back so your full body is in frame.",
            "Bend your knees, rise, and extend to SHOOT.",
            "Pump fake to make the defender jump - then fire!",
            "Open shots and clean form earn bonus points.",
        ]
        line_y = box.y + 195
        for line in lines:
            self._text(line, self.font_small, config.COLOR_TEXT_DIM, cx, line_y, center=True)
            line_y += 32

        self._text("PRESS SPACE TO START", self.font_med, config.COLOR_SUCCESS,
                   cx, box.bottom - 90, center=True)
        self._text("PRESS Q TO QUIT", self.font_small, config.COLOR_TEXT_DIM,
                   cx, box.bottom - 50, center=True)

    def _draw_end_overlay(self, manager):
        box = self._overlay_box()
        cx = box.centerx
        self._text("FINAL BUZZER!", self.font_big, config.COLOR_ACCENT,
                   cx, box.y + 55, center=True)
        self._text(f"SCORE  {manager.score}", self.font_huge, config.COLOR_TEXT,
                   cx, box.y + 130, center=True)

        stats = [
            f"Makes / Attempts:  {manager.makes} / {manager.attempts}",
            f"Shooting:  {manager.shooting_pct:.0f}%",
            f"Average form:  {manager.average_form:.0f}",
            f"Best form:  {manager.best_form:.0f}",
        ]
        line_y = box.y + 200
        for line in stats:
            self._text(line, self.font_med, config.COLOR_TEXT, cx, line_y, center=True)
            line_y += 40

        self._text("R - PLAY AGAIN      Q - QUIT", self.font_med,
                   config.COLOR_SUCCESS, cx, box.bottom - 45, center=True)
