"""Report run_domains status counts for run c1515ce9-41d3-462e-a822-2a48f6155e81."""
import asyncio
from sqlalchemy import text
from app.adapters.db.session import AsyncSessionLocal

RUN_ID = "c1515ce9-41d3-462e-a822-2a48f6155e81"


async def main() -> None:
    async with AsyncSessionLocal() as db:
        rows = (
            await db.execute(
                text(
                    "SELECT COALESCE(status, '') AS st, COUNT(*) "
                    "FROM run_domains WHERE run_id = :rid "
                    "GROUP BY COALESCE(status, '') ORDER BY COALESCE(status, '')"
                ),
                {"rid": RUN_ID},
            )
        ).fetchall()

    print("status counts:")
    for st, cnt in rows:
        label = st if st else "<<empty>>"
        print(f"{label}: {int(cnt)}")


if __name__ == "__main__":
    asyncio.run(main())
