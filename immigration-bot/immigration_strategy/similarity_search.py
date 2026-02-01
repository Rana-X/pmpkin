"""Find similar H-1B cases using combined metadata + embedding similarity."""

import warnings
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

warnings.filterwarnings("ignore", category=RuntimeWarning, module="sklearn")


class SimilaritySearch:
    """Finds cases most similar to a user's profile."""

    def __init__(self, cases, embeddings):
        self.cases = cases
        self.embeddings = embeddings

    # --- Public API ---

    def find_similar_cases(self, user_profile, top_k=20):
        """Find the top-k most similar cases to user_profile.

        user_profile keys: job_title, company_type, wage_level,
                           rfe_issues (list), current_arguments (list)

        Returns list of case dicts augmented with 'similarity_score'.
        """
        # Step 1: score every case by metadata similarity
        meta_scores = np.array([
            self._metadata_similarity(user_profile, c) for c in self.cases
        ])

        # Step 2: build a synthetic query embedding from top metadata matches
        top_meta_idx = np.argsort(meta_scores)[-min(10, len(self.cases)):]
        centroid = self.embeddings[top_meta_idx].mean(axis=0, keepdims=True)

        # Step 3: cosine similarity of centroid vs all embeddings
        emb_scores = cosine_similarity(centroid, self.embeddings)[0]

        # Step 4: combined score  (60% metadata, 40% embedding)
        # Replace any NaN from embedding issues with 0
        emb_scores = np.nan_to_num(emb_scores, nan=0.0)
        combined = 0.6 * meta_scores + 0.4 * emb_scores

        # Step 5: rank, deduplicate, and return top_k
        ranked_idx = np.argsort(combined)[::-1]

        results = []
        seen_cases = set()
        for idx in ranked_idx:
            case_num = self.cases[idx].get("case_number") or ""
            job = self.cases[idx].get("job_title") or ""
            # Dedup by case_number if available, otherwise by index
            dedup_key = case_num if case_num else str(idx)
            if dedup_key in seen_cases:
                continue
            seen_cases.add(dedup_key)

            case = dict(self.cases[idx])
            case["similarity_score"] = round(float(combined[idx]), 4)
            case["metadata_score"] = round(float(meta_scores[idx]), 4)
            case["embedding_score"] = round(float(emb_scores[idx]), 4)
            results.append(case)

            if len(results) >= top_k:
                break

        return results

    # --- Metadata similarity components ---

    def _metadata_similarity(self, profile, case):
        """Weighted combination of per-field similarity scores."""
        scores = []
        weights = []

        # Job title (Jaccard on tokens) — weight 0.30
        if profile.get("job_title") and case.get("job_title"):
            scores.append(self._job_title_sim(profile["job_title"], case["job_title"]))
            weights.append(0.30)

        # Company type (exact match) — weight 0.20
        if profile.get("company_type") and case.get("company_type"):
            scores.append(1.0 if profile["company_type"].lower() == case["company_type"].lower() else 0.0)
            weights.append(0.20)

        # Wage level (distance) — weight 0.15
        if profile.get("wage_level") and case.get("wage_level"):
            scores.append(self._wage_level_sim(profile["wage_level"], case["wage_level"]))
            weights.append(0.15)

        # RFE issues (Jaccard) — weight 0.35
        if profile.get("rfe_issues") and case.get("rfe_issues"):
            scores.append(self._jaccard(set(profile["rfe_issues"]), set(case["rfe_issues"])))
            weights.append(0.35)

        if not weights:
            return 0.0

        # Normalise weights so they sum to 1
        total_w = sum(weights)
        return sum(s * w / total_w for s, w in zip(scores, weights))

    @staticmethod
    def _job_title_sim(a, b):
        """Token-level Jaccard similarity between two job titles."""
        ta = set(a.lower().split())
        tb = set(b.lower().split())
        if not ta or not tb:
            return 0.0
        return len(ta & tb) / len(ta | tb)

    @staticmethod
    def _wage_level_sim(a, b):
        """1 - normalised distance between wage levels (0=same, 1=max apart)."""
        order = {"level i": 1, "level ii": 2, "level iii": 3, "level iv": 4}
        va = order.get(a.lower().strip(), 0)
        vb = order.get(b.lower().strip(), 0)
        if va == 0 or vb == 0:
            return 0.0
        return 1.0 - abs(va - vb) / 3.0

    @staticmethod
    def _jaccard(a, b):
        if not a and not b:
            return 0.0
        return len(a & b) / len(a | b) if (a | b) else 0.0
