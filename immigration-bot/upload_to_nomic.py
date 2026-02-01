"""Upload H-1B AAO cases to Nomic Atlas for interactive visualization."""

import os
from pathlib import Path
from dotenv import load_dotenv

import numpy as np
from pymongo import MongoClient
from nomic import atlas

# Load environment variables
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

MONGODB_URI = os.environ.get("MONGODB_URI")
DATABASE_NAME = "rfe_tool"


def main():
    """Upload cases to Nomic Atlas."""

    print("=" * 80)
    print("NOMIC ATLAS UPLOAD - H-1B AAO DECISIONS")
    print("=" * 80)

    # Connect to MongoDB
    print("\n[1/3] Connecting to MongoDB...")
    client = MongoClient(MONGODB_URI)
    db = client[DATABASE_NAME]
    cases_collection = db["cases"]

    # Fetch all completed cases with embeddings
    print("[2/3] Fetching cases with embeddings...")
    query = {"status": "complete", "embedding": {"$exists": True}}
    cases = list(cases_collection.find(query))

    if len(cases) == 0:
        print("\n❌ No cases found with embeddings!")
        print("   Make sure you've run generate_embeddings_openai.py first")
        client.close()
        return

    total_cases = len(cases)
    print(f"Found {total_cases} cases")

    # Extract embeddings
    print("\nExtracting embeddings...")
    embeddings = np.array([c["embedding"] for c in cases])
    print(f"Embeddings shape: {embeddings.shape}")

    # Prepare metadata for each case - DON'T include embeddings in data
    print("\nPreparing metadata for visualization...")
    data = []
    for i, c in enumerate(cases):
        # Convert arrays to comma-separated strings
        rfe_issues = c.get("rfe_issues", [])
        denial_reasons = c.get("denial_reasons", [])
        arguments_made = c.get("arguments_made", [])

        data.append({
            "id": str(c["_id"]),
            "filename": c.get("filename", "Unknown"),
            "outcome": c.get("outcome", "Unknown"),
            "job_title": c.get("job_title", "Unknown"),
            "company_name": c.get("company_name", "Unknown"),
            "company_type": c.get("company_type", "Unknown"),
            "case_number": c.get("case_number", "Unknown"),
            "service_center": c.get("service_center", "Unknown"),
            "wage_level": c.get("wage_level", "Unknown"),
            "rfe_issues": ", ".join(rfe_issues) if rfe_issues else "None",
            "denial_reasons": ", ".join(denial_reasons) if denial_reasons else "None",
            "arguments_made": ", ".join(arguments_made) if arguments_made else "None"
        })

    print(f"Prepared metadata for {len(data)} cases")

    # Upload to Nomic Atlas
    print("\n[3/3] Uploading to Nomic Atlas...")
    print("(This may take 30-60 seconds...)")

    try:
        # Create the map with embeddings - remove indexed_field to use embeddings
        dataset = atlas.map_data(
            data=data,
            embeddings=embeddings,
            identifier="H1B-AAO-Decisions-v2",
            description="H-1B AAO Appeal Decisions - Specialty Occupation Cases (Embedding-based visualization)"
        )

        print("\n" + "=" * 80)
        print("✓ UPLOAD SUCCESSFUL!")
        print("=" * 80)

        # Print the dataset info
        print(f"\n{dataset}")

        # Extract and display the URL more clearly
        print("\n" + "-" * 80)
        print("YOUR INTERACTIVE VISUALIZATION:")
        print("-" * 80)
        print("\n🌐 Open this link in your browser:")
        print(f"   → {dataset}")
        print("\n📊 What you can do:")
        print("   • Hover over dots to see case details")
        print("   • Color by: outcome, company_type, job_title, etc.")
        print("   • Filter and search cases")
        print("   • Zoom and pan to explore clusters")
        print("   • Share the link with anyone (great for demos!)")
        print("\n💡 Try coloring by 'outcome' to see:")
        print("   • Green dots = SUSTAINED (won)")
        print("   • Red dots = DISMISSED (lost)")
        print("   • Gold dots = REMANDED (retry)")

        # Print summary stats
        print("\n" + "-" * 80)
        print("DATA SUMMARY:")
        print("-" * 80)
        outcome_counts = {}
        for case in data:
            outcome = case["outcome"]
            outcome_counts[outcome] = outcome_counts.get(outcome, 0) + 1

        print(f"Total cases uploaded: {total_cases}")
        print(f"Embedding dimensions: {embeddings.shape[1]}")
        print("\nOutcome distribution:")
        for outcome, count in sorted(outcome_counts.items()):
            print(f"  • {outcome}: {count}")

    except Exception as e:
        print("\n" + "=" * 80)
        print("❌ UPLOAD FAILED")
        print("=" * 80)
        print(f"\nError: {e}")
        print("\nPossible issues:")
        print("  1. Not authenticated - Run: nomic login")
        print("  2. Network connection issue")
        print("  3. API rate limit")
        print("\nTo authenticate:")
        print("  • Option A: Run 'nomic login' (opens browser)")
        print("  • Option B: Get API key from atlas.nomic.ai")
        print("             Then run 'nomic login <your-api-key>'")
        client.close()
        return

    client.close()


if __name__ == "__main__":
    main()
