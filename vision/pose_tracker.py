"""
PoseTracker: a thin, friendly wrapper around MediaPipe Pose.

Responsibilities:
- Run MediaPipe Pose on each BGR webcam frame.
- Expose the 12 body landmarks the game cares about as a simple dict of
  (x, y, visibility) tuples in normalized coordinates.
- Draw the skeleton overlay on the frame for the player to see.

Everything downstream (motion detection, form scoring) reads from the
dict this class produces, so the rest of the game never imports
MediaPipe directly.
"""

import cv2
import mediapipe as mp

import config

# The MediaPipe pose solution and its drawing helpers.
mp_pose = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles

# The joints the game tracks, mapped to MediaPipe's landmark enum.
# Keys are the friendly names used everywhere else in the codebase.
TRACKED_LANDMARKS = {
    "left_shoulder": mp_pose.PoseLandmark.LEFT_SHOULDER,
    "right_shoulder": mp_pose.PoseLandmark.RIGHT_SHOULDER,
    "left_elbow": mp_pose.PoseLandmark.LEFT_ELBOW,
    "right_elbow": mp_pose.PoseLandmark.RIGHT_ELBOW,
    "left_wrist": mp_pose.PoseLandmark.LEFT_WRIST,
    "right_wrist": mp_pose.PoseLandmark.RIGHT_WRIST,
    "left_hip": mp_pose.PoseLandmark.LEFT_HIP,
    "right_hip": mp_pose.PoseLandmark.RIGHT_HIP,
    "left_knee": mp_pose.PoseLandmark.LEFT_KNEE,
    "right_knee": mp_pose.PoseLandmark.RIGHT_KNEE,
    "left_ankle": mp_pose.PoseLandmark.LEFT_ANKLE,
    "right_ankle": mp_pose.PoseLandmark.RIGHT_ANKLE,
}


class PoseTracker:
    """Detects and tracks the player's pose frame by frame."""

    def __init__(self):
        # Create one long-lived Pose object; MediaPipe tracks between
        # frames internally, which is faster than re-detecting each frame.
        self._pose = mp_pose.Pose(
            model_complexity=config.POSE_MODEL_COMPLEXITY,
            min_detection_confidence=config.POSE_DETECTION_CONFIDENCE,
            min_tracking_confidence=config.POSE_TRACKING_CONFIDENCE,
        )
        # Raw MediaPipe results for the latest frame (used for drawing).
        self._latest_results = None

    def process(self, frame_bgr):
        """
        Run pose detection on one webcam frame.

        Args:
            frame_bgr: the frame as OpenCV delivers it (BGR color order).

        Returns:
            A dict mapping joint names (e.g. "right_wrist") to
            (x, y, visibility) tuples in normalized 0-1 coordinates,
            or None if no person was detected this frame.
        """
        # MediaPipe expects RGB; OpenCV gives BGR, so convert first.
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)

        # Marking the frame read-only lets MediaPipe skip a copy (faster).
        frame_rgb.flags.writeable = False
        self._latest_results = self._pose.process(frame_rgb)
        frame_rgb.flags.writeable = True

        if not self._latest_results.pose_landmarks:
            return None

        all_landmarks = self._latest_results.pose_landmarks.landmark

        # Extract only the joints the game uses into a simple dict.
        joints = {}
        for name, landmark_id in TRACKED_LANDMARKS.items():
            lm = all_landmarks[landmark_id]
            joints[name] = (lm.x, lm.y, lm.visibility)
        return joints

    def body_visibility(self):
        """
        Return the average visibility (0.0-1.0) of the tracked joints for
        the latest processed frame, or 0.0 if no pose was found.

        The game uses this to warn the player to step back into frame.
        """
        if not self._latest_results or not self._latest_results.pose_landmarks:
            return 0.0
        all_landmarks = self._latest_results.pose_landmarks.landmark
        tracked = [all_landmarks[lid] for lid in TRACKED_LANDMARKS.values()]
        return sum(lm.visibility for lm in tracked) / len(tracked)

    def draw_skeleton(self, frame_bgr):
        """
        Draw the full MediaPipe skeleton overlay onto the frame in place.

        Call this AFTER process() so it draws the latest detection.
        """
        if self._latest_results and self._latest_results.pose_landmarks:
            mp_drawing.draw_landmarks(
                frame_bgr,
                self._latest_results.pose_landmarks,
                mp_pose.POSE_CONNECTIONS,
                landmark_drawing_spec=mp_drawing_styles.get_default_pose_landmarks_style(),
            )

    def close(self):
        """Release MediaPipe resources. Call once when the game exits."""
        self._pose.close()
