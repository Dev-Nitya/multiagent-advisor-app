import logging
from typing import Optional

from sqlalchemy import or_

from config.database import get_db
from models.agent_costs import CostEvent
from services.cost_service import compute_cost

logger = logging.getLogger(__name__)

TARGET_MODEL = "gpt-3.5-turbo"
MATCH_MODELS = (None, "", "gpt-4", "gpt-3.5-turbo-0125")

def _estimate_split(total_tokens: int) -> tuple[int, int]:
    prompt = int(round(total_tokens * 0.85))
    completion = total_tokens - prompt
    return prompt, completion

def run_script(batch_size: int = 200):
    db = next(get_db())
    updated = 0
    failed = 0
    try:
        q = db.query(CostEvent).filter(
            or_(
                CostEvent.model_name == None,
                CostEvent.model_name == "",
                CostEvent.model_name == "gpt-4",
                CostEvent.model_name == "gpt-3.5-turbo-0125",
            )
        )

        total = q.count()
        print(f"Found {total} cost_event rows to update (model_name NULL/empty or 'gpt-4').")
        if total == 0:
            return

        # iterate and update in batches
        offset = 0
        while True:
            rows = q.limit(batch_size).offset(offset).all()
            if not rows:
                break
            for r in rows:
                try:
                    # determine tokens to use for pricing
                    prompt_tokens = r.prompt_tokens
                    completion_tokens = r.completion_tokens
                    if (prompt_tokens is None or completion_tokens is None) and getattr(r, "total_tokens", None) is not None:
                        prompt_tokens, completion_tokens = _estimate_split(int(r.total_tokens))
                    # safe defaults
                    prompt_tokens = int(prompt_tokens or 0)
                    completion_tokens = int(completion_tokens or 0)

                    cost_usd: Optional[float] = compute_cost(TARGET_MODEL, prompt_tokens, completion_tokens)
                    if cost_usd is None:
                        # pricing not found; log and set 0.0
                        logger.warning(f"Pricing missing for model {TARGET_MODEL}; setting cost_snapshot_usd=0 for event id={r.id}")
                        cost_val = 0.0
                    else:
                        cost_val = float(cost_usd)

                    r.model_name = TARGET_MODEL
                    r.cost_snapshot_usd = cost_val

                    db.add(r)
                    updated += 1
                except Exception as ex:
                    logger.exception("Failed to update cost_event id=%s", getattr(r, "id", None))
                    failed += 1

            db.commit()
            offset += batch_size

        print(f"Update complete. rows_updated={updated}, rows_failed={failed}")
    finally:
        try:
            db.close()
        except Exception:
            pass

run_script()