"""Build NetworkX knowledge graph from MongoDB H-1B AAO cases."""

import os
import pickle
import warnings
import numpy as np
import networkx as nx
from pathlib import Path
from dotenv import load_dotenv
from pymongo import MongoClient
from sklearn.metrics.pairwise import cosine_similarity

warnings.filterwarnings("ignore", category=RuntimeWarning, module="sklearn")

env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)


class GraphBuilder:
    """Builds and manages the H-1B case knowledge graph."""

    def __init__(self):
        self.G = nx.DiGraph()
        self.cases = []
        self.embeddings = None

    def load_from_mongodb(self, uri=None, db_name="rfe_tool", collection_name="cases"):
        """Load all complete cases with embeddings from MongoDB."""
        uri = uri or os.environ.get("MONGODB_URI")
        if not uri:
            raise ValueError(
                "No MongoDB URI. Pass uri= or set MONGODB_URI in .env"
            )

        client = MongoClient(uri)
        db = client[db_name]
        collection = db[collection_name]

        query = {"status": "complete", "embedding": {"$exists": True}}
        raw_cases = list(collection.find(query))
        client.close()

        if not raw_cases:
            raise ValueError(
                f"No complete cases with embeddings in {db_name}.{collection_name}"
            )

        # Separate embeddings from case metadata — normalise to unit vectors
        # to prevent overflow in cosine similarity calculations
        raw_emb = np.array([c["embedding"] for c in raw_cases], dtype=np.float64)
        norms = np.linalg.norm(raw_emb, axis=1, keepdims=True)
        norms[norms == 0] = 1.0  # avoid division by zero
        self.embeddings = raw_emb / norms

        # Store cases without embedding/full_text to keep memory light
        self.cases = []
        for i, c in enumerate(raw_cases):
            self.cases.append({
                "index": i,
                "mongo_id": str(c["_id"]),
                "case_number": c.get("case_number", ""),
                "outcome": c.get("outcome", "UNKNOWN"),
                "decision_date": c.get("decision_date", ""),
                "service_center": c.get("service_center", ""),
                "job_title": c.get("job_title", ""),
                "company_name": c.get("company_name", ""),
                "company_type": c.get("company_type", "unknown"),
                "wage_level": c.get("wage_level", ""),
                "rfe_issues": c.get("rfe_issues") or [],
                "denial_reasons": c.get("denial_reasons") or [],
                "arguments_made": c.get("arguments_made") or [],
                "x_2d": c.get("x_2d", 0.0),
                "y_2d": c.get("y_2d", 0.0),
                "filename": c.get("filename", ""),
            })

        # Print distribution
        outcomes = {}
        for c in self.cases:
            o = c["outcome"]
            outcomes[o] = outcomes.get(o, 0) + 1
        print(f"Loaded {len(self.cases)} cases from MongoDB")
        print(f"Outcome distribution: {outcomes}")

        return self.cases

    def build_graph(self, similarity_threshold=0.92):
        """Build knowledge graph with all node and edge types."""
        G = nx.DiGraph()

        # --- Add nodes and relationship edges for each case ---
        for case in self.cases:
            idx = case["index"]
            case_id = f"case_{idx}"

            # Case node
            G.add_node(case_id, node_type="Case", **{
                k: v for k, v in case.items()
                if k not in ("index", "mongo_id")
            })

            # Outcome -> RESULTED_IN
            outcome = case["outcome"]
            if outcome:
                oid = f"outcome_{outcome}"
                if oid not in G:
                    G.add_node(oid, node_type="Outcome", value=outcome)
                G.add_edge(case_id, oid, edge_type="RESULTED_IN")

            # Arguments -> USED_ARGUMENT
            for arg in case["arguments_made"]:
                aid = f"arg_{arg}"
                if aid not in G:
                    G.add_node(aid, node_type="Argument", value=arg)
                G.add_edge(case_id, aid, edge_type="USED_ARGUMENT")

            # Company type -> FILED_BY
            ct = case["company_type"]
            if ct:
                ctid = f"comptype_{ct}"
                if ctid not in G:
                    G.add_node(ctid, node_type="Company_Type", value=ct)
                G.add_edge(case_id, ctid, edge_type="FILED_BY")

            # Job title -> FOR_ROLE
            jt = case["job_title"]
            if jt:
                jtid = f"role_{jt}"
                if jtid not in G:
                    G.add_node(jtid, node_type="Job_Title", value=jt)
                G.add_edge(case_id, jtid, edge_type="FOR_ROLE")

            # RFE issues -> RECEIVED_RFE
            for issue in case["rfe_issues"]:
                rid = f"rfe_{issue}"
                if rid not in G:
                    G.add_node(rid, node_type="RFE_Issue", value=issue)
                G.add_edge(case_id, rid, edge_type="RECEIVED_RFE")

        # --- SIMILAR_TO edges from embedding cosine similarity ---
        n_similar = 0
        if self.embeddings is not None and len(self.embeddings) > 1:
            sim_matrix = cosine_similarity(self.embeddings)

            for i in range(len(self.cases)):
                for j in range(i + 1, len(self.cases)):
                    sim = float(sim_matrix[i][j])
                    if sim > similarity_threshold:
                        G.add_edge(
                            f"case_{i}", f"case_{j}",
                            edge_type="SIMILAR_TO", weight=sim,
                        )
                        G.add_edge(
                            f"case_{j}", f"case_{i}",
                            edge_type="SIMILAR_TO", weight=sim,
                        )
                        n_similar += 1

        self.G = G

        # Stats
        def count_type(t):
            return sum(1 for _, d in G.nodes(data=True) if d.get("node_type") == t)

        print(f"\nGraph built:")
        print(f"  Nodes: {G.number_of_nodes()}  |  Edges: {G.number_of_edges()}")
        print(f"  Cases: {count_type('Case')}  |  Arguments: {count_type('Argument')}")
        print(f"  Job Titles: {count_type('Job_Title')}  |  RFE Issues: {count_type('RFE_Issue')}")
        print(f"  SIMILAR_TO pairs: {n_similar} (threshold={similarity_threshold})")

        if n_similar == 0:
            print(
                f"  WARNING: No SIMILAR_TO edges at threshold {similarity_threshold}. "
                "Consider lowering the threshold."
            )

        return G

    def save_graph(self, path="h1b_graph.pkl"):
        """Persist graph + cases + embeddings to disk."""
        with open(path, "wb") as f:
            pickle.dump({
                "graph": self.G,
                "cases": self.cases,
                "embeddings": self.embeddings,
            }, f)
        print(f"Graph saved to {path}")

    def load_graph(self, path="h1b_graph.pkl"):
        """Load persisted graph from disk."""
        with open(path, "rb") as f:
            data = pickle.load(f)
        self.G = data["graph"]
        self.cases = data["cases"]
        self.embeddings = data["embeddings"]
        print(
            f"Graph loaded: {self.G.number_of_nodes()} nodes, "
            f"{self.G.number_of_edges()} edges, {len(self.cases)} cases"
        )
        return self.G
