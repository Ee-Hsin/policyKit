"""Script to inspect the contents of ChromaDB."""

import asyncio
from app.core.vector_store import ChromaVectorStore
import json

async def inspect_chroma():
    """Inspect the contents of ChromaDB."""
    vector_store = ChromaVectorStore()
    
    results = vector_store.collection.get()
    
    print("\n=== ChromaDB Contents ===")
    print(f"Total items: {len(results['ids'])}")
    
    if not results['ids']:
        print("No items found in ChromaDB.")
        return
    
    print("\nItems:")
    for i, (id, metadata) in enumerate(zip(results['ids'], results['metadatas']), 1):
        print(f"\n--- Item {i} ---")
        print(f"ID: {id}")
        print(f"Job Description: {metadata['job_description']}")
        print(f"Has Violations: {metadata['has_violations']}")
        if metadata.get('violations'):
            print("Violations:")
            violations = json.loads(metadata['violations'])
            for violation in violations:
                print(f"  - Category: {violation['category']}")
                print(f"    Policies: {', '.join(violation['policy'])}")
                print(f"    Reasoning: {violation['reasoning']}")
        print("-" * 50)

if __name__ == "__main__":
    asyncio.run(inspect_chroma()) 