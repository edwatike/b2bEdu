"""Check which domains _domain_exists_in_suppliers would filter out"""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(__file__))

async def main():
    from app.adapters.db.session import AsyncSessionLocal
    from sqlalchemy import text
    from app.transport.routers.domain_parser import _domain_exists_in_suppliers, _domain_requires_moderation, _normalize_domain_full, _normalize_domain

    domains = [
        "avito.ru", "generalsteel.ru", "market.yandex.ru", "mc.ru",
        "metallikaspb.ru", "metallobazav.ru", "ozon.ru", "petrovich.ru",
        "rusevromet.ru", "shopmetal.ru", "spb.inoxpoint.ru", "spb.kontinental.ru",
        "spb.russteels.ru", "steelss.ru", "szppk.ru", "wildberries.ru"
    ]

    for d in domains:
        full = _normalize_domain_full(d)
        root = _normalize_domain(d)
        is_sup = await _domain_exists_in_suppliers(d)
        is_mod = await _domain_requires_moderation(d)
        skip = is_sup or is_mod
        reason = []
        if is_sup: reason.append("supplier")
        if is_mod: reason.append("moderation")
        print(f"  {d:25s} full={full:20s} root={root:20s} skip={skip} ({', '.join(reason) or 'NEW'})")

asyncio.run(main())
