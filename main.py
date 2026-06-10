"""
CLUTCH SHOT - AI Defender Basketball Challenge
Entry point.

PHASE 1 (current): vision system check.
Opens the webcam, runs MediaPipe Pose, draws the skeleton overlay, and
prints live joint angles for the shooting arm and legs. This proves the
camera, pose tracking, and angle math all work before any game logic
is added.

Later phases will replace this preview loop with the full Pygame game.

Run:
    python main.py

Controls:
    Q or ESC - quit
"""

import sys
import time

import cv2

import config
from vision.pose_tracker import PoseTracker
from vision.biomechanics import calculate_angle, midpoint, tilt_degrees


def open_camera():
    """
    Open the webcam configured in config.CAMERA_INDEX.

    Exits with a helpful message if no camera can be opened, since
    nothing else in the game works without one.
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


def draw_text(frame, text, position, color=(255, 255, 255), scale=0.6):
    """Draw readable text with a thin black outline onto the frame."""
    x, y = position
    # Outline first (thicker, black), then the colored text on top.
    cv2.putText(frame, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX,
                scale, (0, 0, 0), 4, cv2.LINE_AA)
    cv2.putText(frame, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX,
                scale, color, 2, cv2.LINE_AA)


def compute_debug_angles(joints):
    """
    Compute the joint angles Phase 1 displays, using the dominant arm
    from config.py.

    Args:
        joints: dict of joint name -> (x, y, visibility) from PoseTracker.

    Returns:
        dict of label -> value (degrees), ready to print on screen.
    """
    side = config.DOMINANT_ARM  # "right" or "left"

    # Shooting-arm elbow angle: shoulder -> elbow -> wrist.
    elbow_angle = calculate_angle(
        joints[f"{side}_shoulder"],
        joints[f"{side}_elbow"],
        joints[f"{side}_wrist"],
    )

    # Same-side knee angle: hip -> knee -> ankle.
    knee_angle = calculate_angle(
        joints[f"{side}_hip"],
        joints[f"{side}_knee"],
        joints[f"{side}_ankle"],
    )

    # Balance preview: how tilted the shoulder line is (0 = level).
    shoulder_tilt = tilt_degrees(joints["left_shoulder"], joints["right_shoulder"])

    return {
        f"{side} elbow": elbow_angle,
        f"{side} knee": knee_angle,
        "shoulder tilt": shoulder_tilt,
    }


def main():
    """Phase 1 preview loop: webcam + skeleton + live angles."""
    print("CLUTCH SHOT - Phase 1 vision check")
    print(f"Dominant arm: {config.DOMINANT_ARM}")
    print("Press Q or ESC in the video window to quit.\n")

    camera = open_camera()
    tracker = PoseTracker()

    # Simple FPS counter so we can confirm the laptop keeps up.
    frame_count = 0
    fps = 0.0
    fps_timer = time.time()

    try:
        while True:
            ok, frame = camera.read()
            if not ok:
                print("WARNING: failed to read a frame from the camera.")
                break

            # Mirror the image so it behaves like a mirror - moving your
            # right hand moves the figure's right side on screen.
            frame = cv2.flip(frame, 1)

            joints = tracker.process(frame)
            tracker.draw_skeleton(frame)

            if joints is not None:
                # Show live angles so we can verify the math by eye:
                # straighten your arm -> elbow angle should approach 180.
                angles = compute_debug_angles(joints)
                y = 30
                for label, value in angles.items():
                    draw_text(frame, f"{label}: {value:5.1f} deg", (10, y),
                              color=(0, 165, 255))
                    y += 28

                visibility = tracker.body_visibility()
                draw_text(frame, f"body visibility: {visibility:.2f}", (10, y))

                # Mark the body center (hip midpoint) with a small circle.
                hip_center = midpoint(joints["left_hip"], joints["right_hip"])
                h, w = frame.shape[:2]
                cv2.circle(frame, (int(hip_center[0] * w), int(hip_center[1] * h)),
                           6, (0, 165, 255), -1)
            else:
                draw_text(frame, "No player detected - step into frame",
                          (10, 30), color=(0, 0, 255))

            # Update the FPS counter once per second.
            frame_count += 1
            now = time.time()
            if now - fps_timer >= 1.0:
                fps = frame_count / (now - fps_timer)
                frame_count = 0
                fps_timer = now
            draw_text(frame, f"FPS: {fps:.0f}", (10, frame.shape[0] - 15),
                      scale=0.5)

            cv2.imshow("CLUTCH SHOT - Phase 1 (Q to quit)", frame)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), ord("Q"), 27):  # 27 = ESC
                break
    finally:
        # Always release the camera and windows, even after an error,
        # so the webcam isn't left locked by a dead process.
        camera.release()
        tracker.close()
        cv2.destroyAllWindows()
        print("Camera released. Goodbye!")


if __name__ == "__main__":
    main()
