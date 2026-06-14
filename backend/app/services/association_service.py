import pandas as pd
import numpy as np
from itertools import combinations
from collections import defaultdict
from sqlalchemy import text, select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, date

from app.models.association import AssociationRule, AssociationAnalysisJob


async def run_association_analysis(
    db: AsyncSession,
    store_id: int,
    start_date: str,
    end_date: str,
    min_support: float,
    min_confidence: float,
    category_filter: str = None,
    min_transactions: int = 2,
) -> dict:
    """
    Main analysis function:
    1. Query sales grouped by receipt_no to build baskets
    2. Filter baskets with >= min_transactions items
    3. Run Apriori to find frequent itemsets
    4. Generate rules from frequent itemsets
    5. Store results in association_rules table
    6. Return summary stats
    """
    # Build baskets
    baskets, item_names, total_transactions = await _build_baskets(
        db, store_id, start_date, end_date, category_filter, min_transactions
    )

    if total_transactions == 0:
        return {
            "total_transactions": 0,
            "unique_items": 0,
            "rules_found": 0,
            "message": "No qualifying transactions found",
        }

    # Get all unique items across baskets
    all_items = set()
    for basket in baskets:
        all_items.update(basket)

    # Run Apriori algorithm
    frequent_itemsets = _apriori(baskets, all_items, min_support, total_transactions)

    # Generate association rules
    rules = _generate_rules(frequent_itemsets, total_transactions, min_confidence)

    # Delete old rules for same store/period/category
    delete_sql = text("""
        DELETE FROM association_rules
        WHERE store_id = :store_id
        AND period_start = :period_start
        AND period_end = :period_end
        AND (category_filter = :category_filter OR (category_filter IS NULL AND :category_filter IS NULL))
    """)
    await db.execute(delete_sql, {
        "store_id": store_id,
        "period_start": start_date,
        "period_end": end_date,
        "category_filter": category_filter,
    })

    # Store rules in database
    for rule in rules:
        antecedent_list = list(rule["antecedent"])
        consequent_list = list(rule["consequent"])
        db_rule = AssociationRule(
            store_id=store_id,
            antecedent_items=antecedent_list,
            consequent_items=consequent_list,
            antecedent_names=[item_names.get(item_id, item_id) for item_id in antecedent_list],
            consequent_names=[item_names.get(item_id, item_id) for item_id in consequent_list],
            support=rule["support"],
            confidence=rule["confidence"],
            lift=rule["lift"],
            conviction=rule.get("conviction"),
            leverage=rule.get("leverage"),
            transaction_count=total_transactions,
            period_start=start_date,
            period_end=end_date,
            category_filter=category_filter,
        )
        db.add(db_rule)

    await db.flush()

    return {
        "total_transactions": total_transactions,
        "unique_items": len(all_items),
        "frequent_itemsets_count": len(frequent_itemsets),
        "rules_found": len(rules),
    }


async def _build_baskets(
    db: AsyncSession,
    store_id: int,
    start_date: str,
    end_date: str,
    category_filter: str = None,
    min_transactions: int = 2,
) -> tuple:
    """
    Query sales grouped by receipt_no to build transaction baskets.
    Returns (baskets: list of sets of item_ids, item_names: dict, total_transactions: int)
    """
    category_clause = ""
    params = {
        "store_id": store_id,
        "start_date": start_date,
        "end_date": end_date,
    }
    if category_filter:
        category_clause = "AND category = :category_filter"
        params["category_filter"] = category_filter

    # Get all items per receipt
    sql = text(f"""
        SELECT receipt_no, item_id, item_name
        FROM sales
        WHERE store_id = :store_id
        AND sale_date BETWEEN :start_date AND :end_date
        {category_clause}
    """)
    result = await db.execute(sql, params)
    rows = result.fetchall()

    if not rows:
        return [], {}, 0

    # Build item_names mapping and group by receipt
    item_names = {}
    receipt_items = defaultdict(set)
    for row in rows:
        receipt_no, item_id, item_name = row[0], row[1], row[2]
        receipt_items[receipt_no].add(item_id)
        if item_name:
            item_names[item_id] = item_name

    # Filter baskets by minimum distinct items
    baskets = [items for items in receipt_items.values() if len(items) >= min_transactions]
    total_transactions = len(baskets)

    return baskets, item_names, total_transactions


def _apriori(baskets: list, items: set, min_support: float, total_transactions: int) -> dict:
    """
    Apriori algorithm (synchronous, CPU-bound):
    1. Count single items, filter by min_support
    2. Generate candidate k-itemsets from (k-1)-itemsets
    3. Count support for candidates
    4. Prune below min_support
    5. Repeat until no more candidates
    Returns: dict mapping frozenset -> support_count
    """
    min_count = min_support * total_transactions
    frequent_itemsets = {}

    # Step 1: Find frequent 1-itemsets
    item_counts = defaultdict(int)
    for basket in baskets:
        for item in basket:
            item_counts[item] += 1

    # Filter by min_support
    freq_1 = {frozenset([item]): count for item, count in item_counts.items() if count >= min_count}
    frequent_itemsets.update(freq_1)

    if not freq_1:
        return frequent_itemsets

    # Step 2+: Generate larger itemsets
    current_freq = freq_1
    k = 2

    while current_freq:
        # Generate candidates of size k from frequent (k-1)-itemsets
        prev_items = list(current_freq.keys())
        candidates = set()

        for i in range(len(prev_items)):
            for j in range(i + 1, len(prev_items)):
                union = prev_items[i] | prev_items[j]
                if len(union) == k:
                    candidates.add(union)

        if not candidates:
            break

        # Count support for candidates
        candidate_counts = defaultdict(int)
        for basket in baskets:
            basket_frozen = frozenset(basket)
            for candidate in candidates:
                if candidate.issubset(basket_frozen):
                    candidate_counts[candidate] += 1

        # Filter by min_support
        current_freq = {
            itemset: count
            for itemset, count in candidate_counts.items()
            if count >= min_count
        }
        frequent_itemsets.update(current_freq)
        k += 1

        # Safety: limit itemset size to prevent combinatorial explosion
        if k > 5:
            break

    return frequent_itemsets


def _generate_rules(
    frequent_itemsets: dict, total_transactions: int, min_confidence: float
) -> list:
    """
    From frequent itemsets, generate association rules.
    For each itemset of size >= 2, try all non-empty proper subsets as antecedent.
    Calculate: support, confidence, lift, conviction, leverage.
    Filter by min_confidence.
    Returns list of dicts with antecedent, consequent, metrics.
    """
    rules = []

    for itemset, support_count in frequent_itemsets.items():
        if len(itemset) < 2:
            continue

        support = support_count / total_transactions

        # Generate all non-empty proper subsets as antecedent
        items_list = list(itemset)
        for i in range(1, len(items_list)):
            for antecedent_tuple in combinations(items_list, i):
                antecedent = frozenset(antecedent_tuple)
                consequent = itemset - antecedent

                if not consequent:
                    continue

                # Get antecedent support count
                antecedent_count = frequent_itemsets.get(antecedent, 0)
                if antecedent_count == 0:
                    continue

                # Get consequent support count
                consequent_count = frequent_itemsets.get(consequent, 0)
                if consequent_count == 0:
                    continue

                antecedent_support = antecedent_count / total_transactions
                consequent_support = consequent_count / total_transactions

                # Confidence = P(consequent | antecedent) = support(A∪C) / support(A)
                confidence = support_count / antecedent_count

                if confidence < min_confidence:
                    continue

                # Lift = confidence / support(consequent)
                lift = confidence / consequent_support if consequent_support > 0 else 0

                # Conviction = (1 - support(C)) / (1 - confidence)
                conviction = None
                if confidence < 1.0:
                    conviction = (1 - consequent_support) / (1 - confidence)

                # Leverage = support(A∪C) - support(A) * support(C)
                leverage = support - (antecedent_support * consequent_support)

                rules.append({
                    "antecedent": antecedent,
                    "consequent": consequent,
                    "support": round(support, 6),
                    "confidence": round(confidence, 6),
                    "lift": round(lift, 4),
                    "conviction": round(conviction, 4) if conviction is not None else None,
                    "leverage": round(leverage, 6),
                })

    # Sort by lift descending
    rules.sort(key=lambda x: x["lift"], reverse=True)
    return rules


async def get_association_rules(
    db: AsyncSession,
    store_id: int,
    start_date: str = None,
    end_date: str = None,
    category: str = None,
    min_lift: float = None,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    """Query stored rules with filters, return paginated results."""
    conditions = ["store_id = :store_id"]
    params = {"store_id": store_id}

    if start_date:
        conditions.append("period_start >= :start_date")
        params["start_date"] = start_date
    if end_date:
        conditions.append("period_end <= :end_date")
        params["end_date"] = end_date
    if category:
        conditions.append("category_filter = :category")
        params["category"] = category
    if min_lift is not None:
        conditions.append("lift >= :min_lift")
        params["min_lift"] = min_lift

    where_clause = " AND ".join(conditions)

    # Count total
    count_sql = text(f"SELECT COUNT(*) FROM association_rules WHERE {where_clause}")
    count_result = await db.execute(count_sql, params)
    total = count_result.scalar()

    # Get paginated results
    offset = (page - 1) * page_size
    params["limit"] = page_size
    params["offset"] = offset

    data_sql = text(f"""
        SELECT id, store_id, antecedent_items, consequent_items,
               antecedent_names, consequent_names, support, confidence, lift,
               conviction, leverage, transaction_count, period_start, period_end,
               category_filter, computed_at
        FROM association_rules
        WHERE {where_clause}
        ORDER BY lift DESC
        LIMIT :limit OFFSET :offset
    """)
    result = await db.execute(data_sql, params)
    rows = result.fetchall()

    rules = []
    for row in rows:
        rules.append({
            "id": row[0],
            "store_id": row[1],
            "antecedent_items": row[2],
            "consequent_items": row[3],
            "antecedent_names": row[4],
            "consequent_names": row[5],
            "support": row[6],
            "confidence": row[7],
            "lift": row[8],
            "conviction": row[9],
            "leverage": row[10],
            "transaction_count": row[11],
            "period_start": row[12],
            "period_end": row[13],
            "category_filter": row[14],
            "computed_at": row[15],
        })

    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

    return {
        "items": rules,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


async def get_cooccurrence_matrix(
    db: AsyncSession,
    store_id: int,
    start_date: str,
    end_date: str,
    category: str = None,
    top_n: int = 20,
) -> dict:
    """
    Compute pairwise co-purchase frequencies:
    1. Build baskets
    2. For top_n most frequent items, count how many baskets contain both item_i and item_j
    3. Return symmetric matrix + item labels
    """
    baskets, item_names, total_transactions = await _build_baskets(
        db, store_id, start_date, end_date, category, min_transactions=2
    )

    if not baskets:
        return {"labels": [], "matrix": []}

    # Count item frequencies
    item_freq = defaultdict(int)
    for basket in baskets:
        for item in basket:
            item_freq[item] += 1

    # Get top_n most frequent items
    sorted_items = sorted(item_freq.items(), key=lambda x: x[1], reverse=True)[:top_n]
    top_items = [item_id for item_id, _ in sorted_items]
    top_items_set = set(top_items)

    # Build labels using item names
    labels = [item_names.get(item_id, item_id) for item_id in top_items]

    # Build co-occurrence matrix
    n = len(top_items)
    matrix = [[0] * n for _ in range(n)]
    item_index = {item_id: idx for idx, item_id in enumerate(top_items)}

    for basket in baskets:
        basket_top = [item for item in basket if item in top_items_set]
        for i in range(len(basket_top)):
            for j in range(i + 1, len(basket_top)):
                idx_i = item_index[basket_top[i]]
                idx_j = item_index[basket_top[j]]
                matrix[idx_i][idx_j] += 1
                matrix[idx_j][idx_i] += 1

    # Diagonal = self frequency
    for item_id in top_items:
        idx = item_index[item_id]
        matrix[idx][idx] = item_freq[item_id]

    return {"labels": labels, "matrix": matrix}


async def get_network_graph_data(
    db: AsyncSession,
    store_id: int,
    start_date: str = None,
    end_date: str = None,
    min_lift: float = 1.5,
    top_n: int = 30,
) -> dict:
    """
    Query association_rules, build graph:
    - Nodes: unique items from antecedent + consequent
    - Edges: rules with lift >= min_lift
    Return {nodes: [...], edges: [...]}
    """
    conditions = ["store_id = :store_id", "lift >= :min_lift"]
    params = {"store_id": store_id, "min_lift": min_lift}

    if start_date:
        conditions.append("period_start >= :start_date")
        params["start_date"] = start_date
    if end_date:
        conditions.append("period_end <= :end_date")
        params["end_date"] = end_date

    where_clause = " AND ".join(conditions)
    params["limit"] = top_n

    sql = text(f"""
        SELECT antecedent_items, consequent_items, antecedent_names, consequent_names,
               lift, transaction_count
        FROM association_rules
        WHERE {where_clause}
        ORDER BY lift DESC
        LIMIT :limit
    """)
    result = await db.execute(sql, params)
    rows = result.fetchall()

    nodes_map = {}  # item_id -> {name, count}
    edges = []

    for row in rows:
        antecedent_items = row[0] or []
        consequent_items = row[1] or []
        antecedent_names = row[2] or []
        consequent_names = row[3] or []
        lift = row[4]
        tx_count = row[5] or 0

        # Add nodes for antecedent items
        for i, item_id in enumerate(antecedent_items):
            name = antecedent_names[i] if i < len(antecedent_names) else item_id
            if item_id not in nodes_map:
                nodes_map[item_id] = {"name": name, "count": tx_count}
            else:
                nodes_map[item_id]["count"] = max(nodes_map[item_id]["count"], tx_count)

        # Add nodes for consequent items
        for i, item_id in enumerate(consequent_items):
            name = consequent_names[i] if i < len(consequent_names) else item_id
            if item_id not in nodes_map:
                nodes_map[item_id] = {"name": name, "count": tx_count}
            else:
                nodes_map[item_id]["count"] = max(nodes_map[item_id]["count"], tx_count)

        # Add edges (from each antecedent item to each consequent item)
        for ant_id in antecedent_items:
            for con_id in consequent_items:
                edges.append({
                    "source": ant_id,
                    "target": con_id,
                    "value": round(lift, 4),
                })

    nodes = [
        {"id": item_id, "name": info["name"], "category": None, "value": info["count"]}
        for item_id, info in nodes_map.items()
    ]

    return {"nodes": nodes, "edges": edges}


async def get_bundle_recommendations(
    db: AsyncSession,
    store_id: int,
    item_id: str,
    top_n: int = 10,
) -> list:
    """
    Query rules where item_id is in antecedent_items.
    Return top_n consequent items sorted by lift descending.
    """
    # Use JSON contains operator for PostgreSQL
    sql = text("""
        SELECT consequent_items, consequent_names, support, confidence, lift
        FROM association_rules
        WHERE store_id = :store_id
        AND antecedent_items @> :item_json::jsonb
        ORDER BY lift DESC
        LIMIT :limit
    """)
    params = {
        "store_id": store_id,
        "item_json": f'["{item_id}"]',
        "limit": top_n * 3,  # get more to deduplicate
    }
    result = await db.execute(sql, params)
    rows = result.fetchall()

    seen_items = set()
    recommendations = []

    for row in rows:
        consequent_items = row[0] or []
        consequent_names = row[1] or []
        support = row[2]
        confidence = row[3]
        lift = row[4]

        for i, cons_item_id in enumerate(consequent_items):
            if cons_item_id in seen_items:
                continue
            seen_items.add(cons_item_id)
            name = consequent_names[i] if i < len(consequent_names) else cons_item_id
            recommendations.append({
                "item_id": cons_item_id,
                "item_name": name,
                "support": support,
                "confidence": confidence,
                "lift": lift,
            })
            if len(recommendations) >= top_n:
                break

        if len(recommendations) >= top_n:
            break

    return recommendations


async def get_layout_suggestions(
    db: AsyncSession,
    store_id: int,
    start_date: str = None,
    end_date: str = None,
    min_lift: float = 2.0,
) -> list:
    """
    1. Get rules with lift >= min_lift
    2. Build a graph of item associations
    3. Find connected components (clusters of related items)
    4. For each cluster: suggest placing items near each other
    5. Return cluster list with items and suggestion text
    """
    conditions = ["store_id = :store_id", "lift >= :min_lift"]
    params = {"store_id": store_id, "min_lift": min_lift}

    if start_date:
        conditions.append("period_start >= :start_date")
        params["start_date"] = start_date
    if end_date:
        conditions.append("period_end <= :end_date")
        params["end_date"] = end_date

    where_clause = " AND ".join(conditions)

    sql = text(f"""
        SELECT antecedent_items, consequent_items, antecedent_names, consequent_names, lift
        FROM association_rules
        WHERE {where_clause}
        ORDER BY lift DESC
    """)
    result = await db.execute(sql, params)
    rows = result.fetchall()

    if not rows:
        return []

    # Build adjacency graph and collect item info
    item_info = {}  # item_id -> item_name
    adjacency = defaultdict(set)
    edge_lifts = defaultdict(list)  # (item_a, item_b) -> [lift values]

    for row in rows:
        antecedent_items = row[0] or []
        consequent_items = row[1] or []
        antecedent_names = row[2] or []
        consequent_names = row[3] or []
        lift = row[4]

        for i, item_id in enumerate(antecedent_items):
            name = antecedent_names[i] if i < len(antecedent_names) else item_id
            item_info[item_id] = name

        for i, item_id in enumerate(consequent_items):
            name = consequent_names[i] if i < len(consequent_names) else item_id
            item_info[item_id] = name

        # Connect antecedent items to consequent items
        for ant_id in antecedent_items:
            for con_id in consequent_items:
                adjacency[ant_id].add(con_id)
                adjacency[con_id].add(ant_id)
                pair = tuple(sorted([ant_id, con_id]))
                edge_lifts[pair].append(lift)

    # Find connected components using BFS
    visited = set()
    clusters = []

    for item_id in item_info:
        if item_id in visited:
            continue
        # BFS
        component = []
        queue = [item_id]
        visited.add(item_id)
        while queue:
            current = queue.pop(0)
            component.append(current)
            for neighbor in adjacency.get(current, set()):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
        if len(component) >= 2:
            clusters.append(component)

    # Build suggestions for each cluster
    suggestions = []
    for cluster_id, component in enumerate(clusters):
        # Calculate average lift within cluster
        cluster_lifts = []
        for i in range(len(component)):
            for j in range(i + 1, len(component)):
                pair = tuple(sorted([component[i], component[j]]))
                if pair in edge_lifts:
                    cluster_lifts.extend(edge_lifts[pair])

        avg_lift = sum(cluster_lifts) / len(cluster_lifts) if cluster_lifts else 0

        items = [
            {"item_id": item_id, "item_name": item_info.get(item_id, item_id)}
            for item_id in component
        ]

        item_names_str = ", ".join([item_info.get(item_id, item_id) for item_id in component[:5]])
        if len(component) > 5:
            item_names_str += f" 等{len(component)}件商品"

        suggestion_text = (
            f"建议将 {item_names_str} 陈列在相邻区域，"
            f"这些商品的关联购买提升度平均为 {avg_lift:.2f}，"
            f"放置在一起可提高交叉销售机会。"
        )

        suggestions.append({
            "cluster_id": cluster_id + 1,
            "items": items,
            "avg_lift": round(avg_lift, 4),
            "suggestion": suggestion_text,
        })

    # Sort by average lift descending
    suggestions.sort(key=lambda x: x["avg_lift"], reverse=True)

    return suggestions
