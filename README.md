# 🏀 CLUTCH SHOT

**AI Defender Basketball Challenge** — an interactive basketball game played
with your body. Stand in front of your webcam, perform real shooting motions,
and beat the clock while virtual defenders apply pressure. Built with
real-time pose detection (MediaPipe + OpenCV) and a Pygame interface.

> **Project status: complete MVP** — all five development phases are done:
> pose tracking, shot/fake detection, defenders, scoring, and the full
> Pygame UI.

---

## Features

- 🎯 **Real shooting-motion detection** — a state machine tracks your body
  through IDLE → LOADING → RISING → RELEASED using live joint angles
- 🤾 **Shot fakes** — pump fake to bait the defender into the air, then
  rise and fire within 2 seconds for a wide-open bonus shot
- 🛡️ **Four defender personalities** — Lazy, Aggressive, Disciplined, and
  a BOSS who takes over the final 15 seconds, each applying
  OPEN / LIGHT / HEAVY pressure with its own probabilities
- 📐 **Form score (0–100)** — elbow extension, knee bend, vertical rise,
  balance, and smoothness, all weighted and tunable in `config.py`
- 🎲 **Transparent make/miss math** — every shot shows its computed
  probability: base + form + pressure − fatigue + fake bonus
- 😮‍💨 **Fatigue system** — spam shots and your percentages drop; rest to
  recover
- 🖥️ **Basketball-styled Pygame dashboard** — webcam + skeleton on the
  left; timer, score, defender, mini-court, last-shot info, fatigue bar,
  and action messages on the right

## Screenshots

*Placeholders — add captures of your own runs here.*

| Start screen | Game dashboard | End screen |
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

Stand back so your **full body** (head to ankles) is in frame, press
SPACE, and you have 60 seconds. Dip your knees, rise, and extend your
shooting arm overhead to shoot. Pump fake (rise without extending, then
come back down) to bait the defender — if they bite, your next shot
within 2 seconds is wide open and worth a bonus.

Camera acting up? Run the diagnostic view first:

```bash
python main.py --vision-check
```

It shows just the webcam, skeleton, and live joint angles — straighten
your arm and the elbow reading should approach 180°.

### Controls

| Key | Action |
|---|---|
| `SPACE` | Start game (start screen) |
| `R` | Restart (end screen) |
| `Q` / `ESC` | Quit at any time |

Left-handed? Open `config.py` and set `DOMINANT_ARM = "left"`.

### Scoring

| Event | Points |
|---|---|
| Made shot | 2 |
| ... while OPEN | +1 |
| ... within 2s of a defender biting your fake | +1 |
| ... with EXCELLENT form (85+) | +1 |
| Missed shot | 0 |

## Running the tests

```bash
pytest tests/ -v
```

All tests are headless (no camera or game window needed). They cover the
biomechanics math (angles, midpoints, tilt, visibility), the shot/fake
state machine driven by synthetic joint data, probability clamping,
form-score range, defender pressure, fatigue bounds, and point bonuses.

## How motion detection works

1. **MediaPipe Pose** finds 33 body landmarks per frame; the game tracks 12
   (shoulders, elbows, wrists, hips, knees, ankles).
2. **Biomechanics helpers** (`vision/biomechanics.py`) turn landmarks into
   numbers: the elbow angle via the vector dot-product formula, knee bend,
   shoulder/hip tilt for balance, and frame-to-frame vertical wrist speed.
3. **A state machine** (`vision/motion_detector.py`) recognizes a shot:
   knees bend (LOADING) → wrist rises fast (RISING) → wrist above the
   shoulder with the elbow extended (RELEASED) → COOLDOWN so one motion
   counts once. A rise that comes back down *without* elbow extension is a
   **shot fake**.
4. **Game logic** (`game/scoring.py`, `game/game_manager.py`) converts the
   raw measurements into a weighted form score, then a make/miss
   probability:
   `0.25 base + form/200 + pressure (±0.15/−0.20) − fatigue (≤0.15) +
   fake bonus (0.10)`, clamped to 5–90%. One random roll decides the
   result.

All thresholds live in `config.py` and are deliberately forgiving — this is
a demo, not a shooting clinic.

## Project structure

```
clutch-shot/
├── main.py                # entry point: game loop + --vision-check mode
├── config.py              # every tunable constant
├── requirements.txt
├── game/
│   ├── game_manager.py    # game clock, score, shot resolution
│   ├── defender.py        # defender personalities & pressure
│   ├── scoring.py         # form score, probability, fatigue, points
│   └── ui.py              # Pygame dashboard, start/end screens
├── vision/
│   ├── pose_tracker.py    # MediaPipe Pose wrapper
│   ├── biomechanics.py    # angle / movement math (pure functions)
│   └── motion_detector.py # IDLE→LOADING→RISING→RELEASED state machine
└── tests/
    ├── test_biomechanics.py    # angle/midpoint/tilt math
    ├── test_motion_detector.py # synthetic shot & fake sequences
    └── test_scoring.py         # probability, form, defenders, fatigue
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
