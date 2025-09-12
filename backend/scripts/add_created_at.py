import sys
import logging
from sqlalchemy import text
from config.database import get_engine

logger = logging.getLogger(__name__)

def run_created_at():
    engine = get_engine()
    try:
        with engine.begin() as conn:
            # check existing columns
            res = conn.execute(text("PRAGMA table_info('cost_events');")).fetchall()
            cols = [r[1] for r in res]  # second column is name
            if "created_at" in cols:
                print("created_at already exists; nothing to do.")
                return

            # add nullable column (SQLite disallows non-constant default in ALTER)
            print("Adding nullable 'created_at' column...")
            conn.execute(text("ALTER TABLE cost_events ADD COLUMN created_at DATETIME;"))

            # backfill existing rows with CURRENT_TIMESTAMP
            print("Backfilling existing rows with CURRENT_TIMESTAMP...")
            conn.execute(text("UPDATE cost_events SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL;"))

            print("Done. New rows will get created_at if you set it in inserts (or add a default via migration).")
    except Exception as e:
        logger.info("Failed to add created_at column")
        sys.exit(1)

run_created_at()