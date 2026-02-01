"""Main recommendation engine — orchestrates graph, search, analysis, and viz."""

import json
from pathlib import Path

from .graph_builder import GraphBuilder
from .similarity_search import SimilaritySearch
from .pattern_analyzer import PatternAnalyzer
from .visualizer import GraphVisualizer


class RecommendationEngine:
    """End-to-end H-1B appeal strategy recommendation system."""

    def __init__(self):
        self.builder = GraphBuilder()
        self.searcher = None
        self.analyzer = None
        self.visualizer = None
        self._loaded = False

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load_from_mongodb(self, uri=None, db_name="rfe_tool",
                          collection_name="cases", similarity_threshold=0.75,
                          cache_path=None):
        """Build everything from MongoDB and optionally cache to disk."""
        self.builder.load_from_mongodb(uri, db_name, collection_name)
        self.builder.build_graph(similarity_threshold)

        if cache_path:
            self.builder.save_graph(cache_path)

        self._init_components()

    def load_from_cache(self, path="h1b_graph.pkl"):
        """Load a previously persisted graph."""
        self.builder.load_graph(path)
        self._init_components()

    def _init_components(self):
        self.searcher = SimilaritySearch(self.builder.cases, self.builder.embeddings)
        self.analyzer = PatternAnalyzer(self.builder.cases, self.builder.G)
        self.visualizer = GraphVisualizer(self.builder.G, self.builder.cases)
        self._loaded = True

    # ------------------------------------------------------------------
    # Core recommendation
    # ------------------------------------------------------------------

    def recommend_strategy(self, user_profile, top_k=20, viz_path=None):
        """Generate a full strategy recommendation.

        Parameters
        ----------
        user_profile : dict
            Keys: job_title, company_type, wage_level, rfe_issues, current_arguments
        top_k : int
            Number of similar cases to consider.
        viz_path : str | None
            If set, write interactive HTML graph to this path.

        Returns
        -------
        dict  (JSON-serialisable)
        """
        if not self._loaded:
            raise RuntimeError("Call load_from_mongodb() or load_from_cache() first.")

        # 1. Find similar cases
        similar = self.searcher.find_similar_cases(user_profile, top_k=top_k)

        # 2. Argument effectiveness in the similar neighbourhood
        arg_patterns = self.analyzer.analyze_argument_patterns(similar)

        # 3. Association rules (full dataset)
        # Low support threshold needed because SUSTAINED cases are rare
        # (5/61 = 8.2% max support for any SUSTAINED rule)
        sustained_count = sum(1 for c in self.builder.cases if c.get("outcome") == "SUSTAINED")
        min_sup = max(0.03, (sustained_count / len(self.builder.cases)) * 0.5)
        assoc_rules = self.analyzer.find_association_rules(
            min_support=min_sup, min_confidence=0.4,
        )

        # 4. Counterfactual (with vs without each argument)
        counterfactuals = self.analyzer.counterfactual_analysis(similar)

        # 5. Success probability
        prob = self.analyzer.calculate_success_probability(user_profile, similar)

        # 6. Build recommendations
        recommendations = self._build_recommendations(
            user_profile, arg_patterns, counterfactuals, assoc_rules,
        )

        # 7. Risk assessment
        risk = self._assess_risk(similar, prob)

        # 8. Winning patterns
        winning = self._extract_winning_patterns(similar)

        # 9. Explanation
        explanation = self._generate_explanation(
            user_profile, similar, prob, recommendations, risk,
        )

        # 10. Visualization
        graph_viz_path = ""
        if viz_path is None:
            viz_path = str(
                Path(__file__).parent.parent / "strategy_recommendation.html"
            )
        graph_viz_path = self.visualizer.create_strategy_visualization(
            user_profile, similar, output_path=viz_path,
        )

        return {
            "similar_cases": self._slim_cases(similar[:10]),
            "success_probability": prob,
            "current_strategy_risk": risk,
            "winning_patterns": winning,
            "recommendations": recommendations,
            "association_rules": assoc_rules[:10],
            "counterfactual_analysis": counterfactuals,
            "explanation": explanation,
            "graph_viz_path": graph_viz_path,
        }

    # ------------------------------------------------------------------
    # Recommendation builder
    # ------------------------------------------------------------------

    def _build_recommendations(self, profile, arg_patterns,
                               counterfactuals, rules):
        """Rank arguments the user should ADD for highest impact."""
        user_args = set(profile.get("current_arguments", []))
        recs = []

        # Source 1: counterfactual impact
        for arg, stats in counterfactuals.items():
            if arg in user_args:
                continue  # user already has it
            if stats["impact"] > 0 and stats["with_count"] >= 2:
                recs.append({
                    "add": arg,
                    "impact": f"+{round(stats['impact'] * 100)}% success rate",
                    "impact_raw": stats["impact"],
                    "with_success_rate": stats["with_success_rate"],
                    "sample_size": stats["with_count"],
                    "confidence": stats["confidence"],
                    "source": "counterfactual",
                })

        # Source 2: high-confidence association rules
        for rule in rules:
            arg_items = [
                a.split(":", 1)[1] for a in rule["antecedent"]
                if a.startswith("arg:")
            ]
            for arg in arg_items:
                if arg in user_args:
                    continue
                # avoid duplicates
                if any(r["add"] == arg for r in recs):
                    existing = next(r for r in recs if r["add"] == arg)
                    # boost confidence if confirmed by rules
                    if rule["confidence"] > 0.7 and existing["confidence"] in ("low", "very_low"):
                        existing["confidence"] = "medium"
                    continue
                recs.append({
                    "add": arg,
                    "impact": f"appears in {round(rule['confidence'] * 100)}%-confidence winning rule",
                    "impact_raw": rule["confidence"] * 0.5,
                    "with_success_rate": rule["confidence"],
                    "sample_size": rule["sample_size"],
                    "confidence": self._conf_label(rule["sample_size"]),
                    "source": "association_rule",
                })

        recs.sort(key=lambda r: -r["impact_raw"])

        # Clean output
        for r in recs:
            del r["impact_raw"]

        return recs

    # ------------------------------------------------------------------
    # Risk assessment
    # ------------------------------------------------------------------

    @staticmethod
    def _assess_risk(similar_cases, prob_info):
        """One-line risk summary."""
        total = len(similar_cases)
        dismissed = sum(1 for c in similar_cases if c.get("outcome") == "DISMISSED")
        pct = round(dismissed / total * 100) if total else 0
        prob_pct = round(prob_info["probability"] * 100)
        return (
            f"{pct}% dismissal rate among {total} similar cases. "
            f"Estimated success probability: {prob_pct}%."
        )

    # ------------------------------------------------------------------
    # Winning patterns
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_winning_patterns(similar_cases):
        """Find argument combinations that led to SUSTAINED."""
        from collections import Counter

        sustained = [c for c in similar_cases if c.get("outcome") == "SUSTAINED"]
        if not sustained:
            return []

        combo_counter = Counter()
        for c in sustained:
            args = tuple(sorted(c.get("arguments_made", [])))
            if args:
                combo_counter[args] += 1

        patterns = []
        total_sustained = len(sustained)
        for combo, count in combo_counter.most_common(5):
            # How many dismissed cases also used this combo?
            dismissed_with = sum(
                1 for c in similar_cases
                if c.get("outcome") == "DISMISSED"
                and set(combo).issubset(set(c.get("arguments_made", [])))
            )
            total_with = count + dismissed_with
            rate = count / total_with if total_with else 0

            patterns.append({
                "arguments": list(combo),
                "success_rate": round(rate, 3),
                "sustained_count": count,
                "sample_size": total_with,
            })

        patterns.sort(key=lambda p: -p["success_rate"])
        return patterns

    # ------------------------------------------------------------------
    # Explanation generator
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_explanation(profile, similar, prob, recs, risk):
        """Human-readable explanation of the recommendation."""
        parts = []

        parts.append(
            f"Based on {len(similar)} similar H-1B AAO appeal cases, "
            f"here is the analysis for a {profile.get('job_title', 'N/A')} "
            f"position at a {profile.get('company_type', 'N/A')} company "
            f"with {profile.get('wage_level', 'N/A')}."
        )

        parts.append(f"\nRISK: {risk}")

        sustained = sum(1 for c in similar if c.get("outcome") == "SUSTAINED")
        dismissed = sum(1 for c in similar if c.get("outcome") == "DISMISSED")
        remanded = sum(1 for c in similar if c.get("outcome") == "REMANDED")
        parts.append(
            f"\nAmong similar cases: {sustained} sustained, "
            f"{dismissed} dismissed, {remanded} remanded."
        )

        if recs:
            parts.append("\nRECOMMENDED ADDITIONS to your argument strategy:")
            for i, r in enumerate(recs[:5], 1):
                parts.append(
                    f"  {i}. Add '{r['add']}' — {r['impact']} "
                    f"(confidence: {r['confidence']}, n={r['sample_size']})"
                )
        else:
            parts.append(
                "\nNo strong additional arguments identified. Your current "
                "strategy covers the most effective arguments for similar cases."
            )

        user_args = profile.get("current_arguments", [])
        if user_args:
            parts.append(
                f"\nYour current arguments ({', '.join(user_args)}) are "
                "included in the analysis. The recommendations above suggest "
                "arguments to ADD on top of your current strategy."
            )

        n = prob.get("sample_size", 0)
        if n < 5:
            parts.append(
                f"\nCAUTION: Only {n} similar cases found. These results "
                "are directional, not statistically significant."
            )

        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _slim_cases(cases):
        """Return only the fields useful in JSON output."""
        keys = [
            "case_number", "outcome", "job_title", "company_name",
            "company_type", "wage_level", "rfe_issues", "arguments_made",
            "similarity_score", "decision_date", "service_center",
        ]
        return [{k: c.get(k) for k in keys} for c in cases]

    @staticmethod
    def _conf_label(n):
        if n < 3:
            return "very_low"
        if n < 5:
            return "low"
        if n < 10:
            return "medium"
        if n < 20:
            return "high"
        return "very_high"

    # ------------------------------------------------------------------
    # Lightweight graph data for frontend SVG visualization
    # ------------------------------------------------------------------

    def get_graph_data(self, user_profile=None, top_k_highlight=20):
        """Return node/edge data for the frontend graph animation.

        Much faster than recommend_strategy() — reads from the in-memory
        graph without running pattern mining or counterfactual analysis.
        """
        if not self._loaded:
            raise RuntimeError("Engine not loaded")

        # 1. All case nodes
        nodes = []
        for case in self.builder.cases:
            nodes.append({
                "id": case["index"],
                "x": case.get("x_2d", 0.0),
                "y": case.get("y_2d", 0.0),
                "outcome": case.get("outcome", "UNKNOWN"),
                "job_title": case.get("job_title") or "",
                "company_type": case.get("company_type") or "",
                "wage_level": case.get("wage_level") or "",
                "case_number": case.get("case_number") or "",
                "arguments_made": case.get("arguments_made", []),
            })

        # 2. Deduplicated SIMILAR_TO edges
        edges = []
        seen = set()
        for u, v, data in self.builder.G.edges(data=True):
            if data.get("edge_type") != "SIMILAR_TO":
                continue
            if not (str(u).startswith("case_") and str(v).startswith("case_")):
                continue
            u_idx = int(str(u).split("_")[1])
            v_idx = int(str(v).split("_")[1])
            pair = (min(u_idx, v_idx), max(u_idx, v_idx))
            if pair in seen:
                continue
            seen.add(pair)
            edges.append({
                "source": pair[0],
                "target": pair[1],
                "weight": round(data.get("weight", 0), 3),
            })

        # 3. User node position + similar case IDs
        similar_ids = []
        user_x, user_y = 0.0, 0.0

        if user_profile and self.searcher:
            similar = self.searcher.find_similar_cases(
                user_profile, top_k=top_k_highlight,
            )
            similar_ids = [c["index"] for c in similar]

            top_5 = similar[:5]
            if top_5:
                weights = [c.get("similarity_score", 0.5) for c in top_5]
                total_w = sum(weights) or 1.0
                user_x = sum(
                    c.get("x_2d", 0) * w for c, w in zip(top_5, weights)
                ) / total_w
                user_y = sum(
                    c.get("y_2d", 0) * w for c, w in zip(top_5, weights)
                ) / total_w
        else:
            if nodes:
                user_x = sum(n["x"] for n in nodes) / len(nodes)
                user_y = sum(n["y"] for n in nodes) / len(nodes)

        return {
            "nodes": nodes,
            "edges": edges,
            "user_node": {"x": round(user_x, 4), "y": round(user_y, 4)},
            "similar_ids": similar_ids,
        }
