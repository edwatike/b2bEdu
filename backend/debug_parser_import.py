import sys
import os

print(f"CWD: {os.getcwd()}")
print(f"sys.path: {sys.path}")

try:
    # Try importing exactly as the router does
    from parser import DomainInfoParser
    print("SUCCESS: Imported DomainInfoParser")
    p = DomainInfoParser()
    print("SUCCESS: Instantiated DomainInfoParser")
except Exception as e:
    print(f"FAILURE: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

try:
    import parser
    print(f"Parser module: {parser}")
    print(f"Parser file: {getattr(parser, '__file__', 'unknown')}")
except Exception as e:
    print(f"Parser import check failed: {e}")
