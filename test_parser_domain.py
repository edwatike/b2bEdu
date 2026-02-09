import asyncio
import sys
sys.path.insert(0, r'D:\b2b\domain_info_parser')
sys.path.insert(0, r'D:\b2b\backend')
from parser import DomainInfoParser

async def test():
    print("Creating DomainInfoParser...")
    p = DomainInfoParser(headless=True, timeout=12000)
    print("Starting browser...")
    await p.start()
    print(f"Browser connected: {p.browser.is_connected()}")
    
    print("Parsing tophouse.ru...")
    try:
        r = await asyncio.wait_for(p.parse_domain('tophouse.ru'), timeout=90)
        print(f"INN: {r.get('inn')}")
        print(f"error: {r.get('error')}")
        print(f"emails: {r.get('emails')}")
        print(f"source_urls: {r.get('source_urls')}")
        print(f"extraction_log: {r.get('extraction_log')}")
    except Exception as e:
        print(f"EXCEPTION: type={type(e).__name__}, msg='{e}', repr={repr(e)}")
    
    await p.close()

asyncio.run(test())
