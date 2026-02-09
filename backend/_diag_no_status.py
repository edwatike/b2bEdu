"""Report counts of run_domains without status."""
import asyncio
from sqlalchemy import text
from app.adapters.db.session import AsyncSessionLocal


async def main() -> None:
    async with AsyncSessionLocal() as db:
        no_status = (await db.execute(
            text("SELECT COUNT(*) FROM run_domains WHERE status IS NULL OR status = ''")
        )).scalar() or 0
        no_status_dist = (await db.execute(
            text("SELECT COUNT(DISTINCT domain) FROM run_domains WHERE status IS NULL OR status = ''")
        )).scalar() or 0
        not_final = (await db.execute(
            text("SELECT COUNT(*) FROM run_domains WHERE COALESCE(status,'') NOT IN ('supplier','reseller','requires_moderation','needs_moderation')")
        )).scalar() or 0

    print(f"run_domains without status (null/empty): {int(no_status)} (distinct domains: {int(no_status_dist)})")
    print(f"run_domains without final status: {int(not_final)}")


if __name__ == "__main__":
    asyncio.run(main())
