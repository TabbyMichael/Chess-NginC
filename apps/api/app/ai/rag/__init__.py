"""RAG layer: recall across the player's *own* games with Postgres full-text.

Long context answers "what happened in this game"; this layer answers the
cross-game questions — "what do I keep doing wrong" and "what opening theory
applies here" — over every review the player has stored.

Deliberately embedding-free (see docs/architecture.md): a plain `tsvector` +
GIN index plus the offline opening book, so no new dependency, no extension and
no change to the offline test/CI guarantees. Recall is best-effort and never
raises into an answer path.
"""
