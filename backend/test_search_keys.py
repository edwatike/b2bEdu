"""Test search keys extraction vs individual positions."""
import sys
from pathlib import Path
import os
import time

sys.path.insert(0, str(Path(__file__).parent))

from app.services.cabinet_recognition import (
    extract_text_best_effort,
    extract_search_keys_via_groq,
    extract_item_names_via_groq_with_usage,
    RecognitionEngine,
)

TEST_DIR = Path("D:/b2b/testsss")

def get_groq_key() -> str:
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
    print("COMPARISON: Individual Positions vs Search Keys")
    print("=" * 80)
    
    groq_key = get_groq_key()
    if not groq_key:
        print("\nERROR: GROQ_API_KEY not found")
        return
    
    print(f"\nGroq API key: {'*' * 10}...{groq_key[-4:]}")
    
    if not TEST_DIR.exists():
        print(f"\nERROR: Test directory not found: {TEST_DIR}")
        return
    
    test_files = [
        f for f in TEST_DIR.glob("*")
        if f.suffix.lower() in {".pdf", ".docx", ".xlsx", ".png", ".jpg", ".jpeg"}
    ]
    
    if not test_files:
        print(f"\nNo test files found in {TEST_DIR}")
        return
    
    total_positions = 0
    total_keys = 0
    
    for test_file in sorted(test_files):
        print(f"\n{'=' * 80}")
        print(f"FILE: {test_file.name}")
        print(f"{'=' * 80}")
        
        try:
            with open(test_file, "rb") as f:
                content = f.read()
            
            # Extract text
            text = extract_text_best_effort(
                filename=test_file.name,
                content=content,
                engine=RecognitionEngine.auto
            )
            
            if not text:
                print("ERROR: No text extracted")
                continue
            
            print(f"Text length: {len(text)} chars")
            
            # Get individual positions
            print("\n[INDIVIDUAL POSITIONS]")
            try:
                positions, pos_usage = extract_item_names_via_groq_with_usage(
                    text=text,
                    api_key=groq_key
                )
                total_positions += len(positions)
                
                print(f"  Found: {len(positions)} positions")
                print(f"  Tokens: {pos_usage.get('total_tokens', 0)}")
                for i, p in enumerate(positions[:5], 1):
                    print(f"    {i}. {p}")
                if len(positions) > 5:
                    print(f"    ... and {len(positions) - 5} more")
            except Exception as e:
                print(f"  ERROR: {e}")
                continue
            
            # Increased delay to avoid rate limit
            time.sleep(3)
            
            # Get search keys (grouped)
            print("\n[SEARCH KEYS - Grouped]")
            try:
                keys, categories, keys_usage = extract_search_keys_via_groq(
                    text=text,
                    api_key=groq_key
                )
                total_keys += len(keys)
                
                print(f"  Found: {len(keys)} search keys")
                print(f"  Tokens: {keys_usage.get('total_tokens', 0)}")
                print(f"  Categories: {', '.join(categories)}")
                print(f"\n  Keys:")
                for i, k in enumerate(keys, 1):
                    print(f"    {i}. {k}")
                
                # Show optimization
                reduction = round((1 - len(keys) / max(len(positions), 1)) * 100)
                print(f"\n  ✅ OPTIMIZATION: {len(positions)} → {len(keys)} ({reduction}% reduction)")
                
            except Exception as e:
                print(f"  ERROR: {e}")
            
            time.sleep(3.5)
            
        except Exception as e:
            print(f"\nERROR: {e}")
    
    # Summary
    print(f"\n{'=' * 80}")
    print("SUMMARY")
    print(f"{'=' * 80}")
    print(f"Total individual positions: {total_positions}")
    print(f"Total search keys (grouped): {total_keys}")
    
    if total_positions > 0:
        reduction = round((1 - total_keys / total_positions) * 100)
        saved = total_positions - total_keys
        print(f"\n✅ OPTIMIZATION:")
        print(f"  Reduction: {reduction}%")
        print(f"  Parsing runs saved: {saved}")
        print(f"  Estimated time saved: ~{saved * 30} seconds ({saved * 0.5:.1f} min)")


if __name__ == "__main__":
    main()
