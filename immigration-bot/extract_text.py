"""Extract text from PDFs in MongoDB using Reducto API."""

import os
import time
import tempfile
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

import requests
from pymongo import MongoClient
from gridfs import GridFS
from reducto import Reducto
from tqdm import tqdm

# Load environment variables
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

MONGODB_URI = os.environ.get("MONGODB_URI")
REDUCTO_API_KEY = os.environ.get("REDUCTO_API_KEY")

if not MONGODB_URI or not REDUCTO_API_KEY:
    raise EnvironmentError(
        f"Missing required environment variables in {env_path}\n"
        "Required: MONGODB_URI, REDUCTO_API_KEY"
    )

DATABASE_NAME = "rfe_tool"
DELAY_BETWEEN_CALLS = 1  # seconds


def extract_text_from_pdf(pdf_bytes, filename, reducto_client):
    """Extract text from PDF using Reducto API.

    Returns:
        dict with keys: full_text, pages, page_count, tables (if any)
    """
    # Write PDF to temp file (Reducto SDK requires file path)
    suffix = Path(filename).suffix or ".pdf"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = Path(tmp.name)

    try:
        # Step 1: Upload to Reducto
        print(f"  Uploading to Reducto...")
        upload_result = reducto_client.upload(file=tmp_path)

        # Step 2: Parse the uploaded file
        print(f"  Parsing (file_id: {upload_result.file_id})...")
        parse_response = reducto_client.parse.run(
            input=f"reducto://{upload_result.file_id}",
        )

        result = parse_response.result
        chunks = []

        # Step 3: Extract chunks (two possible response formats)
        if hasattr(result, "chunks"):
            # Full result returned inline
            for chunk in result.chunks:
                if chunk.content:
                    chunks.append(chunk.content)
        elif hasattr(result, "url"):
            # Large result - fetch from presigned URL
            print(f"  Fetching result from URL...")
            resp = requests.get(result.url, timeout=120)
            resp.raise_for_status()
            data = resp.json()
            for chunk in data.get("chunks", []):
                content = chunk.get("content", "")
                if content:
                    chunks.append(content)

        # Combine all text
        full_text = "\n\n".join(chunks)

        if not full_text.strip():
            raise ValueError("No text content extracted from PDF")

        # Build result
        return {
            "full_text": full_text,
            "pages": chunks,  # Each chunk typically represents content
            "page_count": len(chunks),
            "tables": [],  # Reducto can extract tables - add if needed
        }

    finally:
        # Clean up temp file
        try:
            tmp_path.unlink()
        except OSError:
            pass


def main():
    """Main extraction pipeline."""

    print("=" * 70)
    print("REDUCTO TEXT EXTRACTION PIPELINE")
    print("=" * 70)

    # Connect to MongoDB
    print(f"\nConnecting to MongoDB...")
    client = MongoClient(MONGODB_URI)
    db = client[DATABASE_NAME]
    fs = GridFS(db)
    cases_collection = db["cases"]

    # Initialize Reducto client
    reducto_client = Reducto(api_key=REDUCTO_API_KEY)

    # Get all cases that need text extraction
    query = {"status": "uploaded"}
    cases_to_process = list(cases_collection.find(query))
    total_cases = len(cases_to_process)

    if total_cases == 0:
        print("\n✓ No cases found with status='uploaded'")
        print("  All cases may already be processed!")
        client.close()
        return

    print(f"\nFound {total_cases} cases to process\n")
    print("-" * 70)

    succeeded = 0
    failed = 0

    # Process each case
    for idx, case in enumerate(tqdm(cases_to_process, desc="Processing PDFs"), 1):
        filename = case["filename"]
        pdf_id = case["pdf_id"]
        case_id = case["_id"]

        try:
            # Fetch PDF from GridFS
            print(f"\n[{idx}/{total_cases}] {filename}")
            print(f"  Fetching from GridFS (pdf_id: {pdf_id})...")

            pdf_file = fs.get(pdf_id)
            pdf_bytes = pdf_file.read()

            # Extract text using Reducto
            extracted_data = extract_text_from_pdf(pdf_bytes, filename, reducto_client)

            # Update MongoDB case
            update_data = {
                "full_text": extracted_data["full_text"],
                "pages": extracted_data["pages"],
                "page_count": extracted_data["page_count"],
                "tables": extracted_data.get("tables", []),
                "status": "text_extracted",
                "extracted_at": datetime.utcnow()
            }

            cases_collection.update_one(
                {"_id": case_id},
                {"$set": update_data}
            )

            text_length = len(extracted_data["full_text"])
            print(f"  ✓ Extracted {text_length} chars, {extracted_data['page_count']} pages")

            succeeded += 1

            # Rate limiting
            if idx < total_cases:
                time.sleep(DELAY_BETWEEN_CALLS)

        except Exception as e:
            # Mark as failed and continue
            error_msg = str(e)
            print(f"  ✗ ERROR: {error_msg}")

            cases_collection.update_one(
                {"_id": case_id},
                {"$set": {
                    "status": "extraction_failed",
                    "error": error_msg,
                    "failed_at": datetime.utcnow()
                }}
            )

            failed += 1

            # Continue processing
            if idx < total_cases:
                time.sleep(DELAY_BETWEEN_CALLS)

    # Summary
    print("\n" + "=" * 70)
    print("EXTRACTION COMPLETE")
    print("=" * 70)
    print(f"Total processed: {total_cases}")
    print(f"✓ Succeeded: {succeeded}")
    print(f"✗ Failed: {failed}")
    print("\nUpdated status in MongoDB:")
    print(f"  - text_extracted: {cases_collection.count_documents({'status': 'text_extracted'})}")
    print(f"  - extraction_failed: {cases_collection.count_documents({'status': 'extraction_failed'})}")
    print(f"  - uploaded (pending): {cases_collection.count_documents({'status': 'uploaded'})}")

    client.close()


if __name__ == "__main__":
    main()
