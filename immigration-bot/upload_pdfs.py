"""Upload PDF files from local folder to MongoDB GridFS."""

import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from pymongo import MongoClient
from gridfs import GridFS

# Load environment variables
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

MONGODB_URI = os.environ.get("MONGODB_URI")
if not MONGODB_URI:
    raise EnvironmentError(f"MONGODB_URI not found in {env_path}")

# Configuration
PDF_FOLDER = Path("/Users/ranax/Downloads/usics")
DATABASE_NAME = "rfe_tool"

def upload_pdfs():
    """Upload all PDFs from local folder to MongoDB GridFS."""

    # Connect to MongoDB
    print(f"Connecting to MongoDB...")
    client = MongoClient(MONGODB_URI)
    db = client[DATABASE_NAME]
    fs = GridFS(db)
    cases_collection = db["cases"]

    print(f"Connected to database: {DATABASE_NAME}")
    print(f"Scanning folder: {PDF_FOLDER}")
    print("-" * 60)

    # Get all PDF files
    pdf_files = sorted(PDF_FOLDER.glob("*.pdf"))
    total_files = len(pdf_files)

    if total_files == 0:
        print("No PDF files found!")
        return

    print(f"Found {total_files} PDF files\n")

    uploaded_count = 0

    # Upload each PDF
    for idx, pdf_path in enumerate(pdf_files, 1):
        filename = pdf_path.name

        try:
            # Read PDF file
            with open(pdf_path, "rb") as pdf_file:
                pdf_data = pdf_file.read()

            # Upload to GridFS
            pdf_id = fs.put(
                pdf_data,
                filename=filename,
                content_type="application/pdf"
            )

            # Create document in cases collection
            case_doc = {
                "filename": filename,
                "pdf_id": pdf_id,
                "status": "uploaded",
                "uploaded_at": datetime.utcnow()
            }
            cases_collection.insert_one(case_doc)

            # Print progress
            file_size = len(pdf_data) / 1024  # KB
            print(f"[{idx}/{total_files}] ✓ {filename} ({file_size:.1f} KB)")

            uploaded_count += 1

        except Exception as e:
            print(f"[{idx}/{total_files}] ✗ {filename} - ERROR: {e}")

    print("\n" + "-" * 60)
    print(f"Upload complete!")
    print(f"Total files uploaded: {uploaded_count}/{total_files}")
    print(f"Database: {DATABASE_NAME}")
    print(f"GridFS files: {db.fs.files.count_documents({})}")
    print(f"Cases collection: {cases_collection.count_documents({})}")

    # Close connection
    client.close()


if __name__ == "__main__":
    upload_pdfs()
