"""Long-context facts and the deterministic composer / grounding guard (Phase 11).

Pure unit tests over a stored review payload — no database, no engine, no network
— which is exactly the offline contract the assistant is built on: every answer
must be derivable from the facts alone.
"""

from app.ai.compose import (
    Intent,
    allowed_tokens_from,
    compose,
    detect_intent,
    grounded,
)
from app.ai.longcontext.context import (
    eval_text,
    facts_from_payload,
    find_focus_ply,
    full_review_pack,
    material_imbalance,
    retrieval_pack,
    san_for_uci,
)
from app.games.domain import STARTING_FEN

AFTER_E4 = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"


def _payload() -> list[dict]:
    return [
        {
            "ply": 1,
            "move_number": 1,
            "uci": "e2e4",
            "san": "e4",
            "pre_fen": STARTING_FEN,
            "color": "w",
            "quality": "best",
            "centipawn_loss": 0,
            "best_uci": "e2e4",
            "eval_cp": 20,
            "eval_mate": None,
            "explanation": "e4 is exactly what the engine wants.",
        },
        {
            "ply": 2,
            "move_number": 1,
            "uci": "e7e5",
            "san": "e5",
            "pre_fen": AFTER_E4,
            "color": "b",
            "quality": "blunder",
            "centipawn_loss": 300,
            "best_uci": "c7c5",
            "eval_cp": -20,
            "eval_mate": None,
            "explanation": "e5 walks into the attack.",
        },
    ]


def test_facts_convert_and_derive_opening_family() -> None:
    facts = facts_from_payload(_payload())
    assert [f.san for f in facts] == ["e4", "e5"]
    # Opening is derived on read from the offline book (never stored in the payload).
    assert facts[1].opening_family == "King's Pawn Game"


def test_facts_skip_malformed_entries() -> None:
    facts = facts_from_payload([{"san": "", "ply": 1}, {"ply": None, "san": "x"}, 7])
    assert facts == []


def test_eval_text_mate_beats_centipawns() -> None:
    assert eval_text(150, None) == "+1.50"
    assert eval_text(0, 3) == "mate in 3"
    assert eval_text(0, -2) == "mate in 2"


def test_material_imbalance_reads_white_minus_black() -> None:
    assert material_imbalance(STARTING_FEN) == 0
    # White is up a queen (900) on an otherwise empty board.
    assert material_imbalance("4k3/8/8/8/8/8/8/3QK3 w - - 0 1") == 900


def test_san_for_uci_recovers_best_move_and_rejects_illegal() -> None:
    assert san_for_uci(STARTING_FEN, "e2e4") == "e4"
    assert san_for_uci(STARTING_FEN, "e2e5") == ""  # not a legal king-pawn push
    assert san_for_uci("nonsense", "e2e4") == ""


def test_find_focus_explicit_then_question_then_worst_own() -> None:
    facts = facts_from_payload(_payload())
    assert find_focus_ply(facts, 1, "b", "anything") == 1  # explicit cursor wins
    assert find_focus_ply(facts, None, "b", "tell me about e4") == 1  # SAN in text
    assert find_focus_ply(facts, None, "b", "how did it go") == 2  # hero's worst own error
    assert find_focus_ply([], None, "w", "hello") is None


def test_full_review_pack_marks_the_hero_and_bounded() -> None:
    facts = facts_from_payload(_payload())
    text, included = full_review_pack(facts, "w")
    assert len(included) == 2
    assert "White e4 *" in text  # hero is starred
    assert "best was e4" in text  # the engine line is spelled in SAN
    text2, inc2 = full_review_pack(facts, "w", max_plies=1)
    assert len(inc2) == 1 and "Black e5" not in text2


def test_retrieval_pack_windows_around_focus() -> None:
    facts = facts_from_payload(_payload())
    text, refs = retrieval_pack(facts, 1, "w")
    assert "e4" in text and len(refs) >= 1


# --- composer -----------------------------------------------------------------


def test_detect_intent_routes_the_core_questions() -> None:
    assert detect_intent("what do I keep doing wrong across my games?") is Intent.PATTERNS
    assert detect_intent("what opening theory applies here?") is Intent.OPENING
    assert detect_intent("what else could have gone here instead?") is Intent.ALTERNATIVES
    assert detect_intent("describe the material on the board") is Intent.POSITION
    assert detect_intent("what is the best way to proceed?") is Intent.PLAN
    assert detect_intent("why was that a mistake?") is Intent.EXPLAIN
    assert detect_intent("how did the overall game go?") is Intent.SUMMARY
    assert detect_intent("hello there") is Intent.GENERAL


def test_detect_intent_routes_the_conversational_asks() -> None:
    # Phase 11b: the new ways to lean on the coach still resolve cleanly.
    assert detect_intent("show me the line") is Intent.LESSON
    assert detect_intent("walk me through the main line") is Intent.LESSON
    assert detect_intent("why is that better?") is Intent.WHY
    assert detect_intent("what is the idea here?") is Intent.IDEA


def test_compose_is_grounded_and_cites_references() -> None:
    facts = facts_from_payload(_payload())
    focus = facts[1]
    composed = compose(Intent.EXPLAIN, focus, facts, "b", game_id=42)
    assert composed.answer  # non-empty prose
    assert composed.references and composed.references[0].game_id == 42
    assert "e5" in composed.answer
    # A cited SAN always traces to a stored fact.
    assert all(ref.san in {f.san for f in facts} for ref in composed.references)


def test_compose_summary_reports_hero_error() -> None:
    facts = facts_from_payload(_payload())
    composed = compose(Intent.SUMMARY, None, facts, "b")
    assert "e5" in composed.answer
    assert "300 cp" in composed.answer


def test_compose_alternatives_without_engine_declines_to_guess() -> None:
    facts = facts_from_payload(_payload())
    composed = compose(Intent.ALTERNATIVES, facts[1], facts, "b", lines=[])
    assert "no live engine line" in composed.answer


def test_compose_plan_is_multi_section_and_carries_a_walkable_line() -> None:
    facts = facts_from_payload(_payload())
    composed = compose(Intent.PLAN, facts[1], facts, "b", game_id=42)
    # The recommendation is spelled out in sections, and a line rides along.
    assert "Recommendation:" in composed.answer
    assert "The line:" in composed.answer
    assert composed.line and composed.line[0].san == "e5"
    assert composed.line_title


def test_compose_lesson_walks_the_recorded_variation() -> None:
    facts = facts_from_payload(_payload())
    composed = compose(Intent.LESSON, facts[1], facts, "b")
    assert "walk" in composed.answer.lower()
    assert composed.line and composed.line[0].san == "e5"


def test_compose_recall_fallback_when_nothing_indexed() -> None:
    facts = facts_from_payload(_payload())
    composed = compose(Intent.PATTERNS, None, facts, "b", recall_block="")
    assert "cross-game history" in composed.answer


# --- cite-only grounding guard -------------------------------------------------


def test_grounding_rejects_an_invented_move() -> None:
    facts = facts_from_payload(_payload())
    allowed = allowed_tokens_from(facts)
    assert not grounded("Here Qh7# wins the game.", allowed)


def test_grounding_accepts_moves_it_was_given() -> None:
    facts = facts_from_payload(_payload())
    allowed = allowed_tokens_from(facts)
    assert grounded("You should answer with c5 here.", allowed)
    assert grounded("The engine wanted e5.", allowed)  # best_uci SAN is in the set


def test_grounding_leaves_plain_prose_unconstrained() -> None:
    assert grounded("Your pawn structure was loose.", {"e4"})
    assert not grounded("", {"e4"})  # empty output is never a usable answer
