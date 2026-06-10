# 🏀 CLUTCH SHOT

**Beat the Defender** — an interactive basketball game played with your
body. Stand in front of your webcam and dribble, fake, step back, and
shoot against a live virtual defender who guards the rim, chases your
moves, bites on good fakes, and blocks lazy shots. Built with real-time
pose detection (MediaPipe + OpenCV) and a Pygame interface.

---

## The five moves

The classifier reads your hands relative to your shoulder line on
**every frame**, so moves chain instantly — fake into a dribble into a
stepback into a shot with no dead time.

| Move | How to perform it |
|---|---|
| **DRIBBLE** | bounce one hand up and down **below** your shoulders |
| **LAYUP** | put **one** hand up over your shoulder |
| **SHOT** | put **both** hands up and hold for **1 second** (watch the charge bar) |
| **SHOT FAKE** | both hands up, then back **down within 1 second** |
| **STEPBACK** | step **backwards**, away from the camera |

## The defender

One animated defender stands between YOU and the hoop on the right side
of the screen, and he plays real defense:

- **follows your dribble** side to side to stay in front of the ball
- **bites on shot fakes** — while he's in the air or landing he can't
  defend anything, so that's your window
- **closes out your stepbacks** — a stepback buys you separation, but he
  works to erase it at his difficulty's closing speed
- **contests and blocks** — shoot into his chest and he can flat-out
  reject it; layups are easy points *unless* he's set at the rim

Whether he falls for your moves depends on exactly two things:

1. **Difficulty** (`1` EASY / `2` MEDIUM / `3` HARD on the start screen)
   — bite rate, block rate, contest penalty, closing speed, recovery time
2. **Your deception** — chain *different* setup moves (dribble, fake,
   stepback) within a few seconds and the deception meter fills, making
   him easier to fool and harder to block with. Spam one move and he
   stops respecting it.

## Scoring

| Result | Points |
|---|---|
| Made layup | 2 |
| Made shot | 2 |
| Made **stepback shot** (within 2 s of a stepback) | **3** |
| Missed or blocked | 0 |

Make probability is transparent:
`base (0.80 layup / 0.62 shot) + 0.15 if open − contest penalty +
separation bonus − fatigue − 0.12 if a three`, clamped to 5–95 %.
A blocked attempt never gets a roll — he just took it from you.

## Screenshots

*Placeholders — add captures of your own runs here.*

| Start screen | Gameplay | End screen |
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

Stand back so your **upper body and hands** are fully in frame, pick a
difficulty, press SPACE, and you have 60 seconds. Camera acting up? Run
the diagnostic view first — it shows the skeleton, your live posture
("BOTH HANDS UP" etc.), and prints every detected move to the console:

```bash
python main.py --vision-check
```

### Controls

| Key | Action |
|---|---|
| `1` / `2` / `3` | Difficulty: EASY / MEDIUM / HARD (start screen) |
| `SPACE` | Start game (start screen) |
| `R` | Restart (end screen) |
| `Q` / `ESC` | Quit at any time |

## Running the tests

```bash
pytest tests/ -v
```

All tests are headless (no camera or game window needed). They drive the
classifier with synthetic joint data acting out all five moves and the
fast combos, and cover probability clamping, defender reactions per
difficulty, separation/closeout behavior, fatigue bounds, and points.

## How it works

1. **MediaPipe Pose** finds 33 body landmarks per frame; the game uses
   shoulders and wrists for the moves (plus the rest for the skeleton).
2. **The classifier** (`vision/motion_detector.py`) evaluates every rule
   every frame: hands vs. the shoulder line for shot/fake/layup timing
   windows, vertical wrist reversals for dribbles, and shrinking
   shoulder width (you getting smaller on camera) for stepbacks.
3. **The DefenderAI** (`game/defender.py`) is a small state machine —
   GUARD / IN_AIR / CONTEST / RECOVER / BEATEN — whose dice rolls come
   from the difficulty profile plus your live deception level.
4. **Resolution** (`game/scoring.py`, `game/game_manager.py`): the
   defender first decides OPEN / CONTESTED / BLOCKED, then a single
   probability roll decides make or miss.

All thresholds, timing windows, and difficulty profiles live in
`config.py` and are deliberately forgiving — this is a demo, not a
shooting clinic.

## Project structure

```
clutch-shot/
├── main.py                # entry point: game loop + --vision-check mode
├── config.py              # every tunable constant & difficulty profile
├── requirements.txt
├── game/
│   ├── game_manager.py    # clock, score, deception, move resolution
│   ├── defender.py        # the live DefenderAI state machine
│   ├── scoring.py         # probability, points, fatigue
│   └── ui.py              # webcam + court scene + HUD + overlays
├── vision/
│   ├── pose_tracker.py    # MediaPipe Pose wrapper
│   ├── biomechanics.py    # angle / movement math (pure functions)
│   └── motion_detector.py # per-frame five-move classifier
└── tests/
    ├── test_biomechanics.py    # angle/midpoint/tilt math
    ├── test_motion_detector.py # all five moves + combo chains
    └── test_scoring.py         # probability, defender AI, fatigue
```

## Limitations

- Single player only; a second person in frame can confuse tracking.
- Needs decent lighting and your upper body + hands in view.
- The stepback uses shoulder width as a depth proxy, so turning fully
  sideways can read as moving backwards.
- No actual ball tracking; the game reads your body, not a real ball.

## Future improvements

- Ball detection for real make/miss verification
- Crossover detection (hand-to-hand dribbles)
- Defender steal attempts on lazy dribbles
- Local high-score persistence
- Sound effects and crowd reactions

## Portfolio value

This project demonstrates real-time computer vision (MediaPipe pose
estimation), low-latency gesture classification with per-frame rules,
a reactive game AI driven by transparent probabilities, clean modular
architecture with headless unit tests, and Pygame UI work — all running
locally with no cloud dependencies.

## Technology stack

| Tool | Role |
|---|---|
| Python 3.11+ | language |
| OpenCV | webcam capture & image handling |
| MediaPipe Pose | body landmark detection |
| Pygame | game window, UI, input |
| NumPy | numeric helpers |
| pytest | unit testing |
