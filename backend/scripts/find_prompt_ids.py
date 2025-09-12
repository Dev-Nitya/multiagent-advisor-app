from config.database import get_db
from models.agent_costs import CostEvent

def run_script():
    db = next(get_db())
    try:
        cond = (
            (CostEvent.request_id == None) | (CostEvent.request_id == "") |
            (CostEvent.prompt_id == None)   | (CostEvent.prompt_id == "")
        )
        q = db.query(CostEvent).filter(cond)
        total = q.count()
        print(f"Found {total} CostEvent rows with NULL/empty request_id or prompt_id.")
        if total == 0:
            return
        deleted = q.delete(synchronize_session=False)
        db.commit()
        print(f"Deleted {deleted} rows.")
    finally:
        try:
            db.close()
        except Exception:
            pass

run_script()