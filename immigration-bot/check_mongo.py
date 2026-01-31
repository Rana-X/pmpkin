"""Quick script to view MongoDB GridFS data."""

import os
from pathlib import Path
from dotenv import load_dotenv
from pymongo import MongoClient

# Load environment variables
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

MONGODB_URI = os.environ.get("MONGODB_URI")
client = MongoClient(MONGODB_URI)
db = client["rfe_tool"]

print("=" * 70)
print("MONGODB DATABASE: rfe_tool")
print("=" * 70)

# Show cases collection
print("\n📁 CASES COLLECTION:")
print("-" * 70)
cases = db["cases"].find().limit(5)
for i, case in enumerate(cases, 1):
    print(f"{i}. {case['filename']}")
    print(f"   PDF ID: {case['pdf_id']}")
    print(f"   Status: {case['status']}")
    print(f"   Uploaded: {case['uploaded_at']}")
    print()

total_cases = db["cases"].count_documents({})
print(f"Total cases: {total_cases}")

# Show GridFS files
print("\n📄 GRIDFS FILES (fs.files):")
print("-" * 70)
files = db.fs.files.find().limit(5)
for i, file in enumerate(files, 1):
    size_kb = file['length'] / 1024
    print(f"{i}. {file['filename']}")
    print(f"   ID: {file['_id']}")
    print(f"   Size: {size_kb:.1f} KB")
    print(f"   Upload Date: {file.get('uploadDate', 'N/A')}")
    print()

total_files = db.fs.files.count_documents({})
print(f"Total GridFS files: {total_files}")

# Show collections
print("\n📊 ALL COLLECTIONS IN DATABASE:")
print("-" * 70)
for collection_name in db.list_collection_names():
    count = db[collection_name].count_documents({})
    print(f"  • {collection_name}: {count} documents")

print("\n" + "=" * 70)

client.close()
