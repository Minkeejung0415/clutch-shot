"""
CLUTCH SHOT - AI Defender Basketball Challenge
Entry point: wires the vision pipeline to the game and the UI.

Per frame the data flows one way:

    webcam -> PoseTracker -> MotionDetector -> GameManager -> GameUI

Run:
    python main.py

Controls:
    SPACE - start the game (from the start screen)
    R     - restart (from the end screen)
    Q/ESC - quit at any time

Want a quick camera-only check without the game? Run:
    python main.py --vision-check
"""

import sys
import time

import cv2
import pygame

import config
from game.game_manager import STATE_GAME_OVER, STATE_PLAYING, STATE_START, GameManager
from game.ui import GameUI
from vision.motion_detector import MotionDetector
from vision.pose_tracker import PoseTracker


def open_camera():
    """
    Open the webcam configured in config.CAMERA_INDEX.

    Exits with a helpful message if no camera can be opened, since
    nothing in the game works without one.
    """
    capture = cv2.VideoCapture(config.CAMERA_INDEX)
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_WIDTH)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_HEIGHT)

    if not capture.isOpened():
        print(f"ERROR: Could not open camera index {config.CAMERA_INDEX}.")
        print("Try changing CAMERA_INDEX in config.py (0, 1, 2, ...)")
        print("and make sure no other app is using the webcam.")
        sys.exit(1)
    return capture


def run_game():
    """The full Pygame game loop."""
    pygame.init()
    pygame.display.set_caption("CLUTCH SHOT")
    screen = pygame.display.set_mode((config.WINDOW_WIDTH, config.WINDOW_HEIGHT))
    clock = pygame.time.Clock()

    camera = open_camera()
    tracker = PoseTracker()
    detector = MotionDetector()
    manager = GameManager()
    ui = GameUI(screen)

    print("CLUTCH SHOT ready. SPACE to start, Q to quit.")

    running = True
    try:
        while running:
            # dt in seconds; also caps the loop at TARGET_FPS.
            dt = clock.tick(config.TARGET_FPS) / 1000.0
            now = time.time()

            # ---- Input ------------------------------------------------
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_q, pygame.K_ESCAPE):
                        running = False
                    elif event.key == pygame.K_SPACE and manager.state == STATE_START:
                        manager.start()
                        print("Game on! 60 seconds on the clock.")
                    elif event.key == pygame.K_r and manager.state == STATE_GAME_OVER:
                        manager.start()
                        print("Rematch! 60 seconds on the clock.")

            # ---- Vision -----------------------------------------------
            ok, frame = camera.read()
            frame_rgb = None
            joints = None
            if ok:
                # Mirror so the screen behaves like a mirror.
                frame = cv2.flip(frame, 1)
                joints = tracker.process(frame)
                tracker.draw_skeleton(frame)
                # Pygame wants RGB; OpenCV delivers BGR.
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # ---- Game logic -------------------------------------------
            # The detector only feeds the game while the clock runs, but
            # it keeps tracking on other screens so its state display is
            # live and the player can warm up.
            motion_event = detector.update(joints, now)
            if manager.state == STATE_PLAYING:
                manager.handle_motion_event(motion_event)
            manager.update(dt)

            # ---- Draw -------------------------------------------------
            ui.render(frame_rgb, manager, detector.state, tracker.body_visibility())
    finally:
        # Always free the camera even after a crash, so it isn't left
        # locked for other apps.
        camera.release()
        tracker.close()
        pygame.quit()
        cv2.destroyAllWindows()
        print("Camera released. Thanks for playing!")


def run_vision_check():
    """
    The Phase 1 diagnostic: plain OpenCV window with the skeleton and
    live joint angles. Useful for verifying the camera and tracking
    without launching the full game.
    """
    from vision.biomechanics import calculate_angle, tilt_degrees

    camera = open_camera()
    tracker = PoseTracker()
    side = config.DOMINANT_ARM
    print("Vision check - press Q or ESC to quit.")

    try:
        while True:
            ok, frame = camera.read()
            if not ok:
                break
            frame = cv2.flip(frame, 1)
            joints = tracker.process(frame)
            tracker.draw_skeleton(frame)

            if joints is not None:
                elbow = calculate_angle(joints[f"{side}_shoulder"],
                                        joints[f"{side}_elbow"],
                                        joints[f"{side}_wrist"])
                knee = calculate_angle(joints[f"{side}_hip"],
                                       joints[f"{side}_knee"],
                                       joints[f"{side}_ankle"])
                tilt = tilt_degrees(joints["left_shoulder"], joints["right_shoulder"])
                for i, line in enumerate([f"{side} elbow: {elbow:5.1f}",
                                          f"{side} knee:  {knee:5.1f}",
                                          f"tilt: {tilt:5.1f}"]):
                    cv2.putText(frame, line, (10, 30 + i * 28),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 165, 255), 2)

            cv2.imshow("CLUTCH SHOT - vision check (Q to quit)", frame)
            if cv2.waitKey(1) & 0xFF in (ord("q"), ord("Q"), 27):
                break
    finally:
        camera.release()
        tracker.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    if "--vision-check" in sys.argv:
        run_vision_check()
    else:
        run_game()
