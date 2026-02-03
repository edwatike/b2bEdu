"""Test Groq recognition on all files from testsss folder."""
import sys
from pathlib import Path
import os
import time

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.cabinet_recognition import (
    RecognitionEngine,
    extract_text_best_effort,
    extract_item_names_via_groq_with_usage,
    normalize_item_names,
    parse_positions_from_text,
    RecognitionDependencyError,
)

# Test directory (main repo, not worktree)
TEST_DIR = Path("D:/b2b/testsss")

def get_groq_key() -> str:
    """Get Groq API key from environment."""
    key = os.getenv("GROQ_API_KEY", "").strip()
    if not key:
        env_file = Path(__file__).parent / ".env"
        if env_file.exists():
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("GROQ_API_KEY="):
                        key = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break
    return key


def main():
    print("=" * 80)
    print("GROQ RECOGNITION TEST - Worktree Version")
    print("=" * 80)
    
    if not TEST_DIR.exists():
        print(f"\nERROR: Test directory not found: {TEST_DIR}")
        return
    
    # Get all test files
    test_files = [
        f for f in TEST_DIR.glob("*")
        if f.suffix.lower() in {".pdf", ".docx", ".xlsx", ".png", ".jpg", ".jpeg"}
    ]
    
    if not test_files:
        print(f"\nNo test files found in {TEST_DIR}")
        return
    
    print(f"\nFound {len(test_files)} test files:")
    for f in test_files:
        print(f"  - {f.name}")
    
    # Get Groq key
    groq_key = get_groq_key()
    if groq_key:
        print(f"\nGroq API key: {'*' * 10}...{groq_key[-4:]}")
    else:
        print(f"\nWARNING: GROQ_API_KEY not found")
        return
    
    # Test each file
    results = []
    for filepath in sorted(test_files):
        print(f"\n{'=' * 80}")
        print(f"FILE: {filepath.name}")
        print(f"{'=' * 80}")
        
        try:
            with open(filepath, "rb") as f:
                content = f.read()
            
            # Extract text
            text = extract_text_best_effort(
                filename=filepath.name,
                content=content,
                engine=RecognitionEngine.auto
            )
            print(f"Text extracted: {len(text)} chars")
            
            if not text:
                print("ERROR: No text extracted!")
                results.append({"file": filepath.name, "status": "FAIL", "error": "No text", "positions": 0})
                continue
            
            # Heuristic (fallback)
            heuristic = parse_positions_from_text(text)
            print(f"Heuristic positions: {len(heuristic)}")
            
            # Groq extraction
            groq_positions = []
            groq_error = None
            try:
                groq_positions, usage = extract_item_names_via_groq_with_usage(
                    text=text,
                    api_key=groq_key
                )
                print(f"✅ Groq SUCCESS: {len(groq_positions)} positions")
                print(f"   Tokens: {usage.get('total_tokens', 0)}")
                
                # Show first 8 positions
                for i, p in enumerate(groq_positions[:8], 1):
                    print(f"   {i}. {p}")
                if len(groq_positions) > 8:
                    print(f"   ... and {len(groq_positions) - 8} more")
                
                results.append({
                    "file": filepath.name,
                    "status": "OK",
                    "positions": len(groq_positions),
                    "tokens": usage.get("total_tokens", 0)
                })
                
            except RecognitionDependencyError as e:
                groq_error = str(e)[:100]
                print(f"❌ Groq FAILED: {groq_error}")
                results.append({
                    "file": filepath.name,
                    "status": "FAIL",
                    "error": groq_error,
                    "positions": len(heuristic),
                    "fallback": "heuristic"
                })
            
            # Small delay to avoid rate limit
            time.sleep(2)
            
        except Exception as e:
            print(f"\nERROR: {e}")
            results.append({"file": filepath.name, "status": "ERROR", "error": str(e)[:100]})
    
    # Summary
    print(f"\n{'=' * 80}")
    print("SUMMARY")
    print(f"{'=' * 80}")
    
    total_ok = sum(1 for r in results if r["status"] == "OK")
    total_fail = sum(1 for r in results if r["status"] in ["FAIL", "ERROR"])
    total_positions = sum(r.get("positions", 0) for r in results if r["status"] == "OK")
    
    for r in results:
        status_icon = "✅" if r["status"] == "OK" else "❌"
        print(f"{status_icon} {r['file']}: {r['status']}", end="")
        if r["status"] == "OK":
            print(f" ({r['positions']} positions, {r.get('tokens', 0)} tokens)")
        elif "error" in r:
            print(f" - {r.get('error', 'unknown')}")
        else:
            print()
    
    print(f"\n{'=' * 80}")
    print(f"Total: {total_ok} OK, {total_fail} FAIL")
    print(f"Total positions extracted: {total_positions}")
    print(f"{'=' * 80}")


if __name__ == "__main__":
    main()
