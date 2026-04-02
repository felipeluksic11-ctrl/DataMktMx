"""API usage tracker — logs every Anthropic call with tokens and cost.

Stores accumulated usage in PostgreSQL (shared with API container).
Dashboard reads via GET /data/ai-usage.

Pricing (as of 2026):
- Haiku 4.5:  $0.80/M input,  $4/M output
- Sonnet 4.6: $3/M input,    $15/M output
- Opus 4.6:   $15/M input,   $75/M output

Cost estimates per operation:
- Spot check (Haiku + screenshot): ~$0.002
- Visual repair (Sonnet + screenshot): ~$0.02
- Full analysis (Sonnet + screenshot): ~$0.025
"""

import json
import asyncio
import datetime

from sqlalchemy import text

from shared.config import settings
from shared.db.session import get_session_factory
from shared.logging import get_logger

logger = get_logger("supervisor.usage")

PRICING = {
    "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.00},
    "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
    "claude-opus-4-20250514": {"input": 15.00, "output": 75.00},
}


def track_usage(
    model: str,
    input_tokens: int,
    output_tokens: int,
    purpose: str = "general",
) -> dict:
    """Record an API call. Writes to DB asynchronously.

    Returns cost info for this call.
    """
    pricing = PRICING.get(model, {"input": 3.0, "output": 15.0})
    cost = (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000

    logger.info(
        "usage.tracked",
        model=model,
        purpose=purpose,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=round(cost, 6),
    )

    # Fire-and-forget DB write
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(_persist_usage(model, input_tokens, output_tokens, cost, purpose))
        else:
            asyncio.run(_persist_usage(model, input_tokens, output_tokens, cost, purpose))
    except Exception:
        logger.exception("usage.persist_error")

    return {"cost": cost, "input_tokens": input_tokens, "output_tokens": output_tokens}


async def _persist_usage(
    model: str, input_tokens: int, output_tokens: int, cost: float, purpose: str
) -> None:
    """Write usage to PostgreSQL ai_usage table."""
    session_factory = get_session_factory()
    today = datetime.date.today().isoformat()

    async with session_factory() as session:
        # Ensure table exists
        await session.execute(text("""
            CREATE TABLE IF NOT EXISTS public.ai_usage (
                id SERIAL PRIMARY KEY,
                total_calls INTEGER DEFAULT 0,
                total_input_tokens BIGINT DEFAULT 0,
                total_output_tokens BIGINT DEFAULT 0,
                total_cost_usd DOUBLE PRECISION DEFAULT 0,
                today_date DATE DEFAULT CURRENT_DATE,
                today_cost_usd DOUBLE PRECISION DEFAULT 0,
                by_purpose JSONB DEFAULT '{}',
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """))

        # Get or create the single summary row
        result = await session.execute(text("SELECT id, today_date, by_purpose FROM public.ai_usage LIMIT 1"))
        row = result.mappings().first()

        if row:
            by_purpose = dict(row["by_purpose"] or {})
            if purpose not in by_purpose:
                by_purpose[purpose] = {"calls": 0, "cost": 0.0}
            by_purpose[purpose]["calls"] += 1
            by_purpose[purpose]["cost"] = round(by_purpose[purpose]["cost"] + cost, 6)

            # Reset today_cost if new day
            reset_today = "today_cost_usd = :cost" if str(row["today_date"]) != today else "today_cost_usd = today_cost_usd + :cost"

            await session.execute(text(f"""
                UPDATE public.ai_usage SET
                    total_calls = total_calls + 1,
                    total_input_tokens = total_input_tokens + :input_tokens,
                    total_output_tokens = total_output_tokens + :output_tokens,
                    total_cost_usd = total_cost_usd + :cost,
                    today_date = CURRENT_DATE,
                    {reset_today},
                    by_purpose = :by_purpose::jsonb,
                    updated_at = NOW()
                WHERE id = :id
            """), {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost": cost,
                "by_purpose": json.dumps(by_purpose),
                "id": row["id"],
            })
        else:
            by_purpose = {purpose: {"calls": 1, "cost": round(cost, 6)}}
            await session.execute(text("""
                INSERT INTO public.ai_usage (total_calls, total_input_tokens, total_output_tokens, total_cost_usd, today_cost_usd, by_purpose)
                VALUES (1, :input_tokens, :output_tokens, :cost, :cost, :by_purpose::jsonb)
            """), {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost": cost,
                "by_purpose": json.dumps(by_purpose),
            })

        await session.commit()
