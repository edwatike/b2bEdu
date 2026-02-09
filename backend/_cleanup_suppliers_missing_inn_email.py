"""Delete moderator_suppliers records missing INN or email (and related domains/emails)."""
import asyncio
from sqlalchemy import text
from app.adapters.db.session import AsyncSessionLocal


async def main() -> None:
    async with AsyncSessionLocal() as db:
        rows = (
            await db.execute(
                text(
                    "SELECT id FROM moderator_suppliers "
                    "WHERE COALESCE(inn, '') = '' OR COALESCE(email, '') = ''"
                )
            )
        ).fetchall()
        ids = [int(r[0]) for r in rows if r and r[0]]
        if not ids:
            print("No suppliers to delete.")
            return

        await db.execute(text("DELETE FROM supplier_domains WHERE supplier_id = ANY(:ids)"), {"ids": ids})
        await db.execute(text("DELETE FROM supplier_emails WHERE supplier_id = ANY(:ids)"), {"ids": ids})
        await db.execute(text("DELETE FROM moderator_suppliers WHERE id = ANY(:ids)"), {"ids": ids})
        await db.commit()

    print(f"Deleted suppliers without INN/email: {len(ids)}")


if __name__ == "__main__":
    asyncio.run(main())
