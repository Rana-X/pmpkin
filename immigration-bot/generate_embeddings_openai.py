"""Generate embeddings for all cases using OpenAI."""

import os
import time
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

from pymongo import MongoClient
from openai import OpenAI
from tqdm import tqdm

# Load environment variables
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

MONGODB_URI = os.environ.get("MONGODB_URI")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

if not MONGODB_URI or not OPENAI_API_KEY:
    raise EnvironmentError(
        f"Missing required environment variables in {env_path}\n"
        "Required: MONGODB_URI, OPENAI_API_KEY"
    )

DATABASE_NAME = "rfe_tool"
DELAY_BETWEEN_CALLS = 0.5  # seconds
MODEL = "text-embedding-3-large"  # 3072 dimensions, best quality
# Alternative: "text-embedding-3-small" (1536 dims, faster/cheaper)


def generate_embedding(text, openai_client, max_retries=2):
    """Generate embedding for text using OpenAI.

    Args:
        text: Input text to embed
        openai_client: OpenAI client instance
        max_retries: Number of retry attempts

    Returns:
        list: Embedding vector or None if failed
    """
    for attempt in range(max_retries):
        try:
            # OpenAI has 8191 token limit for embeddings
            # Roughly 1 token = 4 chars, so limit to ~30k chars
            max_chars = 30000
            if len(text) > max_chars:
                text = text[:max_chars]

            response = openai_client.embeddings.create(
                model=MODEL,
                input=text
            )

            embedding = response.data[0].embedding

            # Verify embedding dimensions
            expected_dims = 3072 if "large" in MODEL else 1536
            if len(embedding) != expected_dims:
                raise ValueError(f"Expected {expected_dims} dimensions, got {len(embedding)}")

            return embedding

        except Exception as e:
            if attempt < max_retries - 1:
                print(f"    ⚠️  OpenAI API error (attempt {attempt + 1}/{max_retries}): {e}")
                time.sleep(2)
                continue
            else:
                print(f"    ❌ Failed after {max_retries} attempts: {e}")
                return None

    return None


def main():
    """Main embedding generation pipeline."""

    print("=" * 80)
    print("OPENAI EMBEDDING GENERATION PIPELINE")
    print("=" * 80)

    # Connect to MongoDB
    print(f"\nConnecting to MongoDB...")
    client = MongoClient(MONGODB_URI)
    db = client[DATABASE_NAME]
    cases_collection = db["cases"]

    # Initialize OpenAI client
    openai_client = OpenAI(api_key=OPENAI_API_KEY)

    # Get all cases that need embeddings
    query = {"status": "features_extracted"}
    cases_to_process = list(cases_collection.find(query))
    total_cases = len(cases_to_process)

    if total_cases == 0:
        print("\n✓ No cases found with status='features_extracted'")
        print("  All cases may already be embedded!")

        # Check what statuses we have
        print("\nCurrent status distribution:")
        for status in ["embedded", "features_extracted", "text_extracted", "uploaded"]:
            count = cases_collection.count_documents({"status": status})
            if count > 0:
                print(f"  - {status}: {count}")

        client.close()
        return

    dims = 3072 if "large" in MODEL else 1536
    print(f"\nFound {total_cases} cases to process")
    print(f"Using model: {MODEL} ({dims} dimensions)")
    print("\n" + "-" * 80)

    succeeded = 0
    failed = 0

    # Process each case
    for idx, case in enumerate(tqdm(cases_to_process, desc="Generating embeddings"), 1):
        filename = case["filename"]
        case_id = case["_id"]
        full_text = case.get("full_text", "")

        if not full_text:
            print(f"\n[{idx}/{total_cases}] {filename}")
            print(f"  ❌ No full_text found")
            failed += 1
            continue

        try:
            print(f"\n[{idx}/{total_cases}] {filename}")
            print(f"  Text length: {len(full_text)} chars")

            # Generate embedding with OpenAI
            embedding = generate_embedding(full_text, openai_client)

            if embedding is None:
                # Mark as failed
                cases_collection.update_one(
                    {"_id": case_id},
                    {"$set": {
                        "status": "embedding_failed",
                        "embedding_failed_at": datetime.utcnow()
                    }}
                )
                failed += 1
                continue

            # Update MongoDB with embedding
            update_data = {
                "embedding": embedding,
                "embedding_model": MODEL,
                "embedding_dimensions": len(embedding),
                "status": "embedded",
                "embedded_at": datetime.utcnow()
            }

            cases_collection.update_one(
                {"_id": case_id},
                {"$set": update_data}
            )

            print(f"  ✓ Embedded ({len(embedding)} dims)")

            succeeded += 1

            # Rate limiting
            if idx < total_cases:
                time.sleep(DELAY_BETWEEN_CALLS)

        except Exception as e:
            print(f"  ❌ Unexpected error: {e}")

            cases_collection.update_one(
                {"_id": case_id},
                {"$set": {
                    "status": "embedding_failed",
                    "error": str(e),
                    "embedding_failed_at": datetime.utcnow()
                }}
            )

            failed += 1

            if idx < total_cases:
                time.sleep(DELAY_BETWEEN_CALLS)

    # Summary
    print("\n" + "=" * 80)
    print("EMBEDDING GENERATION COMPLETE")
    print("=" * 80)
    print(f"Total processed: {total_cases}")
    print(f"✓ Succeeded: {succeeded}")
    print(f"❌ Failed: {failed}")
    print("\nUpdated status in MongoDB:")
    print(f"  - embedded: {cases_collection.count_documents({'status': 'embedded'})}")
    print(f"  - embedding_failed: {cases_collection.count_documents({'status': 'embedding_failed'})}")
    print(f"  - features_extracted (pending): {cases_collection.count_documents({'status': 'features_extracted'})}")

    # Show sample embedding info
    if succeeded > 0:
        print("\n" + "-" * 80)
        print("SAMPLE EMBEDDING INFO:")
        print("-" * 80)
        sample = cases_collection.find_one({"status": "embedded"})
        if sample:
            print(f"\nFilename: {sample.get('filename')}")
            print(f"Embedding model: {sample.get('embedding_model')}")
            print(f"Embedding dimensions: {sample.get('embedding_dimensions')}")
            print(f"First 10 values: {sample.get('embedding', [])[:10]}")
            print(f"Embedded at: {sample.get('embedded_at')}")

    client.close()


if __name__ == "__main__":
    main()
