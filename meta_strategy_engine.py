from debug_runtime import read_debug_snapshot
from evolution_engine import upsert_rule
from intelligence_metrics import get_recent_metric_summary


def run_meta_strategy_adjustments():
    snapshot = read_debug_snapshot()
    summary = get_recent_metric_summary(limit=12)
    created = []

    if summary.get("average_engagement", 0.0) < 0.5:
        created.append(
            upsert_rule(
                "engagement_compaction",
                "When engagement trends low, prefer sharper and shorter answers before expanding.",
                weight=0.83,
                source="meta_strategy",
            )
        )
    if summary.get("clarify_rate", 0.0) > 0.25:
        created.append(
            upsert_rule(
                "clarify_is_working",
                "Use clarifying questions for ambiguous high-impact decisions more often.",
                weight=0.79,
                source="meta_strategy",
            )
        )
    if (snapshot.get("complexity") or "").strip().lower() == "simple" and len((snapshot.get("final_answer") or "").split()) > 110:
        created.append(
            upsert_rule(
                "simple_prompts_need_compaction",
                "For simple prompts, compress the answer instead of over-explaining.",
                weight=0.85,
                source="self_debug",
            )
        )
    return created
