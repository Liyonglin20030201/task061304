import pytest
from itertools import combinations
from collections import defaultdict


# ---------------------------------------------------------------------------
# Helper functions that mirror service logic for testability
# ---------------------------------------------------------------------------

def build_baskets(sales_rows, min_transactions=2):
    """Group raw sales rows by receipt_id into baskets of unique items.

    Args:
        sales_rows: list of dicts with at least 'receipt_id' and 'product_id'
        min_transactions: minimum number of unique items for a basket to be kept

    Returns:
        list of sets, each set being the unique product_ids in one receipt
    """
    grouped = defaultdict(set)
    for row in sales_rows:
        grouped[row["receipt_id"]].add(row["product_id"])
    return [items for items in grouped.values() if len(items) >= min_transactions]


def apriori(baskets, min_support, total_transactions=None):
    """Find frequent itemsets using the Apriori algorithm.

    Args:
        baskets: list of sets (each set is a transaction basket)
        min_support: minimum support threshold (0.0 - 1.0)
        total_transactions: total number of transactions (defaults to len(baskets))

    Returns:
        dict mapping frozenset -> support value
    """
    if total_transactions is None:
        total_transactions = len(baskets)

    # Count single items
    item_counts = defaultdict(int)
    for basket in baskets:
        for item in basket:
            item_counts[item] += 1

    # Filter by min_support to get frequent 1-itemsets
    frequent = {}
    for item, count in item_counts.items():
        support = count / total_transactions
        if support >= min_support:
            frequent[frozenset([item])] = support

    k = 2
    current_frequent_items = [itemset for itemset in frequent]

    while current_frequent_items:
        # Generate candidates of size k
        all_items = set()
        for itemset in current_frequent_items:
            all_items.update(itemset)

        candidates = [
            frozenset(combo)
            for combo in combinations(sorted(all_items), k)
        ]

        # Count support for candidates
        candidate_counts = defaultdict(int)
        for basket in baskets:
            for candidate in candidates:
                if candidate.issubset(basket):
                    candidate_counts[candidate] += 1

        # Filter by min_support
        new_frequent = {}
        for candidate, count in candidate_counts.items():
            support = count / total_transactions
            if support >= min_support:
                new_frequent[candidate] = support

        if not new_frequent:
            break

        frequent.update(new_frequent)
        current_frequent_items = list(new_frequent.keys())
        k += 1

    return frequent


def generate_rules(frequent_itemsets, total_transactions, min_confidence=0.0):
    """Generate association rules from frequent itemsets.

    Args:
        frequent_itemsets: dict mapping frozenset -> support
        total_transactions: total number of transactions
        min_confidence: minimum confidence threshold

    Returns:
        list of dicts with keys: antecedent, consequent, support, confidence, lift, conviction
    """
    rules = []

    for itemset, support in frequent_itemsets.items():
        if len(itemset) < 2:
            continue

        items = list(itemset)
        # Generate all non-empty proper subsets as antecedents
        for i in range(1, len(items)):
            for antecedent_tuple in combinations(items, i):
                antecedent = frozenset(antecedent_tuple)
                consequent = itemset - antecedent

                support_antecedent = frequent_itemsets.get(antecedent, 0)
                support_consequent = frequent_itemsets.get(consequent, 0)

                if support_antecedent == 0 or support_consequent == 0:
                    continue

                confidence = support / support_antecedent
                if confidence < min_confidence:
                    continue

                lift = confidence / support_consequent if support_consequent > 0 else 0

                # conviction = (1 - support(consequent)) / (1 - confidence)
                if confidence == 1.0:
                    conviction = float("inf")
                else:
                    conviction = (1 - support_consequent) / (1 - confidence)

                rules.append({
                    "antecedent": antecedent,
                    "consequent": consequent,
                    "support": support,
                    "confidence": confidence,
                    "lift": lift,
                    "conviction": conviction,
                })

    return rules


def compute_cooccurrence(baskets, items, top_n=None):
    """Compute a co-occurrence matrix for items across baskets.

    Args:
        baskets: list of sets
        items: list of items to include
        top_n: if provided, only include top N items by frequency

    Returns:
        dict of dicts: matrix[item_i][item_j] = co-occurrence count
    """
    # Count item frequency
    freq = defaultdict(int)
    for basket in baskets:
        for item in basket:
            if item in items:
                freq[item] += 1

    # Select top_n items if specified
    if top_n is not None:
        sorted_items = sorted(items, key=lambda x: freq.get(x, 0), reverse=True)
        selected = sorted_items[:top_n]
    else:
        selected = list(items)

    # Build co-occurrence matrix
    matrix = {item: defaultdict(int) for item in selected}
    for basket in baskets:
        basket_items = [item for item in selected if item in basket]
        for i, item_a in enumerate(basket_items):
            matrix[item_a][item_a] += 1
            for j in range(i + 1, len(basket_items)):
                item_b = basket_items[j]
                matrix[item_a][item_b] += 1
                matrix[item_b][item_a] += 1

    return matrix


def build_network_graph(rules, min_lift=1.0):
    """Build a network graph from association rules.

    Args:
        rules: list of rule dicts
        min_lift: minimum lift threshold for including an edge

    Returns:
        dict with 'nodes' (set) and 'edges' (list of tuples with metadata)
    """
    nodes = set()
    edges = []

    for rule in rules:
        if rule["lift"] >= min_lift:
            for item in rule["antecedent"]:
                nodes.add(item)
            for item in rule["consequent"]:
                nodes.add(item)
            edges.append({
                "source": rule["antecedent"],
                "target": rule["consequent"],
                "lift": rule["lift"],
            })

    return {"nodes": nodes, "edges": edges}


def get_bundle_recommendations(rules, item, top_n=5):
    """Get bundle recommendations for a given item sorted by lift.

    Args:
        rules: list of rule dicts
        item: the item to get recommendations for
        top_n: number of recommendations to return

    Returns:
        list of rule dicts where item is in antecedent, sorted by lift desc
    """
    matching = [
        rule for rule in rules
        if item in rule["antecedent"]
    ]
    matching.sort(key=lambda r: r["lift"], reverse=True)
    return matching[:top_n]


def find_layout_clusters(rules, min_lift=1.0):
    """Find clusters of associated items using connected components.

    Args:
        rules: list of rule dicts
        min_lift: minimum lift for a rule to count as a link

    Returns:
        list of dicts with 'items' (set) and 'avg_lift' (float)
    """
    # Build adjacency
    adjacency = defaultdict(set)
    edge_lifts = defaultdict(list)

    for rule in rules:
        if rule["lift"] < min_lift:
            continue
        all_items = rule["antecedent"] | rule["consequent"]
        items_list = list(all_items)
        for i in range(len(items_list)):
            for j in range(i + 1, len(items_list)):
                adjacency[items_list[i]].add(items_list[j])
                adjacency[items_list[j]].add(items_list[i])
                edge_lifts[frozenset([items_list[i], items_list[j]])].append(rule["lift"])

    # Find connected components via BFS
    visited = set()
    clusters = []

    for node in adjacency:
        if node in visited:
            continue
        component = set()
        queue = [node]
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            component.add(current)
            for neighbor in adjacency[current]:
                if neighbor not in visited:
                    queue.append(neighbor)

        # Calculate average lift for edges within cluster
        cluster_lifts = []
        for edge_key, lifts in edge_lifts.items():
            if edge_key.issubset(component):
                cluster_lifts.extend(lifts)

        avg_lift = sum(cluster_lifts) / len(cluster_lifts) if cluster_lifts else 0.0
        clusters.append({"items": component, "avg_lift": avg_lift})

    return clusters


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestBasketConstruction:
    def test_group_by_receipt(self):
        sales_rows = [
            {"receipt_id": "R1", "product_id": "A"},
            {"receipt_id": "R1", "product_id": "B"},
            {"receipt_id": "R2", "product_id": "C"},
            {"receipt_id": "R2", "product_id": "D"},
            {"receipt_id": "R3", "product_id": "E"},
            {"receipt_id": "R3", "product_id": "F"},
        ]
        baskets = build_baskets(sales_rows, min_transactions=2)
        assert len(baskets) == 3
        assert {"A", "B"} in baskets
        assert {"C", "D"} in baskets
        assert {"E", "F"} in baskets

    def test_min_transactions_filter(self):
        sales_rows = [
            {"receipt_id": "R1", "product_id": "A"},
            {"receipt_id": "R1", "product_id": "B"},
            {"receipt_id": "R1", "product_id": "C"},
            {"receipt_id": "R2", "product_id": "D"},
            {"receipt_id": "R2", "product_id": "E"},
        ]
        baskets = build_baskets(sales_rows, min_transactions=3)
        assert len(baskets) == 1
        assert {"A", "B", "C"} in baskets

    def test_single_item_baskets_excluded(self):
        sales_rows = [
            {"receipt_id": "R1", "product_id": "A"},
            {"receipt_id": "R2", "product_id": "B"},
            {"receipt_id": "R2", "product_id": "C"},
        ]
        baskets = build_baskets(sales_rows, min_transactions=2)
        assert len(baskets) == 1
        assert {"B", "C"} in baskets

    def test_duplicate_items_in_receipt(self):
        sales_rows = [
            {"receipt_id": "R1", "product_id": "A"},
            {"receipt_id": "R1", "product_id": "A"},
            {"receipt_id": "R1", "product_id": "B"},
        ]
        baskets = build_baskets(sales_rows, min_transactions=2)
        assert len(baskets) == 1
        assert {"A", "B"} in baskets
        # Duplicate A should count as 1 unique item
        basket = baskets[0]
        assert len(basket) == 2


class TestAprioriAlgorithm:
    @pytest.fixture
    def simple_baskets(self):
        return [
            {"A", "B", "C"},
            {"A", "B"},
            {"A", "C"},
            {"B", "C"},
            {"A", "B", "C"},
        ]

    def test_basic_frequent_itemsets(self, simple_baskets):
        result = apriori(simple_baskets, min_support=0.4)

        # Single items: A=4/5, B=4/5, C=4/5
        assert result[frozenset(["A"])] == pytest.approx(4 / 5)
        assert result[frozenset(["B"])] == pytest.approx(4 / 5)
        assert result[frozenset(["C"])] == pytest.approx(4 / 5)

        # Pairs: AB=3/5, AC=3/5, BC=3/5
        assert result[frozenset(["A", "B"])] == pytest.approx(3 / 5)
        assert result[frozenset(["A", "C"])] == pytest.approx(3 / 5)
        assert result[frozenset(["B", "C"])] == pytest.approx(3 / 5)

        # Triple: ABC=2/5
        assert result[frozenset(["A", "B", "C"])] == pytest.approx(2 / 5)

    def test_min_support_filtering(self, simple_baskets):
        result = apriori(simple_baskets, min_support=0.5)

        # All single items should pass (support = 0.8)
        assert frozenset(["A"]) in result
        assert frozenset(["B"]) in result
        assert frozenset(["C"]) in result

        # Pairs should pass (support = 0.6)
        assert frozenset(["A", "B"]) in result
        assert frozenset(["A", "C"]) in result
        assert frozenset(["B", "C"]) in result

        # Triple should NOT pass (support = 0.4 < 0.5)
        assert frozenset(["A", "B", "C"]) not in result

    def test_no_frequent_itemsets(self):
        baskets = [
            {"A", "B"},
            {"C", "D"},
            {"E", "F"},
            {"G", "H"},
            {"I", "J"},
        ]
        result = apriori(baskets, min_support=0.9)
        # No single item appears in 90% of transactions
        assert len(result) == 0

    def test_large_itemsets(self):
        baskets = [
            {"A", "B", "C", "D"},
            {"A", "B", "C"},
            {"A", "B", "C", "D"},
            {"A", "B", "C"},
            {"A", "B", "C", "D"},
        ]
        result = apriori(baskets, min_support=0.5)

        # ABC should be frequent (5/5 = 1.0)
        assert frozenset(["A", "B", "C"]) in result
        assert result[frozenset(["A", "B", "C"])] == pytest.approx(1.0)

        # ABCD should be frequent (3/5 = 0.6)
        assert frozenset(["A", "B", "C", "D"]) in result
        assert result[frozenset(["A", "B", "C", "D"])] == pytest.approx(3 / 5)


class TestRuleGeneration:
    def test_basic_rule_metrics(self):
        frequent_itemsets = {
            frozenset(["A"]): 0.8,
            frozenset(["B"]): 0.7,
            frozenset(["A", "B"]): 0.6,
        }
        rules = generate_rules(frequent_itemsets, total_transactions=10)

        # Find rule A -> B
        rule_a_to_b = next(
            r for r in rules
            if r["antecedent"] == frozenset(["A"]) and r["consequent"] == frozenset(["B"])
        )
        # confidence = support(AB) / support(A) = 0.6 / 0.8 = 0.75
        assert rule_a_to_b["confidence"] == pytest.approx(0.75)
        # lift = confidence / support(B) = 0.75 / 0.7
        assert rule_a_to_b["lift"] == pytest.approx(0.75 / 0.7)

    def test_confidence_filter(self):
        frequent_itemsets = {
            frozenset(["A"]): 0.9,
            frozenset(["B"]): 0.3,
            frozenset(["A", "B"]): 0.3,
        }
        # confidence of A->B = 0.3/0.9 = 0.333
        rules = generate_rules(frequent_itemsets, total_transactions=10, min_confidence=0.5)
        rules_a_to_b = [
            r for r in rules
            if r["antecedent"] == frozenset(["A"]) and r["consequent"] == frozenset(["B"])
        ]
        assert len(rules_a_to_b) == 0

        # confidence of B->A = 0.3/0.3 = 1.0 (should pass)
        rules_b_to_a = [
            r for r in rules
            if r["antecedent"] == frozenset(["B"]) and r["consequent"] == frozenset(["A"])
        ]
        assert len(rules_b_to_a) == 1
        assert rules_b_to_a[0]["confidence"] == pytest.approx(1.0)

    def test_lift_calculation(self):
        frequent_itemsets = {
            frozenset(["A"]): 0.5,
            frozenset(["B"]): 0.4,
            frozenset(["A", "B"]): 0.4,
        }
        rules = generate_rules(frequent_itemsets, total_transactions=10)
        rule_a_to_b = next(
            r for r in rules
            if r["antecedent"] == frozenset(["A"]) and r["consequent"] == frozenset(["B"])
        )
        # confidence = 0.4/0.5 = 0.8, lift = 0.8/0.4 = 2.0
        assert rule_a_to_b["lift"] == pytest.approx(2.0)
        assert rule_a_to_b["lift"] > 1.0  # positive association

    def test_conviction_calculation(self):
        frequent_itemsets = {
            frozenset(["A"]): 0.8,
            frozenset(["B"]): 0.6,
            frozenset(["A", "B"]): 0.6,
        }
        rules = generate_rules(frequent_itemsets, total_transactions=10)
        rule_a_to_b = next(
            r for r in rules
            if r["antecedent"] == frozenset(["A"]) and r["consequent"] == frozenset(["B"])
        )
        # confidence = 0.6/0.8 = 0.75
        # conviction = (1 - support(B)) / (1 - confidence) = (1 - 0.6) / (1 - 0.75) = 0.4 / 0.25 = 1.6
        assert rule_a_to_b["conviction"] == pytest.approx(1.6)

    def test_bidirectional_rules(self):
        frequent_itemsets = {
            frozenset(["A"]): 0.7,
            frozenset(["B"]): 0.6,
            frozenset(["A", "B"]): 0.5,
        }
        rules = generate_rules(frequent_itemsets, total_transactions=10)

        antecedent_consequent_pairs = [
            (r["antecedent"], r["consequent"]) for r in rules
        ]
        # Both directions should exist
        assert (frozenset(["A"]), frozenset(["B"])) in antecedent_consequent_pairs
        assert (frozenset(["B"]), frozenset(["A"])) in antecedent_consequent_pairs


class TestCooccurrenceMatrix:
    @pytest.fixture
    def baskets_and_items(self):
        baskets = [
            {"A", "B", "C"},
            {"A", "B"},
            {"A", "C"},
            {"B", "C"},
            {"A", "B", "C"},
        ]
        items = ["A", "B", "C"]
        return baskets, items

    def test_matrix_symmetry(self, baskets_and_items):
        baskets, items = baskets_and_items
        matrix = compute_cooccurrence(baskets, items)
        for item_a in items:
            for item_b in items:
                assert matrix[item_a][item_b] == matrix[item_b][item_a]

    def test_diagonal_is_self_count(self, baskets_and_items):
        baskets, items = baskets_and_items
        matrix = compute_cooccurrence(baskets, items)
        # A appears in baskets 0,1,2,4 = 4
        assert matrix["A"]["A"] == 4
        # B appears in baskets 0,1,3,4 = 4
        assert matrix["B"]["B"] == 4
        # C appears in baskets 0,2,3,4 = 4
        assert matrix["C"]["C"] == 4

    def test_correct_counts(self, baskets_and_items):
        baskets, items = baskets_and_items
        matrix = compute_cooccurrence(baskets, items)
        # A and B co-occur in baskets 0,1,4 = 3
        assert matrix["A"]["B"] == 3
        # A and C co-occur in baskets 0,2,4 = 3
        assert matrix["A"]["C"] == 3
        # B and C co-occur in baskets 0,3,4 = 3
        assert matrix["B"]["C"] == 3

    def test_top_n_selection(self):
        baskets = [
            {"A", "B", "C", "D"},
            {"A", "B", "C"},
            {"A", "B"},
            {"A"},
        ]
        items = ["A", "B", "C", "D"]
        matrix = compute_cooccurrence(baskets, items, top_n=2)
        # Top 2 items by frequency: A(4), B(3)
        assert "A" in matrix
        assert "B" in matrix
        assert "C" not in matrix
        assert "D" not in matrix


class TestNetworkGraph:
    @pytest.fixture
    def sample_rules(self):
        return [
            {
                "antecedent": frozenset(["A"]),
                "consequent": frozenset(["B"]),
                "support": 0.5,
                "confidence": 0.8,
                "lift": 1.5,
                "conviction": 2.0,
            },
            {
                "antecedent": frozenset(["B"]),
                "consequent": frozenset(["C"]),
                "support": 0.4,
                "confidence": 0.7,
                "lift": 1.2,
                "conviction": 1.5,
            },
            {
                "antecedent": frozenset(["D"]),
                "consequent": frozenset(["E"]),
                "support": 0.3,
                "confidence": 0.5,
                "lift": 0.8,
                "conviction": 0.9,
            },
        ]

    def test_nodes_from_rules(self, sample_rules):
        graph = build_network_graph(sample_rules, min_lift=1.0)
        # Only rules with lift >= 1.0: A->B (1.5) and B->C (1.2)
        assert "A" in graph["nodes"]
        assert "B" in graph["nodes"]
        assert "C" in graph["nodes"]

    def test_edges_from_rules(self, sample_rules):
        graph = build_network_graph(sample_rules, min_lift=1.0)
        # Two rules pass: A->B and B->C
        assert len(graph["edges"]) == 2

    def test_min_lift_filter(self, sample_rules):
        graph = build_network_graph(sample_rules, min_lift=1.0)
        # D->E has lift 0.8 < 1.0, so D and E should not appear
        assert "D" not in graph["nodes"]
        assert "E" not in graph["nodes"]
        # Verify no edge with lift < 1.0
        for edge in graph["edges"]:
            assert edge["lift"] >= 1.0


class TestBundleRecommendations:
    @pytest.fixture
    def rules_for_bundles(self):
        return [
            {
                "antecedent": frozenset(["A"]),
                "consequent": frozenset(["B"]),
                "support": 0.5,
                "confidence": 0.8,
                "lift": 2.5,
                "conviction": 2.0,
            },
            {
                "antecedent": frozenset(["A"]),
                "consequent": frozenset(["C"]),
                "support": 0.4,
                "confidence": 0.7,
                "lift": 1.8,
                "conviction": 1.5,
            },
            {
                "antecedent": frozenset(["A"]),
                "consequent": frozenset(["D"]),
                "support": 0.3,
                "confidence": 0.6,
                "lift": 3.0,
                "conviction": 1.8,
            },
            {
                "antecedent": frozenset(["B"]),
                "consequent": frozenset(["A"]),
                "support": 0.5,
                "confidence": 0.9,
                "lift": 1.2,
                "conviction": 3.0,
            },
        ]

    def test_recommendations_sorted_by_lift(self, rules_for_bundles):
        recs = get_bundle_recommendations(rules_for_bundles, "A", top_n=5)
        lifts = [r["lift"] for r in recs]
        assert lifts == sorted(lifts, reverse=True)
        # Highest lift first: 3.0, 2.5, 1.8
        assert lifts[0] == 3.0
        assert lifts[1] == 2.5
        assert lifts[2] == 1.8

    def test_top_n_limit(self, rules_for_bundles):
        recs = get_bundle_recommendations(rules_for_bundles, "A", top_n=2)
        assert len(recs) == 2

    def test_no_rules_for_item(self, rules_for_bundles):
        recs = get_bundle_recommendations(rules_for_bundles, "Z", top_n=5)
        assert recs == []


class TestLayoutSuggestions:
    @pytest.fixture
    def layout_rules(self):
        return [
            {
                "antecedent": frozenset(["A"]),
                "consequent": frozenset(["B"]),
                "support": 0.5,
                "confidence": 0.8,
                "lift": 2.0,
                "conviction": 2.0,
            },
            {
                "antecedent": frozenset(["B"]),
                "consequent": frozenset(["C"]),
                "support": 0.4,
                "confidence": 0.7,
                "lift": 1.5,
                "conviction": 1.5,
            },
            {
                "antecedent": frozenset(["D"]),
                "consequent": frozenset(["E"]),
                "support": 0.3,
                "confidence": 0.6,
                "lift": 1.8,
                "conviction": 1.3,
            },
            {
                "antecedent": frozenset(["X"]),
                "consequent": frozenset(["Y"]),
                "support": 0.2,
                "confidence": 0.4,
                "lift": 0.5,
                "conviction": 0.8,
            },
        ]

    def test_connected_components(self, layout_rules):
        clusters = find_layout_clusters(layout_rules, min_lift=1.0)
        # Cluster 1: A-B-C (connected via A->B and B->C)
        # Cluster 2: D-E (connected via D->E)
        # X->Y excluded (lift 0.5 < 1.0)
        cluster_item_sets = [c["items"] for c in clusters]
        assert {"A", "B", "C"} in cluster_item_sets
        assert {"D", "E"} in cluster_item_sets
        assert len(clusters) == 2

    def test_isolated_items_excluded(self, layout_rules):
        clusters = find_layout_clusters(layout_rules, min_lift=1.0)
        all_clustered_items = set()
        for c in clusters:
            all_clustered_items.update(c["items"])
        # X and Y should not appear because their rule has lift < 1.0
        assert "X" not in all_clustered_items
        assert "Y" not in all_clustered_items

    def test_cluster_avg_lift(self, layout_rules):
        clusters = find_layout_clusters(layout_rules, min_lift=1.0)
        # Find cluster containing A, B, C
        abc_cluster = next(c for c in clusters if "A" in c["items"])
        # Edges in this cluster: A-B (lift 2.0), B-C (lift 1.5)
        # Average lift = (2.0 + 1.5) / 2 = 1.75
        assert abc_cluster["avg_lift"] == pytest.approx(1.75)

        # Find cluster containing D, E
        de_cluster = next(c for c in clusters if "D" in c["items"])
        # Only one edge: D-E (lift 1.8)
        assert de_cluster["avg_lift"] == pytest.approx(1.8)
