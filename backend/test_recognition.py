"""Test script for cabinet recognition - tests all files in testsss folder."""
import asyncio
import os
import sys
from pathlib import Path

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

# Load environment
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

TEST_DIR = Path(__file__).parent.parent / "testsss"

def get_groq_key() -> str:
    """Get Groq API key from environment."""
    key = os.getenv("GROQ_API_KEY", "").strip()
    if not key:
        # Try to load from backend .env
        env_file = Path(__file__).parent / ".env"
        if env_file.exists():
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("GROQ_API_KEY="):
                        key = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break
    return key


def test_file(filepath: Path, groq_key: str) -> dict:
    """Test recognition for a single file."""
    result = {
        "file": filepath.name,
        "size_kb": filepath.stat().st_size / 1024,
        "text_extracted": False,
        "text_length": 0,
        "text_preview": "",
        "groq_used": False,
        "groq_error": None,
        "groq_tokens": {},
        "positions_groq": [],
        "positions_heuristic": [],
        "positions_final": [],
    }
    
    # Read file
    with open(filepath, "rb") as f:
        content = f.read()
    
    # Extract text
    print(f"\n{'='*60}")
    print(f"Testing: {filepath.name} ({result['size_kb']:.1f} KB)")
    print(f"{'='*60}")
    
    text = extract_text_best_effort(filename=filepath.name, content=content, engine=RecognitionEngine.auto)
    result["text_extracted"] = bool(text)
    result["text_length"] = len(text)
    result["text_preview"] = text[:500] if text else ""
    
    print(f"\n[TEXT EXTRACTION]")
    print(f"  Extracted: {result['text_extracted']}")
    print(f"  Length: {result['text_length']} chars")
    if text:
        print(f"  Preview (first 300 chars):\n{'-'*40}")
        print(text[:300])
        print(f"{'-'*40}")
    
    # Heuristic extraction (fallback)
    if text:
        heuristic_positions = parse_positions_from_text(text)
        result["positions_heuristic"] = heuristic_positions
        print(f"\n[HEURISTIC EXTRACTION]")
        print(f"  Found {len(heuristic_positions)} positions:")
        for i, pos in enumerate(heuristic_positions[:10], 1):
            print(f"    {i}. {pos}")
        if len(heuristic_positions) > 10:
            print(f"    ... and {len(heuristic_positions) - 10} more")
    
    # Groq extraction
    if text and groq_key:
        print(f"\n[GROQ EXTRACTION]")
        try:
            groq_positions, usage = extract_item_names_via_groq_with_usage(text=text, api_key=groq_key)
            result["groq_used"] = True
            result["groq_tokens"] = usage
            result["positions_groq"] = groq_positions
            result["positions_final"] = groq_positions
            
            print(f"  Status: SUCCESS")
            print(f"  Tokens: {usage}")
            print(f"  Found {len(groq_positions)} positions:")
            for i, pos in enumerate(groq_positions[:15], 1):
                print(f"    {i}. {pos}")
            if len(groq_positions) > 15:
                print(f"    ... and {len(groq_positions) - 15} more")
                
        except RecognitionDependencyError as e:
            result["groq_error"] = str(e)
            result["positions_final"] = result["positions_heuristic"]
            print(f"  Status: FAILED")
            print(f"  Error: {e}")
    else:
        if not groq_key:
            result["groq_error"] = "GROQ_API_KEY not configured"
            print(f"\n[GROQ EXTRACTION]")
            print(f"  Status: SKIPPED (no API key)")
        result["positions_final"] = result["positions_heuristic"]
    
    # Final result
    print(f"\n[FINAL RESULT]")
    print(f"  Total positions: {len(result['positions_final'])}")
    
    return result


def main():
    print("="*60)
    print("CABINET RECOGNITION TEST")
    print("="*60)
    
    # Check test directory
    if not TEST_DIR.exists():
        print(f"ERROR: Test directory not found: {TEST_DIR}")
        return
    
    # Get test files
    test_files = list(TEST_DIR.glob("*"))
    test_files = [f for f in test_files if f.is_file() and f.suffix.lower() in {".pdf", ".docx", ".xlsx", ".png", ".jpg", ".jpeg", ".txt"}]
    
    if not test_files:
        print(f"ERROR: No test files found in {TEST_DIR}")
        return
    
    print(f"\nFound {len(test_files)} test files:")
    for f in test_files:
        print(f"  - {f.name}")
    
    # Get Groq key
    groq_key = get_groq_key()
    if groq_key:
        print(f"\nGroq API key: {'*' * 10}...{groq_key[-4:]}")
    else:
        print(f"\nWARNING: GROQ_API_KEY not found - will use heuristic extraction only")
    
    # Test each file
    results = []
    for filepath in sorted(test_files):
        try:
            result = test_file(filepath, groq_key)
            results.append(result)
        except Exception as e:
            print(f"\nERROR testing {filepath.name}: {e}")
            import traceback
            traceback.print_exc()
            results.append({
                "file": filepath.name,
                "error": str(e),
            })
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    total_positions = 0
    groq_success = 0
    groq_failed = 0
    
    for r in results:
        if "error" in r and r.get("error"):
            print(f"\n{r['file']}: ERROR - {r['error']}")
            continue
            
        positions = len(r.get("positions_final", []))
        total_positions += positions
        
        if r.get("groq_used"):
            groq_success += 1
            status = "✅ GROQ"
        elif r.get("groq_error"):
            groq_failed += 1
            status = f"❌ GROQ ({r['groq_error'][:50]}...)" if len(r.get("groq_error", "")) > 50 else f"❌ GROQ ({r.get('groq_error')})"
        else:
            status = "⚠️ HEURISTIC"
        
        print(f"\n{r['file']}:")
        print(f"  Text: {r.get('text_length', 0)} chars")
        print(f"  Status: {status}")
        print(f"  Positions: {positions}")
        if r.get("positions_final"):
            for i, pos in enumerate(r["positions_final"][:5], 1):
                print(f"    {i}. {pos}")
            if len(r["positions_final"]) > 5:
                print(f"    ... and {len(r['positions_final']) - 5} more")
    
    print(f"\n{'='*60}")
    print(f"TOTALS:")
    print(f"  Files tested: {len(results)}")
    print(f"  Groq success: {groq_success}")
    print(f"  Groq failed: {groq_failed}")
    print(f"  Total positions: {total_positions}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
