"""Test script to verify MongoDB data and GridFS setup."""

import os
from pathlib import Path
from dotenv import load_dotenv
from pymongo import MongoClient
from gridfs import GridFS

# Load environment variables
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

MONGODB_URI = os.environ.get("MONGODB_URI")
DATABASE_NAME = "rfe_tool"

def main():
    """Run all verification tests."""

    # Connect to MongoDB
    client = MongoClient(MONGODB_URI)
    db = client[DATABASE_NAME]
    fs = GridFS(db)
    cases = db["cases"]

    print("=" * 80)
    print("MONGODB DATA VERIFICATION TESTS")
    print("=" * 80)

    # TEST 1: Show sample case
    print("\n=== TEST 1: SAMPLE CASE ===")
    print("-" * 80)

    sample = cases.find_one({"status": "text_extracted"})

    if not sample:
        print("⚠️  No cases found with status='text_extracted'")
        print("   Checking for any cases...")
        sample = cases.find_one()

    if sample:
        print("Document ID:", sample.get("_id"))
        print("\nAll fields:")
        for key, value in sample.items():
            if key == "full_text":
                # Don't print full text here, save for TEST 2
                print(f"  {key}: <{len(value)} characters>")
            elif key == "pages":
                print(f"  {key}: <{len(value)} pages>")
            else:
                print(f"  {key}: {value}")
    else:
        print("❌ No cases found in database!")
        return

    # TEST 2: Check text quality
    print("\n=== TEST 2: TEXT QUALITY ===")
    print("-" * 80)

    if "full_text" in sample:
        full_text = sample["full_text"]
        print(f"Total text length: {len(full_text)} characters")
        print(f"\nFirst 2000 characters:\n")
        print("-" * 80)
        print(full_text[:2000])
        print("-" * 80)
        if len(full_text) > 2000:
            print(f"\n... (showing first 2000 of {len(full_text)} total characters)")
    else:
        print("❌ No 'full_text' field found in this document")

    # TEST 3: Verify PDF link works
    print("\n=== TEST 3: VERIFY PDF LINK ===")
    print("-" * 80)

    pdf_id = sample.get("pdf_id")
    filename = sample.get("filename", "unknown.pdf")

    if pdf_id:
        print(f"Fetching PDF from GridFS...")
        print(f"  PDF ID: {pdf_id}")
        print(f"  Filename: {filename}")

        try:
            # Fetch from GridFS
            pdf_file = fs.get(pdf_id)
            pdf_bytes = pdf_file.read()

            print(f"\n✓ Successfully retrieved PDF")
            print(f"  Size: {len(pdf_bytes):,} bytes ({len(pdf_bytes)/1024:.1f} KB)")

            # Save to test file
            output_path = Path(__file__).parent / "test_output.pdf"
            output_path.write_bytes(pdf_bytes)

            print(f"\n✓ Saved test PDF to: {output_path}")
            print(f"  You can open this file to verify the PDF is valid")

        except Exception as e:
            print(f"❌ Error fetching PDF: {e}")
    else:
        print("❌ No 'pdf_id' field found in document")

    # TEST 4: Collection stats
    print("\n=== TEST 4: COLLECTION STATS ===")
    print("-" * 80)

    total_cases = cases.count_documents({})
    text_extracted = cases.count_documents({"status": "text_extracted"})
    uploaded = cases.count_documents({"status": "uploaded"})
    failed = cases.count_documents({"status": "extraction_failed"})

    print(f"Total cases: {total_cases}")
    print(f"  ✓ text_extracted: {text_extracted}")
    print(f"  ⏳ uploaded (pending): {uploaded}")
    print(f"  ❌ extraction_failed: {failed}")

    # Calculate average text length
    if text_extracted > 0:
        pipeline = [
            {"$match": {"status": "text_extracted", "full_text": {"$exists": True}}},
            {"$project": {"text_length": {"$strLenCP": "$full_text"}}},
            {"$group": {"_id": None, "avg_length": {"$avg": "$text_length"}}}
        ]
        result = list(cases.aggregate(pipeline))
        if result:
            avg_length = result[0]["avg_length"]
            print(f"\nAverage full_text length: {avg_length:,.0f} characters")

    # GridFS stats
    gridfs_files = db.fs.files.count_documents({})
    gridfs_chunks = db.fs.chunks.count_documents({})

    print(f"\nGridFS:")
    print(f"  Files: {gridfs_files}")
    print(f"  Chunks: {gridfs_chunks}")

    # TEST 5: List all filenames
    print("\n=== TEST 5: ALL FILENAMES ===")
    print("-" * 80)

    all_cases = cases.find({}, {"filename": 1, "status": 1}).sort("filename", 1)

    print(f"\nAll {total_cases} files:\n")
    for i, case in enumerate(all_cases, 1):
        filename = case.get("filename", "unknown")
        status = case.get("status", "unknown")

        # Status emoji
        if status == "text_extracted":
            emoji = "✓"
        elif status == "uploaded":
            emoji = "⏳"
        elif status == "extraction_failed":
            emoji = "❌"
        else:
            emoji = "?"

        print(f"  {i:2d}. {emoji} {filename:50s} [{status}]")

    print("\n" + "=" * 80)
    print("TESTS COMPLETE")
    print("=" * 80)

    client.close()


if __name__ == "__main__":
    main()
