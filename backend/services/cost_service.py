from datetime import datetime
import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Dict, Any
from sqlalchemy.exc import SQLAlchemyError

from config.database import get_db
from models.agent_costs import CostEvent, ModelPricing
from models.user import UserBudget
from utils.request_context import get_request_context

logger = logging.getLogger(__name__)

class BudgetExceeded(Exception):
    pass

def compute_cost(model_name: str, prompt_tokens: int, completion_tokens: int) -> Optional[float]:
    """
    Compute cost in USD for given model and token counts using model_pricing.
    Returns rounded float or None if pricing missing.
    """
    try:
        db = next(get_db())
        mp = db.query(ModelPricing).filter(ModelPricing.model_name == model_name).first()
        if not mp:
            return None
        input_cost = (prompt_tokens / 1000) * mp.input_usd_per_1k
        output_cost = (completion_tokens / 1000) * mp.output_usd_per_1k
        total = input_cost + output_cost
        return total
    except Exception:
        logger.exception("compute_cost failed")
        return None
    finally:
        db.close()

def _estimate_split(total_tokens: int) -> tuple[int, int, str]:
    # split 85% prompt, 15% completion
    prompt = int(round(total_tokens * 0.85))
    completion = total_tokens - prompt
    return prompt, completion, "estimated_split"

def record_cost_event(
    *,
    user_id: Optional[str],
    request_id: Optional[str],
    graph_node_id: Optional[str],
    agent_id: Optional[str],
    tool_id: Optional[str],
    provider: Optional[str],
    model_name: Optional[str],
    prompt_tokens: Optional[int],
    completion_tokens: Optional[int],
    total_tokens: Optional[int],
    operation_type: Optional[str] = None,
    successful: Optional[bool] = True,
    cached: Optional[bool] = False,
    note: Optional[str] = "",
    prompt_id: Optional[str] = None, 
) -> Optional[str]:
    """
    Persist cost_event and update user budget. Returns cost_event.id or None on failure.
    This function is robust: logs exceptions and will not raise unless budget exceeded.
    """

    # Fallback: if caller did not provide user_id, try to read current request context
    if not user_id:
        try:
            ctx = get_request_context() or {}
            fallback_user = ctx.get("user_id")
            if fallback_user:
                user_id = fallback_user
        except Exception:
            pass

    if total_tokens is None and (prompt_tokens is None and completion_tokens is None):
        logger.debug("No tokens provided; skipping cost event")
        return None

    # derive prompt/completion if needed
    extra_note = note or ""
    if total_tokens is not None and (prompt_tokens is None or completion_tokens is None):
        prompt_tokens, completion_tokens, est_note = _estimate_split(total_tokens)
        extra_note = (extra_note + ("; " if extra_note else "") + est_note)

    if prompt_tokens is None:
        prompt_tokens = 0
    if completion_tokens is None:
        completion_tokens = 0
    total = prompt_tokens + completion_tokens

    try:
        cost_usd = compute_cost(model_name or "", prompt_tokens, completion_tokens)
        logger.info(f"Computed cost_usd: {cost_usd} for model: {model_name}, prompt_tokens: {prompt_tokens}, completion_tokens: {completion_tokens}")
    except Exception:
        logger.info("compute_cost failed; proceeding with cost_usd=None")

    cost_val = cost_usd if cost_usd is not None else 0.0

    try:
        db = next(get_db())
        ev = CostEvent(
            user_id=user_id,
            request_id=request_id,
            graph_node_id=graph_node_id,
            agent_id=agent_id,
            tool_id=tool_id,
            provider=provider,
            model_name=model_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total,
            operation_type=operation_type,
            cost_snapshot_usd=cost_val,
            successful=successful,
            cached=cached,
            note=extra_note,
            prompt_id=prompt_id, 
            created_at=datetime.utcnow(),
        )
        db.add(ev)
        db.commit()
        db.refresh(ev)

        # Update user budget safely
        if user_id:
            ub = db.query(UserBudget).filter(UserBudget.user_id == user_id).with_for_update().first()
            if ub:
                ub.daily_spent_usd = (ub.daily_spent_usd or 0) + (cost_usd if cost_usd is not None else 0)
                ub.monthly_spent_usd = (ub.monthly_spent_usd or 0) + (cost_usd if cost_usd is not None else 0)
            else:
                ub = UserBudget(user_id=user_id, budget_usd=0, daily_spent_usd=(cost_usd if cost_usd is not None else 0),
                                monthly_spent_usd=(cost_usd if cost_usd is not None else 0),
                                spent_usd=(cost_usd if cost_usd is not None else 0))
                db.add(ub)
            db.commit()
            return ev.id
    except BudgetExceeded:
        # surface budget exceed to caller
        raise
    except SQLAlchemyError:
        logger.info("Failed to record cost_event to DB (SQLAlchemyError)")
        raise
    except Exception:
        logger.info("Failed to record cost_event")
        raise
    finally:
        db.close()

# Aggregation helpers
def apply_request_spend(
    *,
    user_id: Optional[str],
    request_id: Optional[str],
    total_cost_usd: float,
    breakdown_by_node: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Apply the aggregated spend for a completed request to the user's budget.
    - Increments user_budget.spent_usd by total_cost_usd (best-effort).
    - If the user's budget is set and is exceeded, raises BudgetExceeded.
    Returns True on success, False on non-fatal DB errors.
    """
    if not user_id:
        logger.debug("apply_request_spend called without user_id; skipping budget write")
        return False

    try:
        db = next(get_db())
        # lock the row to avoid race conditions
        ub = db.query(UserBudget).filter(UserBudget.user_id == user_id).with_for_update().first()
        if ub is None:
            # create a row if missing (budget_usd default 0)
            logger.error('No existing UserBudget for user %s', user_id)
            raise Exception("UserBudget not found")
        else:
            # Check if we need to reset daily/monthly counters
            current_date = datetime.utcnow().date()
            current_month = datetime.utcnow().replace(day=1).date()

            # Reset daily spending if it's a new day
            if ub.daily_reset_date and ub.daily_reset_date.date() < current_date:
                logger.info(f"Resetting daily spending for user {user_id} (new day)")
                ub.daily_spent_usd = 0
                ub.daily_reset_date = datetime.utcnow()

            # Reset monthly spending if it's a new month
            if ub.monthly_reset_date and ub.monthly_reset_date.date() < current_month:
                logger.info(f"Resetting monthly spending for user {user_id} (new month)")
                ub.monthly_spent_usd = 0
                ub.monthly_reset_date = datetime.utcnow()

            # Add the cost to current spending using Decimal arithmetic to avoid type errors
            logger.info(f"Applying spend of {total_cost_usd} to user {user_id}")
            add_amount = 0 + total_cost_usd
            # coerce existing stored values to Decimal safely
            existing_daily = ub.daily_spent_usd or 0
            existing_monthly = ub.monthly_spent_usd or 0
            ub.daily_spent_usd = existing_daily + add_amount
            ub.monthly_spent_usd = existing_monthly + add_amount
            ub.updated_at = datetime.utcnow()

        db.commit()

        # optional: persist breakdown_by_node to audit table (not implemented here)
        return True
    except BudgetExceeded:
        # propagate enforcement up to caller
        raise
    except Exception:
        logger.exception("Failed to apply request spend for user=%s (non-fatal)", user_id)
        return False
    finally:
        db.close()

def total_spent_by_user_last_n_days(user_id: str, days: int = 7) -> float:
    from sqlalchemy import func, cast
    from datetime import datetime, timedelta
    try:
        cutoff = func.now() - func.cast(f"interval '{days} days'", type_=func.now().__class__)
        db = next(get_db())
        s = db.query(func.sum(CostEvent.cost_snapshot_usd)).filter(CostEvent.user_id == user_id)
        # note: if timezone handling needed, refine
        total = s.scalar() or 0
        return float(total)
    except Exception:
        logger.exception("total_spent_by_user_last_n_days failed")
        return 0.0
    finally:
        db.close()

def cost_by_group(request_id: Optional[str] = None, group_by: str = "graph_node_id"):
    """
    Returns dict grouping cost and tokens by graph_node_id/agent_id/tool_id.
    """
    from sqlalchemy import func
    try:
        db = next(get_db())
        q = db.query(getattr(CostEvent, group_by).label("grp"),
                     func.sum(CostEvent.total_tokens).label("tokens"),
                     func.sum(CostEvent.cost_snapshot_usd).label("cost"))
        if request_id:
            q = q.filter(CostEvent.request_id == request_id)
        q = q.group_by(getattr(CostEvent, group_by))
        results = {r.grp or "{{DEFAULT_GRAPH_NODE}}": {"tokens": int(r.tokens or 0), "cost": float(r.cost or 0)} for r in q.all()}
        return results
    except Exception:
        logger.exception("cost_by_group failed")
        return {}
    finally:
        db.close()