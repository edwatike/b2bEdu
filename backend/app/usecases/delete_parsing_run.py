"""Use case for deleting parsing run."""
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

logger = logging.getLogger(__name__)


async def execute(db: AsyncSession, run_id: str) -> bool:
    """Delete parsing run by run_id."""
    # CRITICAL FIX: Use direct SQL to delete, bypassing repository
    # This avoids the SimpleNamespace issue completely
    logger.info(f"Deleting parsing run {run_id} using direct SQL")
    
    # First, check if run exists
    check_result = await db.execute(
        text("SELECT COUNT(*) FROM parsing_runs WHERE run_id = :run_id"),
        {"run_id": run_id}
    )
    count_before = check_result.scalar()
    logger.info(f"Runs with run_id {run_id} before delete: {count_before}")
    
    if count_before == 0:
        logger.warning(f"Run {run_id} not found in database")
        return False
    
    # Delete the run
    result = await db.execute(
        text("DELETE FROM parsing_runs WHERE run_id = :run_id"),
        {"run_id": run_id}
    )
    # NOTE: Don't flush here - let the caller handle flush and commit
    # This prevents transaction conflicts in bulk delete
    
    deleted_count = result.rowcount
    logger.info(f"Delete query executed - rowcount: {deleted_count}")
    
    # Verify deletion
    check_result_after = await db.execute(
        text("SELECT COUNT(*) FROM parsing_runs WHERE run_id = :run_id"),
        {"run_id": run_id}
    )
    count_after = check_result_after.scalar()
    logger.info(f"Runs with run_id {run_id} after delete (before commit): {count_after}")
    
    # Check if any row was deleted
    return deleted_count > 0







