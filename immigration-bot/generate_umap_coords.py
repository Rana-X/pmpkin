"""Generate 2D UMAP coordinates for case visualization."""

import os
import pickle
from pathlib import Path
from dotenv import load_dotenv

import numpy as np
from pymongo import MongoClient
import umap

# Load environment variables
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

MONGODB_URI = os.environ.get("MONGODB_URI")
DATABASE_NAME = "rfe_tool"

# UMAP parameters
UMAP_PARAMS = {
    "n_neighbors": 15,
    "min_dist": 0.1,
    "metric": "cosine",
    "random_state": 42
}

def main():
    """Main UMAP coordinate generation pipeline."""

    print("=" * 80)
    print("UMAP 2D COORDINATE GENERATION")
    print("=" * 80)

    # Connect to MongoDB
    print(f"\nConnecting to MongoDB...")
    client = MongoClient(MONGODB_URI)
    db = client[DATABASE_NAME]
    cases_collection = db["cases"]

    # Fetch all embedded cases
    print(f"\nFetching cases with embeddings...")
    query = {"status": "embedded", "embedding": {"$exists": True}}
    cases = list(cases_collection.find(query))

    if len(cases) == 0:
        print("\n❌ No cases found with embeddings!")
        print("   Run generate_embeddings_openai.py first")
        client.close()
        return

    total_cases = len(cases)
    print(f"Found {total_cases} cases with embeddings")

    # Extract embeddings and case IDs
    print(f"\nExtracting embeddings into numpy array...")
    embeddings = np.array([c["embedding"] for c in cases])
    case_ids = [c["_id"] for c in cases]
    filenames = [c.get("filename", "unknown") for c in cases]

    print(f"Embedding matrix shape: {embeddings.shape}")
    print(f"Dimensions: {embeddings.shape[1]}")

    # Run UMAP
    print(f"\nRunning UMAP dimensionality reduction...")
    print(f"Parameters:")
    for key, value in UMAP_PARAMS.items():
        print(f"  - {key}: {value}")

    reducer = umap.UMAP(**UMAP_PARAMS)
    coords_2d = reducer.fit_transform(embeddings)

    print(f"\n✓ UMAP complete!")
    print(f"2D coordinates shape: {coords_2d.shape}")
    print(f"X range: [{coords_2d[:, 0].min():.2f}, {coords_2d[:, 0].max():.2f}]")
    print(f"Y range: [{coords_2d[:, 1].min():.2f}, {coords_2d[:, 1].max():.2f}]")

    # Update MongoDB with 2D coordinates
    print(f"\nUpdating MongoDB with 2D coordinates...")
    for i, case_id in enumerate(case_ids):
        cases_collection.update_one(
            {"_id": case_id},
            {"$set": {
                "x_2d": float(coords_2d[i, 0]),
                "y_2d": float(coords_2d[i, 1]),
                "status": "complete"
            }}
        )

        if (i + 1) % 10 == 0 or (i + 1) == total_cases:
            print(f"  Updated {i + 1}/{total_cases} cases")

    # Save UMAP model for projecting new cases later
    model_path = Path(__file__).parent / "umap_model.pkl"
    print(f"\nSaving UMAP model to: {model_path}")
    with open(model_path, "wb") as f:
        pickle.dump(reducer, f)

    print(f"✓ UMAP model saved!")

    # Summary
    print("\n" + "=" * 80)
    print("UMAP GENERATION COMPLETE")
    print("=" * 80)
    print(f"Total cases processed: {total_cases}")
    print(f"All cases now have x_2d, y_2d coordinates")
    print(f"Status updated to: complete")

    # Show sample coordinates
    print("\n" + "-" * 80)
    print("SAMPLE COORDINATES (first 10 cases):")
    print("-" * 80)
    print(f"\n{'Filename':<40} {'X':<12} {'Y':<12}")
    print("-" * 80)

    for i in range(min(10, total_cases)):
        filename = filenames[i]
        x = coords_2d[i, 0]
        y = coords_2d[i, 1]
        print(f"{filename:<40} {x:>11.4f} {y:>11.4f}")

    # Distribution stats
    print("\n" + "-" * 80)
    print("COORDINATE DISTRIBUTION:")
    print("-" * 80)
    print(f"X: mean={coords_2d[:, 0].mean():.4f}, std={coords_2d[:, 0].std():.4f}")
    print(f"Y: mean={coords_2d[:, 1].mean():.4f}, std={coords_2d[:, 1].std():.4f}")

    # Verify in MongoDB
    print("\n" + "-" * 80)
    print("MONGODB VERIFICATION:")
    print("-" * 80)
    complete_count = cases_collection.count_documents({"status": "complete"})
    with_coords = cases_collection.count_documents({
        "x_2d": {"$exists": True},
        "y_2d": {"$exists": True}
    })

    print(f"Cases with status='complete': {complete_count}")
    print(f"Cases with x_2d, y_2d coordinates: {with_coords}")

    print("\n" + "=" * 80)
    print("✓ READY FOR VISUALIZATION!")
    print("=" * 80)
    print("\nNext steps:")
    print("  1. Use x_2d, y_2d coordinates to visualize cases in 2D space")
    print("  2. Load umap_model.pkl to project new cases into same space")
    print("  3. Color points by outcome, wage_level, or other features")

    client.close()


if __name__ == "__main__":
    main()
