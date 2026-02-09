"""Cleanup run_domains/domain_moderation for run c1515ce9 when parser failed due to missing Playwright browser."""
import asyncio
from sqlalchemy import text
from app.adapters.db.session import AsyncSessionLocal

RUN_ID = "c1515ce9-41d3-462e-a822-2a48f6155e81"


async def main() -> None:
    async with AsyncSessionLocal() as db:
        rows = (
            await db.execute(
                text(
                    "SELECT domain FROM run_domains "
                    "WHERE run_id = :rid "
                    "AND status = 'requires_moderation' "
                    "AND (reason ILIKE '%playwright%' OR reason ILIKE '%Executable doesn''t exist%')"
                ),
                {"rid": RUN_ID},
            )
        ).fetchall()
        domains = [str(r[0]) for r in rows if r and r[0]]

        if not domains:
            print("No run_domains to cleanup.")
            return

        await db.execute(
            text(
                "UPDATE run_domains SET status = NULL, reason = NULL, updated_at = NOW() "
                "WHERE run_id = :rid AND domain = ANY(:domains)"
            ),
            {"rid": RUN_ID, "domains": domains},
        )
        await db.execute(
            text("DELETE FROM domain_moderation WHERE domain = ANY(:domains)"),
            {"domains": domains},
        )
        await db.commit()

    print(f"Cleaned {len(domains)} domains for run {RUN_ID}.")


if __name__ == "__main__":
    asyncio.run(main())
