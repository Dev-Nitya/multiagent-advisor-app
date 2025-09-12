import logging
from decimal import Decimal
from typing import Dict, Any

from config.database import get_db
from config.cost_limits import OPENAI_PRICING
from models.agent_costs import ModelPricing

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def _normalize_pricing(entry: Dict[str, Any]) -> Dict[str, Decimal]:
    """
    Accepts various key names (input_cost_per_1k / input_usd_per_1k etc.)
    and returns normalized Decimal values for input/output per 1k tokens.
    """
    in_keys = ("input_usd_per_1k", "input_cost_per_1k", "input_per_1k")
    out_keys = ("output_usd_per_1k", "output_cost_per_1k", "output_per_1k")
    input_val = None
    output_val = None
    for k in in_keys:
        if k in entry:
            input_val = entry[k]
            break
    for k in out_keys:
        if k in entry:
            output_val = entry[k]
            break
    # Fallback to 0.0 if not found
    input_val = input_val if input_val is not None else 0
    output_val = output_val if output_val is not None else 0
    return {"input_usd_per_1k": input_val, "output_usd_per_1k": output_val}


def seed_model_pricing(overwrite: bool = True) -> None:
    """
    Insert or update ModelPricing rows from OPENAI_PRICING.
    If overwrite=False existing rows will be left unchanged.
    """
    logger.info("Seeding model_pricing from OPENAI_PRICING (%d models)", len(OPENAI_PRICING))
    db = next(get_db())
    for model_name, entry in OPENAI_PRICING.items():
        try:
            normalized = _normalize_pricing(entry)
            row = db.query(ModelPricing).filter(ModelPricing.model_name == model_name).first()
            if row is None:
                row = ModelPricing(
                    model_name=model_name,
                    input_usd_per_1k=normalized["input_usd_per_1k"],
                    output_usd_per_1k=normalized["output_usd_per_1k"]
                )
                db.add(row)
                db.commit()
                logger.info("Inserted pricing for model=%s", model_name)
            else:
                if overwrite:
                    row.input_usd_per_1k = normalized["input_usd_per_1k"]
                    row.output_usd_per_1k = normalized["output_usd_per_1k"]
                    db.commit()
                    logger.info("Updated pricing for model=%s", model_name)
                else:
                    logger.info("Skipping existing pricing for model=%s (overwrite=False)", model_name)
        except Exception:
            logger.exception("Failed to seed pricing for model=%s", model_name)


seed_model_pricing(overwrite=True)
logger.info("Model pricing seed complete.")