"""Interactive graph visualization using pyvis."""

from pyvis.network import Network


# Outcome colours
OUTCOME_COLORS = {
    "SUSTAINED": "#00ff88",
    "DISMISSED": "#ff4466",
    "REMANDED": "#ffcc00",
}
NODE_TYPE_COLORS = {
    "Argument": "#6ec6ff",
    "RFE_Issue": "#ce93d8",
    "Company_Type": "#ffb74d",
    "Job_Title": "#a5d6a7",
    "Outcome": "#e0e0e0",
}
NODE_TYPE_SHAPES = {
    "Case": "dot",
    "Argument": "diamond",
    "RFE_Issue": "triangle",
    "Company_Type": "square",
    "Job_Title": "star",
    "Outcome": "box",
}


class GraphVisualizer:
    """Creates interactive HTML visualizations of the strategy graph."""

    def __init__(self, graph, cases):
        self.G = graph
        self.cases = cases

    def create_strategy_visualization(self, user_profile, similar_cases,
                                      output_path="strategy_recommendation.html"):
        """Build a focused subgraph around the user and their similar cases.

        Returns the path to the generated HTML file.
        """
        net = Network(
            height="900px", width="100%", bgcolor="#1a1a2e",
            font_color="white", directed=False, notebook=False,
        )
        net.barnes_hut(
            gravity=-3000, central_gravity=0.3,
            spring_length=150, spring_strength=0.05,
        )

        # --- Central USER node ---
        user_label = (
            f"{user_profile.get('job_title', 'Your Case')}\n"
            f"({user_profile.get('company_type', '')}, "
            f"{user_profile.get('wage_level', '')})"
        )
        net.add_node(
            "USER", label=user_label, color="#00bfff", shape="star",
            size=40, borderWidth=3, font={"size": 16, "color": "white"},
            title=self._user_tooltip(user_profile),
        )

        # --- Similar case nodes ---
        added_cases = set()
        for case in similar_cases:
            cid = f"case_{case['index']}"
            added_cases.add(cid)
            outcome = case.get("outcome", "UNKNOWN")
            color = OUTCOME_COLORS.get(outcome, "#888888")
            sim = case.get("similarity_score", 0)

            title_lines = [
                f"<b>{case.get('case_number', 'N/A')}</b>",
                f"Outcome: {outcome}",
                f"Job: {case.get('job_title', 'N/A')}",
                f"Company: {case.get('company_name', 'N/A')} ({case.get('company_type', '')})",
                f"Wage: {case.get('wage_level', 'N/A')}",
                f"RFE: {', '.join(case.get('rfe_issues', [])[:3])}",
                f"Args: {', '.join(case.get('arguments_made', []))}",
                f"Similarity: {sim:.2f}",
            ]

            label = case.get("case_number") or case.get("job_title") or f"Case {case.get('index', '?')}"
            if len(label) > 20:
                label = label[:17] + "..."

            net.add_node(
                cid, label=label, color=color,
                shape="dot", size=15 + sim * 20,
                borderWidth=2,
                title="<br>".join(title_lines),
            )

            # Edge from USER to case
            net.add_edge(
                "USER", cid,
                value=sim, color={"color": "#ffffff44"},
                title=f"Similarity: {sim:.2f}",
            )

        # --- Argument nodes for similar cases ---
        arg_outcomes = {}  # arg -> {SUSTAINED: n, DISMISSED: n}
        for case in similar_cases:
            outcome = case.get("outcome", "")
            for arg in case.get("arguments_made", []):
                if arg not in arg_outcomes:
                    arg_outcomes[arg] = {"SUSTAINED": 0, "DISMISSED": 0, "REMANDED": 0}
                arg_outcomes[arg][outcome] = arg_outcomes[arg].get(outcome, 0) + 1

        user_args = set(user_profile.get("current_arguments", []))

        for arg, stats in arg_outcomes.items():
            aid = f"arg_{arg}"
            total = sum(stats.values())
            sust = stats.get("SUSTAINED", 0)
            rate = sust / total if total else 0

            # Color: green if high success, red if low
            if rate >= 0.6:
                color = "#00ff88"
            elif rate >= 0.3:
                color = "#ffcc00"
            else:
                color = "#ff4466"

            border = "#00bfff" if arg in user_args else "#ffffff44"

            net.add_node(
                aid, label=arg.replace("_", " ").title(),
                color=color, shape="diamond", size=12 + total * 2,
                borderWidth=3 if arg in user_args else 1,
                borderWidthSelected=4,
                title=(
                    f"<b>{arg}</b><br>"
                    f"Success rate: {rate:.0%} ({sust}/{total})<br>"
                    f"{'(You use this)' if arg in user_args else '(Consider adding)'}"
                ),
            )

            # Connect argument to cases that used it
            for case in similar_cases:
                if arg in case.get("arguments_made", []):
                    cid = f"case_{case['index']}"
                    outcome_color = OUTCOME_COLORS.get(case.get("outcome", ""), "#888")
                    net.add_edge(
                        cid, aid,
                        color={"color": outcome_color + "66"},
                        width=1, arrows="",
                    )

        # --- SIMILAR_TO edges between cases ---
        for case_a in similar_cases:
            for case_b in similar_cases:
                a_id = f"case_{case_a['index']}"
                b_id = f"case_{case_b['index']}"
                if a_id >= b_id:
                    continue
                if self.G.has_edge(a_id, b_id):
                    edge_data = self.G[a_id][b_id]
                    if edge_data.get("edge_type") == "SIMILAR_TO":
                        net.add_edge(
                            a_id, b_id,
                            color={"color": "#ffffff22"}, width=1,
                            title=f"Cosine sim: {edge_data.get('weight', 0):.2f}",
                        )

        # --- Legend via hidden nodes ---
        legend_x, legend_y = -800, -400
        legend_items = [
            ("SUSTAINED", "#00ff88", "dot"),
            ("DISMISSED", "#ff4466", "dot"),
            ("REMANDED", "#ffcc00", "dot"),
            ("Your Profile", "#00bfff", "star"),
            ("Argument (high win)", "#00ff88", "diamond"),
            ("Argument (low win)", "#ff4466", "diamond"),
        ]
        for i, (label, color, shape) in enumerate(legend_items):
            net.add_node(
                f"legend_{i}", label=label, color=color, shape=shape,
                size=10, x=legend_x, y=legend_y + i * 50,
                physics=False, font={"size": 12, "color": "white"},
            )

        net.set_options("""
        {
          "interaction": {
            "hover": true,
            "tooltipDelay": 100,
            "navigationButtons": true
          },
          "physics": {
            "barnesHut": {
              "gravitationalConstant": -3000,
              "springLength": 150
            },
            "stabilization": {"iterations": 200}
          }
        }
        """)

        net.save_graph(output_path)
        print(f"Visualization saved to {output_path}")
        return output_path

    @staticmethod
    def _user_tooltip(profile):
        return "<br>".join([
            "<b>YOUR PROFILE</b>",
            f"Job Title: {profile.get('job_title', 'N/A')}",
            f"Company Type: {profile.get('company_type', 'N/A')}",
            f"Wage Level: {profile.get('wage_level', 'N/A')}",
            f"RFE Issues: {', '.join(profile.get('rfe_issues', []))}",
            f"Current Args: {', '.join(profile.get('current_arguments', []))}",
        ])
