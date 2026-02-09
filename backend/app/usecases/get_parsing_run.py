"""Use case for getting parsing run."""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from types import SimpleNamespace
import json
from app.adapters.db.repositories import DomainQueueRepository
from app.adapters.db.models import ParsingRequestModel


async def execute(db: AsyncSession, run_id: str):
    """Get parsing run by ID."""
    # CRITICAL FIX: Use SimpleNamespace instead of ParsingRunModel to avoid AttributeError
    # SQLAlchemy tries to load all columns including results_count when using select(ParsingRunModel)
    # Even creating model with object.__new__() triggers SQLAlchemy's column loading
    # Using SimpleNamespace completely bypasses SQLAlchemy
    
    # First, calculate results_count from domains_queue
    domain_queue_repo = DomainQueueRepository(db)
    entries, count = await domain_queue_repo.list(
        limit=1,
        offset=0,
        parsing_run_id=run_id
    )
    results_count = count if count > 0 else None
    
    # Update results_count in DB using direct SQL (avoids setattr issues)
    if results_count is not None:
        try:
            await db.execute(
                text("UPDATE parsing_runs SET results_count = :count WHERE run_id = :run_id"),
                {"count": results_count, "run_id": run_id}
            )
            await db.commit()
        except Exception:
            await db.rollback()
    
    # ALWAYS use direct SQL to get run data - this completely avoids SQLAlchemy column loading
    sql_result = await db.execute(
        text("""
            SELECT pr.id, pr.run_id, pr.request_id, pr.parser_task_id, 
                   pr.status, pr.depth, pr.source, pr.created_at, 
                   pr.started_at, pr.finished_at, pr.error_message, pr.process_log
            FROM parsing_runs pr
            WHERE pr.run_id = :run_id
        """),
        {"run_id": run_id}
    )
    row = sql_result.fetchone()
    if not row:
        return None
    
    # Create SimpleNamespace instead of ParsingRunModel to completely avoid SQLAlchemy
    # This is a simple object that doesn't trigger SQLAlchemy's column loading
    run = SimpleNamespace()
    run.id = row[0]
    run.run_id = row[1]
    run.request_id = row[2]
    run.parser_task_id = row[3]
    run.status = row[4]
    run.depth = row[5]
    run.source = row[6]
    run.created_at = row[7]
    run.started_at = row[8]
    run.finished_at = row[9]
    run.error_message = row[10]
    process_log_val = row[11]
    if isinstance(process_log_val, str):
        try:
            process_log_val = json.loads(process_log_val)
        except Exception:
            process_log_val = None
    run.process_log = process_log_val if isinstance(process_log_val, dict) else None  # JSONB field
    
    # CRITICAL FIX: Load request using direct SQL to avoid any SQLAlchemy model loading
    # Even loading ParsingRequestModel might trigger SQLAlchemy to check ParsingRunModel
    try:
        request_sql = await db.execute(
            text("""
                SELECT pr.id, pr.title, pr.raw_keys_json
                FROM parsing_requests pr
                WHERE pr.id = :request_id
            """),
            {"request_id": row[2]}
        )
        request_row = request_sql.fetchone()
        if request_row:
            request_obj = SimpleNamespace()
            request_obj.id = request_row[0]
            request_obj.title = request_row[1]
            request_obj.raw_keys_json = request_row[2]
            run.request = request_obj
        else:
            run.request = None
    except Exception:
        run.request = None
    
    return run
