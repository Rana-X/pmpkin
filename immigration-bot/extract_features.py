"""Extract structured features from H-1B AAO decisions using GPT-4."""

import os
import time
import json
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
MODEL = "gpt-4o"  # or "gpt-4o-mini" for lower cost
TEMPERATURE = 0  # deterministic

# GPT-4 extraction prompt
EXTRACTION_PROMPT = """Extract the following from this AAO H-1B appeal decision.
Return ONLY valid JSON, no explanation or markdown.

{
  "case_number": "WAC/EAC/LIN/SRC number or null",
  "outcome": "DISMISSED or SUSTAINED or REMANDED",
  "decision_date": "YYYY-MM-DD or null",
  "service_center": "California or Nebraska or Texas or Vermont or null",
  "job_title": "exact job title or null",
  "company_name": "petitioner company name or null",
  "company_type": "consulting or staffing or direct_employer or unknown",
  "wage_level": "Level I or Level II or Level III or Level IV or null",
  "rfe_issues": ["array of issues from: specialty_occupation, wage_level, employer_employee, beneficiary_qualifications, itinerary, maintenance_of_status, other"],
  "denial_reasons": ["short array of specific denial reasons"],
  "arguments_made": ["array from: expert_letter, onet_citation, prior_approvals, industry_standards, degree_evaluation, other"]
}"""


def extract_features_with_gpt4(full_text, openai_client, max_retries=2):
    """Extract structured features from decision text using GPT-4.

    Returns:
        dict: Extracted features or None if failed
    """
    for attempt in range(max_retries):
        try:
            response = openai_client.chat.completions.create(
                model=MODEL,
                temperature=TEMPERATURE,
                max_tokens=1000,
                messages=[
                    {"role": "system", "content": "You are a legal document analyzer that extracts structured data from H-1B appeal decisions."},
                    {"role": "user", "content": f"{EXTRACTION_PROMPT}\n\n---\n\nDecision Text:\n{full_text}"}
                ]
            )

            # Get response content
            content = response.choices[0].message.content.strip()

            # Remove markdown code blocks if present
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            # Parse JSON
            features = json.loads(content)

            return features

        except json.JSONDecodeError as e:
            if attempt < max_retries - 1:
                print(f"    ⚠️  JSON parse error (attempt {attempt + 1}/{max_retries}): {e}")
                time.sleep(1)
                continue
            else:
                print(f"    ❌ Failed to parse JSON after {max_retries} attempts")
                return None

        except Exception as e:
            print(f"    ❌ GPT-4 API error: {e}")
            return None

    return None


def main():
    """Main feature extraction pipeline."""

    print("=" * 80)
    print("GPT-4 FEATURE EXTRACTION PIPELINE")
    print("=" * 80)

    # Connect to MongoDB
    print(f"\nConnecting to MongoDB...")
    client = MongoClient(MONGODB_URI)
    db = client[DATABASE_NAME]
    cases_collection = db["cases"]

    # Initialize OpenAI client
    openai_client = OpenAI(api_key=OPENAI_API_KEY)

    # Get all cases that need feature extraction
    query = {"status": "text_extracted"}
    cases_to_process = list(cases_collection.find(query))
    total_cases = len(cases_to_process)

    if total_cases == 0:
        print("\n✓ No cases found with status='text_extracted'")
        print("  All cases may already be processed!")
        client.close()
        return

    print(f"\nFound {total_cases} cases to process")
    print(f"Using model: {MODEL}")
    print(f"Temperature: {TEMPERATURE}")
    print("\n" + "-" * 80)

    succeeded = 0
    failed = 0

    # Process each case
    for idx, case in enumerate(tqdm(cases_to_process, desc="Extracting features"), 1):
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

            # Extract features with GPT-4
            features = extract_features_with_gpt4(full_text, openai_client)

            if features is None:
                # Mark as failed
                cases_collection.update_one(
                    {"_id": case_id},
                    {"$set": {
                        "status": "feature_extraction_failed",
                        "failed_at": datetime.utcnow()
                    }}
                )
                failed += 1
                continue

            # Update MongoDB with extracted features
            update_data = {
                **features,  # Spread all extracted fields
                "status": "features_extracted",
                "features_extracted_at": datetime.utcnow()
            }

            cases_collection.update_one(
                {"_id": case_id},
                {"$set": update_data}
            )

            # Print result
            outcome = features.get("outcome", "UNKNOWN")
            case_num = features.get("case_number", "N/A")
            print(f"  ✓ {outcome} - {case_num}")

            succeeded += 1

            # Rate limiting
            if idx < total_cases:
                time.sleep(DELAY_BETWEEN_CALLS)

        except Exception as e:
            print(f"  ❌ Unexpected error: {e}")

            cases_collection.update_one(
                {"_id": case_id},
                {"$set": {
                    "status": "feature_extraction_failed",
                    "error": str(e),
                    "failed_at": datetime.utcnow()
                }}
            )

            failed += 1

            if idx < total_cases:
                time.sleep(DELAY_BETWEEN_CALLS)

    # Summary
    print("\n" + "=" * 80)
    print("FEATURE EXTRACTION COMPLETE")
    print("=" * 80)
    print(f"Total processed: {total_cases}")
    print(f"✓ Succeeded: {succeeded}")
    print(f"❌ Failed: {failed}")
    print("\nUpdated status in MongoDB:")
    print(f"  - features_extracted: {cases_collection.count_documents({'status': 'features_extracted'})}")
    print(f"  - feature_extraction_failed: {cases_collection.count_documents({'status': 'feature_extraction_failed'})}")
    print(f"  - text_extracted (pending): {cases_collection.count_documents({'status': 'text_extracted'})}")

    # Show sample extracted features
    if succeeded > 0:
        print("\n" + "-" * 80)
        print("SAMPLE EXTRACTED FEATURES:")
        print("-" * 80)
        sample = cases_collection.find_one({"status": "features_extracted"})
        if sample:
            print(f"\nFilename: {sample.get('filename')}")
            print(f"Case Number: {sample.get('case_number')}")
            print(f"Outcome: {sample.get('outcome')}")
            print(f"Decision Date: {sample.get('decision_date')}")
            print(f"Job Title: {sample.get('job_title')}")
            print(f"Company: {sample.get('company_name')}")
            print(f"Company Type: {sample.get('company_type')}")
            print(f"Wage Level: {sample.get('wage_level')}")
            print(f"RFE Issues: {sample.get('rfe_issues')}")
            print(f"Denial Reasons: {sample.get('denial_reasons')}")
            print(f"Arguments Made: {sample.get('arguments_made')}")

    client.close()


if __name__ == "__main__":
    main()
