"""CLI interface for the H-1B AAO Appeal Strategy Recommendation System."""

import os
import sys
import json
import argparse
from pathlib import Path

# Allow running as script from inside the package
sys.path.insert(0, str(Path(__file__).parent.parent))

from immigration_strategy.strategy_engine import RecommendationEngine

CACHE_PATH = str(Path(__file__).parent / "h1b_graph.pkl")


def cmd_build(args):
    """Build the knowledge graph from MongoDB and cache it."""
    engine = RecommendationEngine()
    engine.load_from_mongodb(
        uri=args.uri,
        db_name=args.db,
        collection_name=args.collection,
        similarity_threshold=args.threshold,
        cache_path=CACHE_PATH,
    )
    print(f"\nGraph cached to {CACHE_PATH}")


def cmd_recommend(args):
    """Run a recommendation for a user profile."""
    engine = RecommendationEngine()

    if os.path.exists(CACHE_PATH):
        print(f"Loading cached graph from {CACHE_PATH} ...")
        engine.load_from_cache(CACHE_PATH)
    else:
        print("No cache found — building from MongoDB ...")
        engine.load_from_mongodb(cache_path=CACHE_PATH)

    # Build profile from CLI args or use example
    if args.job_title:
        profile = {
            "job_title": args.job_title,
            "company_type": args.company_type or "unknown",
            "wage_level": args.wage_level or "",
            "rfe_issues": [x.strip() for x in args.rfe_issues.split(",")] if args.rfe_issues else [],
            "current_arguments": [x.strip() for x in args.arguments.split(",")] if args.arguments else [],
        }
    else:
        # Default example profile
        profile = {
            "job_title": "Data Engineer",
            "company_type": "consulting",
            "wage_level": "Level II",
            "rfe_issues": ["wage_level", "specialty_occupation"],
            "current_arguments": ["onet_citation"],
        }
        print("\nUsing example profile (pass --job-title to customise):")
        print(json.dumps(profile, indent=2))

    print("\nGenerating recommendations ...\n")
    result = engine.recommend_strategy(profile, viz_path=args.output)

    # Pretty-print results
    print("=" * 70)
    print("STRATEGY RECOMMENDATION")
    print("=" * 70)

    print(f"\n{result['explanation']}")

    print("\n" + "-" * 70)
    print("SUCCESS PROBABILITY")
    print("-" * 70)
    prob = result["success_probability"]
    print(f"  Estimated: {prob['probability']:.0%}  "
          f"(base: {prob['base_probability']:.0%}, "
          f"argument boost: +{prob['argument_boost']:.0%})")
    print(f"  Confidence: {prob['confidence']}  |  "
          f"Sample: {prob['sample_size']} similar cases "
          f"({prob['sustained_in_similar']} sustained)")

    print("\n" + "-" * 70)
    print("TOP RECOMMENDATIONS")
    print("-" * 70)
    for i, rec in enumerate(result["recommendations"][:5], 1):
        print(f"  {i}. ADD '{rec['add']}'")
        print(f"     Impact: {rec['impact']}")
        print(f"     Confidence: {rec['confidence']}  |  Sample: {rec['sample_size']}")
        print()

    if result["winning_patterns"]:
        print("-" * 70)
        print("WINNING ARGUMENT COMBINATIONS")
        print("-" * 70)
        for p in result["winning_patterns"][:3]:
            args_str = " + ".join(p["arguments"])
            print(f"  {args_str}")
            print(f"    Success rate: {p['success_rate']:.0%}  |  "
                  f"Sample: {p['sample_size']}")
            print()

    print("-" * 70)
    print(f"Similar cases: {len(result['similar_cases'])}")
    for c in result["similar_cases"][:5]:
        cnum = c.get("case_number") or "N/A"
        jtitle = c.get("job_title") or "N/A"
        out = c.get("outcome") or "?"
        sim = c.get("similarity_score") or 0
        print(f"  [{out}] {cnum} — {jtitle} (sim={sim:.2f})")

    print(f"\nVisualization: {result['graph_viz_path']}")

    # Also dump full JSON
    json_path = str(Path(__file__).parent.parent / "strategy_result.json")
    with open(json_path, "w") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"Full JSON: {json_path}")


def main():
    parser = argparse.ArgumentParser(
        description="H-1B AAO Appeal Strategy Recommendation System"
    )
    sub = parser.add_subparsers(dest="command")

    # --- build ---
    build_p = sub.add_parser("build", help="Build knowledge graph from MongoDB")
    build_p.add_argument("--uri", default=None, help="MongoDB URI (or MONGODB_URI env)")
    build_p.add_argument("--db", default="rfe_tool", help="Database name")
    build_p.add_argument("--collection", default="cases", help="Collection name")
    build_p.add_argument("--threshold", type=float, default=0.92,
                         help="Cosine similarity threshold for SIMILAR_TO edges")

    # --- recommend ---
    rec_p = sub.add_parser("recommend", help="Get strategy recommendation")
    rec_p.add_argument("--job-title", default=None, help="Job title")
    rec_p.add_argument("--company-type", default=None,
                       help="consulting | staffing | direct_employer")
    rec_p.add_argument("--wage-level", default=None,
                       help="Level I | Level II | Level III | Level IV")
    rec_p.add_argument("--rfe-issues", default=None,
                       help="Comma-separated RFE issues")
    rec_p.add_argument("--arguments", default=None,
                       help="Comma-separated current arguments")
    rec_p.add_argument("--output", default=None,
                       help="Path for HTML visualization")

    args = parser.parse_args()

    if args.command == "build":
        cmd_build(args)
    elif args.command == "recommend":
        cmd_recommend(args)
    else:
        parser.print_help()
        print("\nQuick start:")
        print("  python -m immigration_strategy.main build")
        print("  python -m immigration_strategy.main recommend")
        print("  python -m immigration_strategy.main recommend "
              '--job-title "Software Engineer" '
              "--company-type consulting "
              '--wage-level "Level II" '
              "--rfe-issues specialty_occupation,wage_level "
              "--arguments onet_citation,expert_letter")


if __name__ == "__main__":
    main()
