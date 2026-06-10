# 🏀 CLUTCH SHOT

**AI Defender Basketball Challenge** — an interactive basketball game played
with your body. Stand in front of your webcam, perform real shooting motions,
and beat the clock while virtual defenders apply pressure. Built with
real-time pose detection (MediaPipe + OpenCV) and a Pygame interface.

> **Project status: Phase 1 of 5** — vision system (webcam, pose tracking,
> joint angles) is complete. Game logic and UI arrive in later phases.

---

## Features

- 🎯 **Real shooting-motion detection** — a state machine tracks your body
  through LOADING → RISING → RELEASED using live joint angles *(Phase 2)*
- 🛡️ **Four defender personalities** — from a lazy defender to an
  end-of-game boss, each applying OPEN / LIGHT / HEAVY pressure *(Phase 4)*
- 📐 **Form score (0–100)** — elbow extension, knee bend, vertical rise,
  balance and smoothness, all weighted and tunable *(Phase 4)*
- 🤾 **Shot fakes** — bait the defender into the air, then rise and fire
  for a bonus *(Phase 5)*
- 😮‍💨 **Fatigue system** — spam shots and your percentages drop *(Phase 5)*
- 🖥️ **Basketball-styled Pygame dashboard** — webcam + skeleton on the
  left, live game stats on the right *(Phase 3)*

## Screenshots

*Coming soon — screenshots will be added as each phase lands.*

| Phase 1 vision check | Game dashboard | End screen |
|---|---|---|
| _placeholder_ | _placeholder_ | _placeholder_ |

---

## Installation

Requires **Python 3.11+** and a webcam.

### Windows (PowerShell)

```powershell
git clone https://github.com/minkeejung0415/clutch-shot.git
cd clutch-shot
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### macOS / Linux

```bash
git clone https://github.com/minkeejung0415/clutch-shot.git
cd clutch-shot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Running the game

```bash
python main.py
```

**Phase 1** opens a webcam window with your pose skeleton drawn on top and
live joint angles (shooting elbow, knee, shoulder tilt) in the corner.
Straighten your arm and watch the elbow angle approach 180° — that confirms
the angle math is working.

### Controls

| Key | Action |
|---|---|
| `Q` / `ESC` | Quit (Phase 1 preview) |
| `SPACE` | Start game *(Phase 3)* |
| `R` | Restart after game over *(Phase 3)* |

Left-handed? Open `config.py` and set `DOMINANT_ARM = "left"`.

## Running the tests

```bash
pytest tests/ -v
```

The tests cover the pure-math layer (joint angles, midpoints, tilt,
visibility) and config sanity checks — no camera needed.

## How motion detection works

1. **MediaPipe Pose** finds 33 body landmarks per frame; the game tracks 12
   (shoulders, elbows, wrists, hips, knees, ankles).
2. **Biomechanics helpers** (`vision/biomechanics.py`) turn landmarks into
   numbers: the elbow angle via the vector dot-product formula, knee bend,
   shoulder/hip tilt for balance, and frame-to-frame vertical wrist speed.
3. **A state machine** (`vision/motion_detector.py`, Phase 2) recognizes a
   shot: knees bend (LOADING) → wrist rises fast (RISING) → wrist above the
   shoulder with the elbow extended (RELEASED) → COOLDOWN so one motion
   counts once. A rise that comes back down *without* elbow extension is a
   **shot fake**.
4. **Game logic** (Phase 4) converts form quality, defender pressure, and
   fatigue into a transparent make/miss probability.

All thresholds live in `config.py` and are deliberately forgiving — this is
a demo, not a shooting clinic.

## Project structure

```
clutch-shot/
├── main.py               # entry point (Phase 1: vision check)
├── config.py             # every tunable constant
├── requirements.txt
├── game/
│   ├── game_manager.py   # round flow, timer, score      (Phase 3+)
│   ├── defender.py       # defender AI & pressure        (Phase 4+)
│   ├── scoring.py        # form score, probability, fatigue (Phase 4+)
│   └── ui.py             # Pygame dashboard              (Phase 3+)
├── vision/
│   ├── pose_tracker.py   # MediaPipe Pose wrapper        ✅
│   ├── biomechanics.py   # angle / movement math         ✅
│   └── motion_detector.py# shot state machine            (Phase 2)
└── tests/
    ├── test_biomechanics.py  ✅
    └── test_scoring.py       (expands in Phase 4)
```

## Limitations

- Single player only; a second person in frame can confuse tracking.
- Needs decent lighting and the full upper body (ideally full body) in view.
- Shot detection is heuristic — unusual shooting forms may need threshold
  tuning in `config.py`.
- No actual ball tracking; the game judges *form*, not where a ball goes.

## Future improvements

- Ball detection for real make/miss verification
- Dribble-move recognition (crossovers, step-backs)
- Local high-score persistence
- Two-player split-screen mode
- Sound effects and crowd reactions

## Portfolio value

This project demonstrates real-time computer vision (MediaPipe pose
estimation), gesture recognition via a hand-rolled state machine, game
design with transparent probability math, clean modular architecture with
unit tests, and Pygame UI work — all running locally with no cloud
dependencies.

## Technology stack

| Tool | Role |
|---|---|
| Python 3.11+ | language |
| OpenCV | webcam capture & image handling |
| MediaPipe Pose | body landmark detection |
| Pygame | game window, UI, input |
| NumPy | numeric helpers |
| pytest | unit testing |
