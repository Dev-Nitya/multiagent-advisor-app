from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Body, Query
import logging

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from models.prompt import Prompt
from config.database import get_db
from models.agent_costs import CostEvent

cost_router = APIRouter()
logger = logging.getLogger(__name__)

@cost_router.get('/cost-by-model', summary="Get cost breakdown by model")
async def get_cost_by_model(user_id: str = Query(..., description="User id to filter costs"), db: Session = Depends(get_db)):
    try:
        q = (
            db.query(
                CostEvent.model_name.label("model_name"),
                CostEvent.provider.label("provider"),
                func.count(CostEvent.id).label("event_count"),
                func.coalesce(func.sum(CostEvent.cost_snapshot_usd), 0).label("total_spent_usd"),
                func.coalesce(func.avg(CostEvent.cost_snapshot_usd), 0).label("avg_spent_usd"),
                func.coalesce(func.sum(CostEvent.prompt_tokens), 0).label("prompt_tokens"),
                func.coalesce(func.sum(CostEvent.completion_tokens), 0).label("completion_tokens"),
            )
            .filter(CostEvent.provider == 'openai')
            .filter(CostEvent.user_id == user_id)
            .group_by(CostEvent.model_name, CostEvent.provider)
            .order_by(func.coalesce(func.sum(CostEvent.cost_snapshot_usd), 0).desc())
        )
        rows = q.all()
        result = []
        for r in rows:
            result.append({
                "model_name": r.model_name,
                "provider": r.provider,
                "event_count": int(r.event_count or 0),
                "total_spent_usd": float(r.total_spent_usd or 0.0),
                "avg_spent_usd": float(r.avg_spent_usd or 0.0),
                "prompt_tokens": int(r.prompt_tokens or 0),
                "completion_tokens": int(r.completion_tokens or 0),
            })
        return result
    except Exception as e:
        logger.error(f"Error getting cost by model: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@cost_router.get('/cost-by-prompt', summary="Get cost breakdown by prompt")
async def aggregated_costs_by_prompt(
    db: Session = Depends(get_db),
    sample_events: int = Query(3, ge=0, le=20, description="Number of recent CostEvent samples to include per prompt (0 to disable)"),
):
    """
    Returns an aggregated list (one entry per prompt version/prompt_id) with:
      - total_runs (count of CostEvent rows for that prompt),
      - total_spent_usd, avg_spent_usd,
      - total/avg prompt & completion tokens,
      - model_settings and primary model/provider shortcut fields,
      - optional `sample_cost_events` (most recent N cost events for that prompt).

    Notes:
      - We treat NULL cost_snapshot_usd as 0 for aggregation (so zero-cost rows are included).
      - CostEvent rows with notes in excluded_notes are ignored.
    """
    try:
        excluded_notes = ["external_search_no_token_info"]

        # match condition for events that should be counted (exclude certain notes)
        match_note_cond = ~CostEvent.note.in_(excluded_notes)

        # Aggregate per prompt (group by Prompt.prompt_id / Prompt.name / Prompt.version / Prompt.model_settings)
        q = (
            db.query(
                Prompt.prompt_id.label("prompt_id"),
                Prompt.name.label("prompt_name"),
                Prompt.version.label("prompt_version"),
                Prompt.model_settings.label("model_settings"),
                # number of runs (CostEvent rows for this prompt, excluding excluded notes)
                func.coalesce(func.sum(case((match_note_cond, 1), else_=0)), 0).label("total_runs"),
                # total cost (treat NULL as 0)
                func.coalesce(func.sum(case((match_note_cond, func.coalesce(CostEvent.cost_snapshot_usd, 0)), else_=0)), 0).label("total_spent_usd"),
                # total tokens
                func.coalesce(func.sum(case((match_note_cond, func.coalesce(CostEvent.prompt_tokens, 0)), else_=0)), 0).label("total_prompt_tokens"),
                func.coalesce(func.sum(case((match_note_cond, func.coalesce(CostEvent.completion_tokens, 0)), else_=0)), 0).label("total_completion_tokens"),
            )
            .outerjoin(CostEvent, Prompt.prompt_id == CostEvent.prompt_id)
            .group_by(Prompt.prompt_id, Prompt.name, Prompt.version, Prompt.model_settings)
            .having(func.coalesce(func.sum(case((match_note_cond, 1), else_=0)), 0) > 0)  # only include prompts that have at least one non-excluded event
            .order_by(func.coalesce(func.sum(case((match_note_cond, func.coalesce(CostEvent.cost_snapshot_usd, 0)), else_=0)), 0).desc())
        )

        rows = q.all()
        result = []

        # helper to fetch sample events per prompt (most recent)
        def _fetch_sample_events(prompt_id: str, limit: int):
            if limit <= 0:
                return []
            events = (
                db.query(
                    CostEvent.id,
                    CostEvent.ts,
                    CostEvent.provider,
                    CostEvent.model_name,
                    CostEvent.cost_snapshot_usd,
                    CostEvent.prompt_tokens,
                    CostEvent.completion_tokens,
                    CostEvent.note,
                )
                .filter(
                    CostEvent.prompt_id == prompt_id,
                    match_note_cond
                )
                .order_by(CostEvent.ts.desc())
                .limit(limit)
                .all()
            )
            out = []
            for ev in events:
                out.append({
                    "id": ev.id,
                    "ts": getattr(ev, "ts", None),
                    "provider": ev.provider,
                    "model_name": ev.model_name,
                    "cost_snapshot_usd": float(ev.cost_snapshot_usd or 0.0),
                    "prompt_tokens": int(ev.prompt_tokens or 0),
                    "completion_tokens": int(ev.completion_tokens or 0),
                    "note": ev.note,
                })
            return out

        for r in rows:
            total_runs = int(r.total_runs or 0)
            total_spent = float(r.total_spent_usd or 0.0)
            total_prompt_tokens = int(r.total_prompt_tokens or 0)
            total_completion_tokens = int(r.total_completion_tokens or 0)

            avg_spent = float(total_spent / total_runs) if total_runs > 0 else 0.0
            avg_prompt_tokens = int(total_prompt_tokens / total_runs) if total_runs > 0 else 0
            avg_completion_tokens = int(total_completion_tokens / total_runs) if total_runs > 0 else 0

            model_settings = r.model_settings or {}
            result.append({
                "prompt_id": r.prompt_id,
                "prompt_name": r.prompt_name,
                "prompt_version": r.prompt_version,
                "total_runs": total_runs,
                "total_spent_usd": total_spent,
                "avg_spent_usd": avg_spent,
                "total_prompt_tokens": total_prompt_tokens,
                "avg_prompt_tokens": avg_prompt_tokens,
                "total_completion_tokens": total_completion_tokens,
                "avg_completion_tokens": avg_completion_tokens,
                "model_name": model_settings.get("model_name"),
                "provider": model_settings.get("provider"),
                "model_settings": model_settings,
                "sample_cost_events": _fetch_sample_events(r.prompt_id, sample_events),
            })

        return result

    except Exception as e:
        logger.error(f"Error aggregating costs by prompt: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")