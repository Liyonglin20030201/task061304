import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Optional, List


async def get_rfm_segmentation(
    db: AsyncSession, store_ids: Optional[List[int]] = None
) -> dict:
    store_filter = ""
    params = {}
    if store_ids:
        store_filter = "AND mt.store_id = ANY(:store_ids)"
        params["store_ids"] = store_ids

    sql = f"""
    SELECT
        m.id as member_id,
        m.member_no,
        m.name,
        CURRENT_DATE - MAX(mt.transaction_date)::date as recency,
        COUNT(DISTINCT mt.receipt_no) as frequency,
        COALESCE(SUM(mt.amount), 0) as monetary
    FROM members m
    LEFT JOIN member_transactions mt ON mt.member_id = m.id
    WHERE m.is_active = 1 {store_filter}
    GROUP BY m.id, m.member_no, m.name
    HAVING COUNT(mt.id) > 0
    """
    result = await db.execute(text(sql), params)
    rows = result.fetchall()

    if not rows:
        return {"segments": [], "summary": {}}

    members = []
    for row in rows:
        members.append({
            "member_id": row[0], "member_no": row[1], "name": row[2],
            "recency": row[3] if row[3] else 999,
            "frequency": row[4], "monetary": float(row[5]),
        })

    r_values = [m["recency"] for m in members]
    f_values = [m["frequency"] for m in members]
    m_values = [m["monetary"] for m in members]

    r_thresholds = np.percentile(r_values, [25, 50, 75])
    f_thresholds = np.percentile(f_values, [25, 50, 75])
    m_thresholds = np.percentile(m_values, [25, 50, 75])

    def score(value, thresholds, reverse=False):
        if reverse:
            if value <= thresholds[0]: return 4
            if value <= thresholds[1]: return 3
            if value <= thresholds[2]: return 2
            return 1
        else:
            if value <= thresholds[0]: return 1
            if value <= thresholds[1]: return 2
            if value <= thresholds[2]: return 3
            return 4

    segment_map = {
        (4, 4, 4): "重要价值客户",
        (4, 4, 3): "重要价值客户",
        (4, 3, 4): "重要发展客户",
        (4, 3, 3): "重要发展客户",
        (3, 4, 4): "重要保持客户",
        (3, 4, 3): "重要保持客户",
        (3, 3, 4): "重要挽留客户",
        (3, 3, 3): "一般价值客户",
        (2, 2, 2): "一般发展客户",
        (1, 1, 1): "流失客户",
    }

    def get_segment(r, f, m):
        key = (r, f, m)
        if key in segment_map:
            return segment_map[key]
        avg = (r + f + m) / 3
        if avg >= 3.5: return "重要价值客户"
        if avg >= 3: return "重要保持客户"
        if avg >= 2.5: return "一般价值客户"
        if avg >= 2: return "一般发展客户"
        return "流失客户"

    segments = {}
    for m in members:
        r_score = score(m["recency"], r_thresholds, reverse=True)
        f_score = score(m["frequency"], f_thresholds)
        m_score = score(m["monetary"], m_thresholds)
        seg = get_segment(r_score, f_score, m_score)
        m["rfm_score"] = f"{r_score}{f_score}{m_score}"
        m["segment"] = seg
        segments.setdefault(seg, []).append(m)

    summary = {
        seg: {"count": len(members_list), "avg_monetary": round(np.mean([m["monetary"] for m in members_list]), 2)}
        for seg, members_list in segments.items()
    }

    return {
        "total_members": len(members),
        "summary": summary,
        "segments": [
            {"segment": seg, "count": data["count"], "avg_monetary": data["avg_monetary"]}
            for seg, data in sorted(summary.items(), key=lambda x: -x[1]["count"])
        ],
    }
