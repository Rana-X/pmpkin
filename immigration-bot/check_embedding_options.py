"""Check available embedding options in MongoDB Atlas."""

import os
from pathlib import Path
from dotenv import load_dotenv
from pymongo import MongoClient

# Load environment variables
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

MONGODB_URI = os.environ.get("MONGODB_URI")
DATABASE_NAME = "rfe_tool"

def main():
    """Check MongoDB Atlas capabilities and embedding options."""

    print("=" * 80)
    print("MONGODB ATLAS EMBEDDING OPTIONS CHECK")
    print("=" * 80)

    # Connect to MongoDB
    print(f"\nConnecting to MongoDB Atlas...")
    client = MongoClient(MONGODB_URI)
    db = client[DATABASE_NAME]

    # Get cluster info
    print("\n" + "-" * 80)
    print("CLUSTER INFORMATION:")
    print("-" * 80)

    try:
        server_info = client.server_info()
        print(f"MongoDB Version: {server_info.get('version', 'Unknown')}")
        print(f"Connection Type: {'Atlas' if 'mongodb.net' in MONGODB_URI else 'Local/Self-hosted'}")
    except Exception as e:
        print(f"Could not get server info: {e}")

    # List databases
    print(f"\nDatabases:")
    for db_name in client.list_database_names():
        print(f"  - {db_name}")

    # List collections in rfe_tool
    print(f"\nCollections in '{DATABASE_NAME}':")
    for coll_name in db.list_collection_names():
        count = db[coll_name].count_documents({})
        print(f"  - {coll_name}: {count} documents")

    # Check for Atlas Search indexes
    print("\n" + "-" * 80)
    print("ATLAS SEARCH / VECTOR SEARCH CHECK:")
    print("-" * 80)

    try:
        # Try to list search indexes
        cases = db["cases"]

        # This command checks if Atlas Search is available
        # Note: This may not work on all MongoDB versions/setups
        try:
            indexes = list(cases.list_search_indexes())
            if indexes:
                print(f"\n✓ Atlas Search indexes found:")
                for idx in indexes:
                    print(f"  - {idx}")
            else:
                print("\n⚠️  No Atlas Search indexes found")
                print("   You can create vector search indexes in Atlas UI")
        except Exception as e:
            print(f"\n⚠️  Atlas Search may not be available: {e}")
            print("   This is normal for MongoDB Community or M0/M2/M5 free tiers")

    except Exception as e:
        print(f"Error checking search indexes: {e}")

    # Check current case status
    print("\n" + "-" * 80)
    print("CURRENT DATA STATUS:")
    print("-" * 80)

    cases_coll = db["cases"]
    total = cases_coll.count_documents({})

    print(f"\nTotal cases: {total}")
    print("\nStatus breakdown:")
    for status in ["embedded", "features_extracted", "text_extracted", "uploaded", "embedding_failed"]:
        count = cases_coll.count_documents({"status": status})
        if count > 0:
            print(f"  - {status}: {count}")

    # Check if any cases already have embeddings
    with_embeddings = cases_coll.count_documents({"embedding": {"$exists": True}})
    print(f"\nCases with embeddings: {with_embeddings}")

    # Sample a case to see structure
    sample = cases_coll.find_one({"status": "features_extracted"})
    if sample:
        print("\n" + "-" * 80)
        print("SAMPLE CASE STRUCTURE:")
        print("-" * 80)
        print(f"\nFilename: {sample.get('filename')}")
        print(f"Status: {sample.get('status')}")
        print(f"Has full_text: {'Yes' if sample.get('full_text') else 'No'}")
        print(f"Text length: {len(sample.get('full_text', ''))} chars")
        print(f"Has embedding: {'Yes' if sample.get('embedding') else 'No'}")

    # Recommendations
    print("\n" + "=" * 80)
    print("EMBEDDING OPTIONS AVAILABLE:")
    print("=" * 80)

    print("""
Option 1: VOYAGE AI STANDALONE (Recommended)
  ✓ Use Voyage AI's voyage-law-2 model (optimized for legal docs)
  ✓ 1024 dimensions
  ✓ Best quality for H-1B legal documents
  ⚠️  Requires: VOYAGE_API_KEY from https://dash.voyageai.com

  Usage: Run generate_embeddings.py with Voyage API key

Option 2: OPENAI EMBEDDINGS (Already Available)
  ✓ Use OpenAI's text-embedding-3-large or text-embedding-ada-002
  ✓ You already have OPENAI_API_KEY
  ✓ 1536 or 3072 dimensions

  Usage: Modify generate_embeddings.py to use OpenAI instead

Option 3: MONGODB ATLAS VECTOR SEARCH (If Available)
  ⚠️  Requires Atlas M10+ cluster (not M0/M2/M5 free tier)
  ⚠️  May need to enable Vector Search in Atlas UI

  Steps:
  1. Go to Atlas UI → Database → Search → Create Search Index
  2. Choose "Vector Search"
  3. Configure embedding source (Voyage, OpenAI, etc.)
  4. Use Atlas-managed embeddings

RECOMMENDATION:
For now, use Option 1 (Voyage AI) or Option 2 (OpenAI).
Both will work well for your H-1B document analysis.
""")

    client.close()


if __name__ == "__main__":
    main()
