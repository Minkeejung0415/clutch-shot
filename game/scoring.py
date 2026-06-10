"""
Scoring, form score, shot probability and fatigue (PHASE 4+ - not yet
implemented).

Will implement:
- form score 0-100 from the weighted factors in config (FORM_WEIGHT_*)
- final shot probability: base + form bonus + pressure modifier
  - fatigue penalty + fake bonus, clamped to
  [MIN_SHOT_PROBABILITY, MAX_SHOT_PROBABILITY]
- the 0-100 fatigue meter (rises per attempt, recovers over time)
"""
