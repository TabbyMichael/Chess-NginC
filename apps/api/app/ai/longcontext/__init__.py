"""Long-context layer: the whole stored review of one game as the answer corpus.

A single game is small enough to hand to a model (or to the deterministic
composer) in full, so this path does not *retrieve* — it reads every graded ply
and lets the question pick. What-if lines add a bounded live engine pass on top.
"""
