"""Coach assistant: engine-grounded conversation over a player's own games.

Two retrieval paths feed one answer (see docs/architecture.md):

* **Long context** reads the *whole stored review of the current game* — a few
  thousand tokens of ground truth (grades, evals, best lines, coaching notes) —
  and adds a *bounded live Stockfish* pass for "other ways this could have gone".
* **RAG** recalls *across the player's games* with Postgres full-text search plus
  the offline opening book — what the player keeps getting wrong, and the theory
  names for the positions they reached.

Nothing here invents a chess fact: every move, evaluation and opening cited is
either a stored engine fact, a fresh engine line, or a book name. An optional LLM
may only *rearrange* those facts (cite-only grounding guard) or the deterministic
composer answers instead.
"""
