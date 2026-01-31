"""Export case data for UMAP visualization."""

import os
import json
from pathlib import Path
from dotenv import load_dotenv
from pymongo import MongoClient

# Load environment variables
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

MONGODB_URI = os.environ.get("MONGODB_URI")
DATABASE_NAME = "rfe_tool"

def main():
    """Export case data to JSON for visualization."""

    print("Exporting case data for visualization...")

    # Connect to MongoDB
    client = MongoClient(MONGODB_URI)
    db = client[DATABASE_NAME]
    cases_collection = db["cases"]

    # Fetch all complete cases
    query = {"status": "complete", "x_2d": {"$exists": True}, "y_2d": {"$exists": True}}
    cases = list(cases_collection.find(query))

    if len(cases) == 0:
        print("No complete cases found!")
        client.close()
        return

    # Extract visualization data
    viz_data = []
    for case in cases:
        viz_data.append({
            "filename": case.get("filename", "unknown"),
            "x": case.get("x_2d"),
            "y": case.get("y_2d"),
            "case_number": case.get("case_number"),
            "outcome": case.get("outcome"),
            "decision_date": case.get("decision_date"),
            "job_title": case.get("job_title"),
            "company_name": case.get("company_name"),
            "company_type": case.get("company_type"),
            "wage_level": case.get("wage_level"),
            "service_center": case.get("service_center"),
            "rfe_issues": case.get("rfe_issues", []),
            "denial_reasons": case.get("denial_reasons", []),
        })

    # Save to JSON
    output_path = Path(__file__).parent / "umap_data.json"
    with open(output_path, "w") as f:
        json.dump(viz_data, f, indent=2)

    print(f"✓ Exported {len(viz_data)} cases to: {output_path}")

    # Print summary
    outcomes = {}
    for case in viz_data:
        outcome = case.get("outcome", "UNKNOWN")
        outcomes[outcome] = outcomes.get(outcome, 0) + 1

    print(f"\nOutcome distribution:")
    for outcome, count in sorted(outcomes.items()):
        print(f"  - {outcome}: {count}")

    client.close()


if __name__ == "__main__":
    main()
