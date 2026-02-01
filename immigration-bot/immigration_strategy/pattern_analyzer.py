"""Pattern mining, association rules, and counterfactual analysis."""

import warnings
from collections import defaultdict

import numpy as np
import pandas as pd

try:
    from mlxtend.frequent_patterns import apriori, association_rules
    from mlxtend.preprocessing import TransactionEncoder
    HAS_MLXTEND = True
except ImportError:
    HAS_MLXTEND = False


class PatternAnalyzer:
    """Mines patterns from H-1B case data and the knowledge graph."""

    def __init__(self, cases, graph=None):
        self.cases = cases
        self.G = graph

    # ------------------------------------------------------------------
    # 1. Argument effectiveness for a set of similar cases
    # ------------------------------------------------------------------

    def analyze_argument_patterns(self, similar_cases):
        """Which arguments correlate with SUSTAINED vs DISMISSED?

        Returns dict keyed by argument name with success stats.
        """
        arg_stats = defaultdict(lambda: {"sustained": 0, "dismissed": 0, "remanded": 0, "total": 0})

        for c in similar_cases:
            outcome = (c.get("outcome") or "").upper()
            for arg in c.get("arguments_made", []):
                arg_stats[arg]["total"] += 1
                if outcome == "SUSTAINED":
                    arg_stats[arg]["sustained"] += 1
                elif outcome == "DISMISSED":
                    arg_stats[arg]["dismissed"] += 1
                elif outcome == "REMANDED":
                    arg_stats[arg]["remanded"] += 1

        results = {}
        for arg, stats in arg_stats.items():
            total = stats["total"]
            success_rate = stats["sustained"] / total if total else 0
            results[arg] = {
                "success_rate": round(success_rate, 3),
                "sustained": stats["sustained"],
                "dismissed": stats["dismissed"],
                "remanded": stats["remanded"],
                "total": total,
                "confidence": self._confidence_label(total),
            }

        # Sort by success rate descending
        return dict(sorted(results.items(), key=lambda x: -x[1]["success_rate"]))

    # ------------------------------------------------------------------
    # 2. Association rule mining (full dataset)
    # ------------------------------------------------------------------

    def find_association_rules(self, min_support=0.1, min_confidence=0.5):
        """Apriori association rules across the full case set.

        Returns list of rule dicts, filtered for SUSTAINED consequent.
        """
        if not HAS_MLXTEND:
            return self._fallback_rules(min_confidence)

        transactions = []
        for c in self.cases:
            items = set()
            ct = c.get("company_type")
            if ct:
                items.add(f"comptype:{ct}")
            wl = c.get("wage_level")
            if wl:
                items.add(f"wage:{wl}")
            for rfe in c.get("rfe_issues", []):
                items.add(f"rfe:{rfe}")
            for arg in c.get("arguments_made", []):
                items.add(f"arg:{arg}")
            items.add(f"outcome:{c.get('outcome', 'UNKNOWN')}")
            transactions.append(list(items))

        te = TransactionEncoder()
        te_ary = te.fit(transactions).transform(transactions)
        df = pd.DataFrame(te_ary, columns=te.columns_)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            freq = apriori(df, min_support=min_support, use_colnames=True)

        if freq.empty:
            return []

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            rules = association_rules(
                freq, metric="confidence", min_threshold=min_confidence,
                num_itemsets=len(freq),
            )

        # Keep only rules predicting SUSTAINED
        sustained_rules = rules[
            rules["consequents"].apply(lambda s: "outcome:SUSTAINED" in s)
        ].copy()

        results = []
        for _, row in sustained_rules.iterrows():
            antecedent = sorted(row["consequents"] if False else row["antecedents"])
            results.append({
                "antecedent": antecedent,
                "confidence": round(float(row["confidence"]), 3),
                "support": round(float(row["support"]), 3),
                "lift": round(float(row["lift"]), 3),
                "sample_size": int(round(row["support"] * len(self.cases))),
            })

        results.sort(key=lambda r: -r["confidence"])
        return results

    def _fallback_rules(self, min_confidence):
        """Simple co-occurrence rules when mlxtend is not installed."""
        combo_stats = defaultdict(lambda: {"sustained": 0, "total": 0})
        for c in self.cases:
            outcome = c.get("outcome", "")
            features = []
            ct = c.get("company_type")
            if ct:
                features.append(f"comptype:{ct}")
            for arg in c.get("arguments_made", []):
                features.append(f"arg:{arg}")
            for rfe in c.get("rfe_issues", []):
                features.append(f"rfe:{rfe}")

            # Singles and pairs
            for f in features:
                combo_stats[(f,)]["total"] += 1
                if outcome == "SUSTAINED":
                    combo_stats[(f,)]["sustained"] += 1
            for i in range(len(features)):
                for j in range(i + 1, len(features)):
                    key = tuple(sorted([features[i], features[j]]))
                    combo_stats[key]["total"] += 1
                    if outcome == "SUSTAINED":
                        combo_stats[key]["sustained"] += 1

        results = []
        for combo, stats in combo_stats.items():
            if stats["total"] < 2:
                continue
            conf = stats["sustained"] / stats["total"]
            if conf >= min_confidence:
                results.append({
                    "antecedent": list(combo),
                    "confidence": round(conf, 3),
                    "support": round(stats["total"] / len(self.cases), 3),
                    "lift": 0.0,
                    "sample_size": stats["total"],
                })
        results.sort(key=lambda r: -r["confidence"])
        return results

    # ------------------------------------------------------------------
    # 3. Counterfactual analysis
    # ------------------------------------------------------------------

    def counterfactual_analysis(self, cases_subset=None):
        """For each argument: compare success rate WITH vs WITHOUT.

        Returns dict keyed by argument.
        """
        cases = cases_subset or self.cases

        all_args = set()
        for c in cases:
            all_args.update(c.get("arguments_made", []))

        results = {}
        for arg in sorted(all_args):
            with_arg = [c for c in cases if arg in (c.get("arguments_made") or [])]
            without_arg = [c for c in cases if arg not in (c.get("arguments_made") or [])]

            with_sust = sum(1 for c in with_arg if c.get("outcome") == "SUSTAINED")
            wo_sust = sum(1 for c in without_arg if c.get("outcome") == "SUSTAINED")

            with_rate = with_sust / len(with_arg) if with_arg else 0
            wo_rate = wo_sust / len(without_arg) if without_arg else 0

            results[arg] = {
                "with_count": len(with_arg),
                "without_count": len(without_arg),
                "with_success_rate": round(with_rate, 3),
                "without_success_rate": round(wo_rate, 3),
                "impact": round(with_rate - wo_rate, 3),
                "confidence": self._confidence_label(len(with_arg)),
            }

        return dict(sorted(results.items(), key=lambda x: -x[1]["impact"]))

    # ------------------------------------------------------------------
    # 4. Success probability for a user profile
    # ------------------------------------------------------------------

    def calculate_success_probability(self, user_profile, similar_cases):
        """Estimate P(SUSTAINED) given the user's profile and similar cases.

        Uses weighted average of similar-case outcomes plus argument boost.
        """
        if not similar_cases:
            return {"probability": 0.0, "basis": "no similar cases", "sample_size": 0}

        # Weighted by similarity score
        weights = np.array([c.get("similarity_score", 0.5) for c in similar_cases])
        outcomes = np.array([1.0 if c.get("outcome") == "SUSTAINED" else 0.0 for c in similar_cases])

        if weights.sum() == 0:
            base_prob = float(outcomes.mean())
        else:
            base_prob = float(np.average(outcomes, weights=weights))

        # Argument boost: if user has args that correlate with success
        counterfactuals = self.counterfactual_analysis(similar_cases)
        user_args = set(user_profile.get("current_arguments", []))
        boost = 0.0
        for arg in user_args:
            if arg in counterfactuals:
                impact = counterfactuals[arg]["impact"]
                if impact > 0:
                    boost += impact * 0.3  # dampen the boost

        adjusted = min(1.0, max(0.0, base_prob + boost))

        sustained = int(outcomes.sum())
        total = len(similar_cases)

        return {
            "probability": round(adjusted, 3),
            "base_probability": round(base_prob, 3),
            "argument_boost": round(boost, 3),
            "sustained_in_similar": sustained,
            "sample_size": total,
            "confidence": self._confidence_label(total),
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _confidence_label(n):
        if n < 3:
            return "very_low"
        if n < 5:
            return "low"
        if n < 10:
            return "medium"
        if n < 20:
            return "high"
        return "very_high"
