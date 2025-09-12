"""
Minimal seeding script to create initial Prompt rows for your agents.

Usage (from repo root):
    python backend/scripts/seed_prompts.py [--purge]

--purge : delete all existing prompts before seeding
"""
import json
import hashlib
from datetime import datetime
import uuid
import sys
import argparse

# Adjust imports if your project uses different paths for DB/Models
from config.database import get_db
from models.prompt import Prompt

def _compute_hash(prompt_text: str, model_settings: dict | None) -> str:
    payload = {"prompt_text": prompt_text or "", "model_settings": model_settings or {}}
    j = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(j.encode("utf-8")).hexdigest()

def purge_prompts(db):
    try:
        deleted = db.query(Prompt).delete()
        db.commit()
        print(f"[purged] Deleted {deleted} existing prompt rows")
    except Exception as e:
        db.rollback()
        print(f"[error] Failed to purge prompts: {e}", file=sys.stderr)
        raise

def seed_prompt(
    db,
    *,
    name: str,
    prompt_text: str,
    model_settings: dict | None = None,
    output_schema: dict | None = None,
    author: str = "seed-script",
    changelog: str | None = "initial seed from inline defaults",
) -> str:
    try:
        h = _compute_hash(prompt_text, model_settings)
        existing = db.query(Prompt).filter(Prompt.hash == h).one_or_none()
        if existing:
            print(f"[skip] Identical prompt already exists: name={name} prompt_id={existing.prompt_id} v{existing.version}")
            return existing.prompt_id

        # compute next version for this name
        last = db.query(Prompt).filter(Prompt.name == name).order_by(Prompt.version.desc()).first()
        next_version = (last.version + 1) if last else 1

        p = Prompt(
            prompt_id=str(uuid.uuid4()),
            name=name,
            version=next_version,
            prompt_text=prompt_text,
            model_settings=model_settings,
            output_schema=output_schema,
            hash=h,
            author=author,
            changelog=changelog,
            created_at=datetime.utcnow(),
        )
        db.add(p)
        db.commit()
        db.refresh(p)
        print(f"[created] {name} prompt_id={p.prompt_id} v{p.version}")
        return p.prompt_id
    except Exception as e:
        print(f"[error] Failed to seed prompt name={name}: {e}", file=sys.stderr)
        raise

def run_script(purge: bool = False):
    # (prompt definitions omitted here for brevity — keep same definitions as before)
    # Summary agent (final synthesizer)
    summary_prompt_text = (
        "SYSTEM:\n"
        "You are a senior startup advisor. Goal: Review all agent outputs (market, financial, product) and deliver a concise final verdict.\n\n"
        "BACKSTORY:\n"
        "You have experience evaluating startup viability across markets, finance, and product design. Synthesize expert inputs and provide clear, actionable guidance.\n\n"
        "INSTRUCTIONS:\n"
        "- Do NOT delegate further work.\n"
        "- Produce a strict JSON object matching the expected schema exactly (no extra fields, no surrounding text).\n"
        "- final_recommendation must be one of: \"launch\", \"iterate\", or \"abandon\".\n"
        "- rationale: 2-3 concise sentences combining core evidence from the other agents.\n"
        "- confidence_score: integer 0-10.\n"
        "- Keep responses concise to reduce tokens; avoid long prose.\n"
    )
    summary_output_schema = {
        "market_verdict": "Short verdict from market analysis (one sentence)",
        "financial_verdict": "Short verdict from financial analysis (one sentence)",
        "product_verdict": "Short verdict from product analysis (one sentence)",
        "final_recommendation": "launch | iterate | abandon",
        "rationale": "2-3 sentence combined rationale",
        "confidence_score": "0-10 integer"
    }
    summary_model_settings = {"provider": "openai", "model_name": "gpt-4", "temperature": 0.0, "max_tokens": 400}

    # Market research agent - concise, evidence-first outputs
    market_research_prompt = (
        "SYSTEM:\n"
        "You are a Market Research analyst. Goal: For a given startup idea, produce concise numeric estimates and crisp verdicts.\n\n"
        "INSTRUCTIONS:\n"
        "- Return a compact JSON object (no extra prose) with keys: market_size_estimate_usd, top_competitors (list), differentiation, demand_drivers, confidence.\n"
        "- Provide short assumptions (1-2 bullet points) if you make numeric estimates.\n"
        "- Use conservative rounding and avoid long explanations.\n"
    )
    market_output_schema = {
        "market_size_estimate_usd": "number (approximate total addressable market in USD)",
        "top_competitors": "list of competitor names with 1-line note each",
        "differentiation": "1-line statement of product differentiation",
        "demand_drivers": "short list of demand drivers (comma-separated)",
        "confidence": "0-10 integer for confidence in estimates",
        "assumptions": "short list of assumptions"
    }
    market_model_settings = {"provider": "openai", "model_name": "gpt-3.5-turbo", "temperature": 0.15, "max_tokens": 350}

    # Financial advisor agent - structured numeric outputs
    financial_advisor_prompt = (
        "SYSTEM:\n"
        "You are a Financial Advisor. Goal: Produce structured unit-economics and 3-year projection estimates for a startup idea.\n\n"
        "INSTRUCTIONS:\n"
        "- Return a compact JSON object with keys: revenue_year_1, revenue_year_3, gross_margin_pct, monthly_burn, payback_months, key_risks (list).\n"
        "- State short assumptions used for projections (max 3 bullets).\n"
        "- Prioritize concise numeric outputs and avoid long textual reasoning.\n"
    )
    financial_output_schema = {
        "revenue_year_1": "number (USD estimate)",
        "revenue_year_3": "number (USD estimate)",
        "gross_margin_pct": "number (0-100)",
        "monthly_burn": "number (USD)",
        "payback_months": "number",
        "key_risks": "list of short risk descriptions",
        "assumptions": "short list of assumptions"
    }
    financial_model_settings = {"provider": "openai", "model_name": "gpt-4", "temperature": 0.0, "max_tokens": 500}

    # Product strategist agent - prioritized actions for MVP
    product_strategist_prompt = (
        "SYSTEM:\n"
        "You are a Product Strategist. Goal: Evaluate product-market fit and propose an MVP roadmap.\n\n"
        "INSTRUCTIONS:\n"
        "- Return a compact JSON object: core_mvp_features (prioritized list), critical_assumptions (list), metrics_to_measure (list), recommended_next_steps (ordered list).\n"
        "- Keep text short and actionable (1-2 short bullets per item).\n"
    )
    product_output_schema = {
        "core_mvp_features": "prioritized list of features (short phrases)",
        "critical_assumptions": "list of assumptions to validate",
        "metrics_to_measure": "list of key metrics (e.g., DAU, conversion%)",
        "recommended_next_steps": "ordered short action list"
    }
    product_model_settings = {"provider": "openai", "model_name": "gpt-3.5-turbo", "temperature": 0.1, "max_tokens": 400}

    # Open DB session and optionally purge
    db = next(get_db())
    try:
        if purge:
            purge_prompts(db)

        # v1 seeds (detailed / higher-quality)
        seed_prompt(
            db,
            name="summary_agent",
            prompt_text=summary_prompt_text,
            model_settings=summary_model_settings,
            output_schema=summary_output_schema,
            author="seed-script",
            changelog="seed v1: detailed summary agent prompt + gpt-4 for high-quality synthesis"
        )

        seed_prompt(
            db,
            name="market_research",
            prompt_text=market_research_prompt,
            model_settings=market_model_settings,
            output_schema=market_output_schema,
            author="seed-script",
            changelog="seed v1: structured market research prompt"
        )

        seed_prompt(
            db,
            name="financial_advisor",
            prompt_text=financial_advisor_prompt,
            model_settings=financial_model_settings,
            output_schema=financial_output_schema,
            author="seed-script",
            changelog="seed v1: structured financial advisor prompt"
        )

        seed_prompt(
            db,
            name="product_strategist",
            prompt_text=product_strategist_prompt,
            model_settings=product_model_settings,
            output_schema=product_output_schema,
            author="seed-script",
            changelog="seed v1: product strategist prompt"
        )

        # --- v2 seeds: concise / cost-conscious variants ---
        summary_prompt_text_v2 = summary_prompt_text + "\nINSTRUCTIONS: Be more concise; keep rationale to 1 sentence; minimize tokens."
        summary_model_settings_v2 = {"provider": "openai", "model_name": "gpt-3.5-turbo", "temperature": 0.1, "max_tokens": 250}
        seed_prompt(
            db,
            name="summary_agent",
            prompt_text=summary_prompt_text_v2,
            model_settings=summary_model_settings_v2,
            output_schema=summary_output_schema,
            author="seed-script",
            changelog="seed v2: concise output + cheaper model (gpt-3.5) to reduce cost"
        )

        market_research_prompt_v2 = market_research_prompt + "\nINSTRUCTIONS: Keep numeric estimates short and only return top 3 competitors."
        market_model_settings_v2 = {"provider": "openai", "model_name": "gpt-3.5-turbo", "temperature": 0.2, "max_tokens": 200}
        seed_prompt(
            db,
            name="market_research",
            prompt_text=market_research_prompt_v2,
            model_settings=market_model_settings_v2,
            output_schema=market_output_schema,
            author="seed-script",
            changelog="seed v2: concise market research + cheaper model"
        )

        financial_advisor_prompt_v2 = financial_advisor_prompt + "\nINSTRUCTIONS: Provide only the core numeric outputs; keep assumptions to 1 line each."
        financial_model_settings_v2 = {"provider": "openai", "model_name": "gpt-3.5-turbo", "temperature": 0.0, "max_tokens": 300}
        seed_prompt(
            db,
            name="financial_advisor",
            prompt_text=financial_advisor_prompt_v2,
            model_settings=financial_model_settings_v2,
            output_schema=financial_output_schema,
            author="seed-script",
            changelog="seed v2: concise financial outputs + cheaper model"
        )

        product_strategist_prompt_v2 = product_strategist_prompt + "\nINSTRUCTIONS: Limit recommended_next_steps to top 3 items; be concise."
        product_model_settings_v2 = {"provider": "openai", "model_name": "gpt-3.5-turbo", "temperature": 0.1, "max_tokens": 250}
        seed_prompt(
            db,
            name="product_strategist",
            prompt_text=product_strategist_prompt_v2,
            model_settings=product_model_settings_v2,
            output_schema=product_output_schema,
            author="seed-script",
            changelog="seed v2: concise product strategy + cheaper model"
        )
    finally:
        try:
            db.close()
        except Exception:
            pass


run_script(purge=True)