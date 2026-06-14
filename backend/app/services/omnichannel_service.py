from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Optional, List
from datetime import date, datetime, timedelta
import math

from app.schemas.omnichannel import (
    ChannelKPI, ChannelKPIComparison, ChannelTrendPoint,
    AttributionResult, FunnelStep, ChannelFunnel,
    MemberChannelBehavior, MemberOverlap, ChannelInventoryItem,
    UnifiedMemberStats,
)


def _build_store_filter(
    store_ids: Optional[List[int]],
    params: dict,
    table_alias: str = "",
    column: str = "store_id",
) -> str:
    """
    Centralized store permission filter for all omnichannel queries.
    Always returns a SQL fragment that enforces store isolation.
    For admin (store_ids=None): no filter (returns empty string).
    For non-admin: adds AND clause filtering by authorized stores.
    """
    if store_ids is None:
        return ""
    col = f"{table_alias}.{column}" if table_alias else column
    params["_authorized_store_ids"] = store_ids
    return f"AND {col} = ANY(:_authorized_store_ids)"


async def get_channel_kpi_comparison(
    db: AsyncSession,
    store_ids: Optional[List[int]],
    start_date: date,
    end_date: date,
) -> ChannelKPIComparison:
    params: dict = {"start": start_date, "end": end_date}
    store_filter = _build_store_filter(store_ids, params)

    # Current period
    sql = f"""
    SELECT
        channel,
        COALESCE(SUM(total_amount), 0) as gmv,
        COUNT(DISTINCT receipt_no) as order_count,
        CASE WHEN COUNT(DISTINCT receipt_no) > 0
            THEN SUM(total_amount) / COUNT(DISTINCT receipt_no) ELSE 0 END as avg_ticket,
        COUNT(DISTINCT member_id) FILTER (WHERE member_id IS NOT NULL) as member_count
    FROM channel_sales
    WHERE sale_date BETWEEN :start AND :end {store_filter}
    GROUP BY channel
    """
    result = await db.execute(text(sql), params)
    rows = result.fetchall()

    # Previous period of same length for growth rate
    period_days = (end_date - start_date).days + 1
    prev_start = start_date - timedelta(days=period_days)
    prev_end = start_date - timedelta(days=1)
    prev_params: dict = {"start": prev_start, "end": prev_end}
    prev_store_filter = _build_store_filter(store_ids, prev_params)

    prev_sql = f"""
    SELECT channel, COALESCE(SUM(total_amount), 0) as gmv
    FROM channel_sales
    WHERE sale_date BETWEEN :start AND :end {prev_store_filter}
    GROUP BY channel
    """
    prev_result = await db.execute(text(prev_sql), prev_params)
    prev_rows = prev_result.fetchall()
    prev_gmv_map = {r[0]: float(r[1]) for r in prev_rows}

    channels = []
    total_gmv = 0.0
    total_orders = 0
    for row in rows:
        channel_name = row[0]
        gmv = float(row[1])
        order_count = int(row[2])
        avg_ticket = float(row[3])
        member_count = int(row[4])
        total_gmv += gmv
        total_orders += order_count

        prev_gmv = prev_gmv_map.get(channel_name, 0)
        growth_rate = None
        if prev_gmv > 0:
            growth_rate = round((gmv - prev_gmv) / prev_gmv * 100, 2)

        channels.append(ChannelKPI(
            channel=channel_name,
            gmv=round(gmv, 2),
            order_count=order_count,
            avg_ticket=round(avg_ticket, 2),
            member_count=member_count,
            growth_rate_pct=growth_rate,
        ))

    period_str = f"{start_date.isoformat()} ~ {end_date.isoformat()}"
    return ChannelKPIComparison(
        period=period_str,
        channels=channels,
        total_gmv=round(total_gmv, 2),
        total_orders=total_orders,
    )


async def get_channel_trends(
    db: AsyncSession,
    store_ids: Optional[List[int]],
    start_date: date,
    end_date: date,
    granularity: str = "daily",
) -> List[ChannelTrendPoint]:
    params: dict = {"start": start_date, "end": end_date}
    store_filter = _build_store_filter(store_ids, params)

    if granularity == "weekly":
        date_expr = "DATE_TRUNC('week', sale_date)::date"
    elif granularity == "monthly":
        date_expr = "DATE_TRUNC('month', sale_date)::date"
    else:
        date_expr = "sale_date"

    sql = f"""
    SELECT
        {date_expr} as period_date,
        channel,
        COALESCE(SUM(total_amount), 0) as gmv,
        COUNT(DISTINCT receipt_no) as order_count
    FROM channel_sales
    WHERE sale_date BETWEEN :start AND :end {store_filter}
    GROUP BY period_date, channel
    ORDER BY period_date, channel
    """
    result = await db.execute(text(sql), params)
    rows = result.fetchall()

    return [
        ChannelTrendPoint(
            date=str(row[0]),
            channel=row[1],
            gmv=round(float(row[2]), 2),
            order_count=int(row[3]),
        )
        for row in rows
    ]


async def get_channel_attribution(
    db: AsyncSession,
    store_ids: Optional[List[int]],
    start_date: date,
    end_date: date,
    model: str = "last_touch",
) -> List[AttributionResult]:
    params: dict = {"start": start_date, "end": end_date}
    store_filter = _build_store_filter(store_ids, params, table_alias="cs")

    # Get conversions (purchases) in period with member info
    conversions_sql = f"""
    SELECT DISTINCT cs.receipt_no, cs.member_id, cs.channel as conv_channel,
           cs.sale_date, SUM(cs.total_amount) OVER (PARTITION BY cs.receipt_no) as amount
    FROM channel_sales cs
    WHERE cs.sale_date BETWEEN :start AND :end
      AND cs.member_id IS NOT NULL
      {store_filter}
    """
    conv_result = await db.execute(text(conversions_sql), params)
    conversions = conv_result.fetchall()

    # Deduplicate by receipt_no
    seen_receipts = set()
    unique_conversions = []
    for row in conversions:
        if row[0] not in seen_receipts:
            seen_receipts.add(row[0])
            unique_conversions.append(row)

    if not unique_conversions:
        return []

    member_ids = list({row[1] for row in unique_conversions})

    # Get touchpoint history for these members — must also filter by store
    events_params: dict = {
        "member_ids": member_ids,
        "end_dt": datetime.combine(end_date, datetime.max.time()),
    }
    events_store_filter = _build_store_filter(store_ids, events_params)

    events_sql = f"""
    SELECT member_id, channel, event_type, event_date
    FROM channel_member_events
    WHERE member_id = ANY(:member_ids)
      AND event_date <= :end_dt
      {events_store_filter}
    ORDER BY member_id, event_date
    """
    events_result = await db.execute(text(events_sql), events_params)
    events_rows = events_result.fetchall()

    # Build member -> events map
    member_events: dict = {}
    for ev in events_rows:
        mid = ev[0]
        if mid not in member_events:
            member_events[mid] = []
        member_events[mid].append({
            "channel": ev[1],
            "event_type": ev[2],
            "event_date": ev[3],
        })

    # Apply attribution model
    channel_gmv: dict = {}
    channel_orders: dict = {}
    half_life_days = 7.0

    for conv in unique_conversions:
        receipt_no, member_id, conv_channel, sale_date, amount = conv
        amount = float(amount)
        touchpoints = member_events.get(member_id, [])

        # Filter touchpoints before conversion date
        conv_datetime = datetime.combine(sale_date, datetime.max.time())
        relevant = [tp for tp in touchpoints if tp["event_date"] <= conv_datetime]

        if not relevant:
            # Fall back to conversion channel
            channel_gmv[conv_channel] = channel_gmv.get(conv_channel, 0) + amount
            channel_orders[conv_channel] = channel_orders.get(conv_channel, 0) + 1
            continue

        if model == "last_touch":
            last_ch = relevant[-1]["channel"]
            channel_gmv[last_ch] = channel_gmv.get(last_ch, 0) + amount
            channel_orders[last_ch] = channel_orders.get(last_ch, 0) + 1

        elif model == "first_touch":
            first_ch = relevant[0]["channel"]
            channel_gmv[first_ch] = channel_gmv.get(first_ch, 0) + amount
            channel_orders[first_ch] = channel_orders.get(first_ch, 0) + 1

        elif model == "linear":
            unique_channels = list({tp["channel"] for tp in relevant})
            weight = 1.0 / len(unique_channels) if unique_channels else 1.0
            for ch in unique_channels:
                channel_gmv[ch] = channel_gmv.get(ch, 0) + amount * weight
                channel_orders[ch] = channel_orders.get(ch, 0) + weight

        elif model == "time_decay":
            # Exponential decay: weight = 2^(-days_before / half_life)
            weights = []
            for tp in relevant:
                days_before = (conv_datetime - tp["event_date"]).total_seconds() / 86400.0
                w = math.pow(2, -days_before / half_life_days)
                weights.append((tp["channel"], w))
            total_weight = sum(w for _, w in weights)
            if total_weight > 0:
                for ch, w in weights:
                    normalized = w / total_weight
                    channel_gmv[ch] = channel_gmv.get(ch, 0) + amount * normalized
                    channel_orders[ch] = channel_orders.get(ch, 0) + normalized

    # Build results
    total_gmv_all = sum(channel_gmv.values()) if channel_gmv else 1.0
    results = []
    for ch in sorted(channel_gmv.keys(), key=lambda c: channel_gmv[c], reverse=True):
        results.append(AttributionResult(
            channel=ch,
            attributed_gmv=round(channel_gmv[ch], 2),
            attributed_orders=int(round(channel_orders.get(ch, 0))),
            weight=round(channel_gmv[ch] / total_gmv_all, 4) if total_gmv_all > 0 else 0,
        ))

    return results


async def get_channel_funnel(
    db: AsyncSession,
    store_ids: Optional[List[int]],
    start_date: date,
    end_date: date,
    channel: Optional[str] = None,
) -> List[ChannelFunnel]:
    channel_filter = ""
    params: dict = {"start": start_date, "end": end_date}
    store_filter = _build_store_filter(store_ids, params)
    if channel is not None:
        channel_filter = "AND channel = :channel"
        params["channel"] = channel

    # Get distinct channels to report
    channels_sql = f"""
    SELECT DISTINCT channel FROM channel_member_events
    WHERE event_date BETWEEN :start AND :end_dt
      {store_filter} {channel_filter}
    """
    params_with_dt = {**params, "end_dt": datetime.combine(end_date, datetime.max.time())}
    # Override start for event_date comparison
    params_with_dt["start"] = datetime.combine(start_date, datetime.min.time())
    ch_result = await db.execute(text(channels_sql), params_with_dt)
    channel_list = [r[0] for r in ch_result.fetchall()]

    funnel_steps = ["browse", "add_cart", "purchase"]
    results = []

    for ch in channel_list:
        step_params = {
            "start": datetime.combine(start_date, datetime.min.time()),
            "end_dt": datetime.combine(end_date, datetime.max.time()),
            "ch": ch,
        }
        step_store_filter = _build_store_filter(store_ids, step_params)

        steps_data = []
        for step in funnel_steps:
            step_sql = f"""
            SELECT COUNT(DISTINCT member_id)
            FROM channel_member_events
            WHERE event_date BETWEEN :start AND :end_dt
              AND channel = :ch
              AND event_type = :event_type
              {step_store_filter}
            """
            step_params_full = {**step_params, "event_type": step}
            res = await db.execute(text(step_sql), step_params_full)
            count = int(res.scalar() or 0)
            steps_data.append(count)

        # Repeat purchase: members with 2+ purchases
        repeat_sql = f"""
        SELECT COUNT(*) FROM (
            SELECT member_id
            FROM channel_member_events
            WHERE event_date BETWEEN :start AND :end_dt
              AND channel = :ch
              AND event_type = 'purchase'
              {step_store_filter}
            GROUP BY member_id
            HAVING COUNT(*) >= 2
        ) sub
        """
        rep_res = await db.execute(text(repeat_sql), step_params)
        repeat_count = int(rep_res.scalar() or 0)
        steps_data.append(repeat_count)

        # Build funnel steps with conversion rates
        step_names = ["browse", "add_cart", "purchase", "repeat_purchase"]
        funnel_steps_out = []
        for i, (name, count) in enumerate(zip(step_names, steps_data)):
            conv_rate = None
            if i > 0 and steps_data[i - 1] > 0:
                conv_rate = round(count / steps_data[i - 1] * 100, 2)
            funnel_steps_out.append(FunnelStep(
                step_name=name,
                count=count,
                conversion_rate=conv_rate,
            ))

        results.append(ChannelFunnel(channel=ch, steps=funnel_steps_out))

    return results


async def get_member_cross_channel_behavior(
    db: AsyncSession,
    member_id: int,
    authorized_stores: Optional[List[int]] = None,
) -> MemberChannelBehavior:
    params: dict = {"member_id": member_id}
    store_filter = _build_store_filter(authorized_stores, params)

    sql = f"""
    SELECT channel, event_type, event_date, item_id, amount, session_id, device_type, store_id
    FROM channel_member_events
    WHERE member_id = :member_id {store_filter}
    ORDER BY event_date
    """
    result = await db.execute(text(sql), params)
    rows = result.fetchall()

    events = []
    channels_set: set = set()
    spend_by_channel: dict = {}
    first_channel = None
    last_channel = None

    for row in rows:
        ch = row[0]
        event_type = row[1]
        event_date = row[2]
        item_id = row[3]
        amount = row[4]
        session_id = row[5]
        device_type = row[6]

        channels_set.add(ch)
        if first_channel is None:
            first_channel = ch
        last_channel = ch

        if amount and event_type == "purchase":
            spend_by_channel[ch] = spend_by_channel.get(ch, 0) + float(amount)

        events.append({
            "channel": ch,
            "event_type": event_type,
            "event_date": str(event_date),
            "item_id": item_id,
            "amount": float(amount) if amount else None,
            "session_id": session_id,
            "device_type": device_type,
        })

    return MemberChannelBehavior(
        member_id=member_id,
        events=events,
        channels_used=sorted(channels_set),
        total_spend_by_channel=spend_by_channel,
        first_channel=first_channel or "",
        last_channel=last_channel or "",
    )


async def get_channel_member_overlap(
    db: AsyncSession,
    store_ids: Optional[List[int]],
    start_date: date,
    end_date: date,
) -> MemberOverlap:
    params: dict = {"start": start_date, "end": end_date}
    store_filter = _build_store_filter(store_ids, params)

    sql = f"""
    WITH member_channels AS (
        SELECT
            member_id,
            ARRAY_AGG(DISTINCT channel) as channels,
            BOOL_OR(channel = 'online') as has_online,
            BOOL_OR(channel = 'offline') as has_offline,
            BOOL_OR(channel = 'o2o') as has_o2o
        FROM channel_sales
        WHERE sale_date BETWEEN :start AND :end
          AND member_id IS NOT NULL
          {store_filter}
        GROUP BY member_id
    )
    SELECT
        COUNT(*) FILTER (WHERE has_online AND NOT has_offline AND NOT has_o2o) as online_only,
        COUNT(*) FILTER (WHERE has_offline AND NOT has_online AND NOT has_o2o) as offline_only,
        COUNT(*) FILTER (WHERE has_online AND has_offline) as both_channels,
        COUNT(*) FILTER (WHERE has_o2o) as o2o_members,
        COUNT(*) as total_members
    FROM member_channels
    """
    result = await db.execute(text(sql), params)
    row = result.fetchone()

    if row is None:
        return MemberOverlap(
            online_only=0, offline_only=0, both_channels=0,
            o2o_members=0, total_members=0,
        )

    return MemberOverlap(
        online_only=int(row[0] or 0),
        offline_only=int(row[1] or 0),
        both_channels=int(row[2] or 0),
        o2o_members=int(row[3] or 0),
        total_members=int(row[4] or 0),
    )


async def get_inventory_by_channel(
    db: AsyncSession,
    store_id: int,
    snapshot_date: Optional[date] = None,
) -> List[ChannelInventoryItem]:
    if snapshot_date is None:
        # Get latest snapshot date for this store
        date_sql = """
        SELECT MAX(snapshot_date) FROM channel_inventory WHERE store_id = :store_id
        """
        date_result = await db.execute(text(date_sql), {"store_id": store_id})
        snapshot_date = date_result.scalar()
        if snapshot_date is None:
            return []

    sql = """
    SELECT
        ci.item_id,
        MAX(cs.item_name) as item_name,
        COALESCE(SUM(ci.available_qty) FILTER (WHERE ci.channel = 'online'), 0) as online_available,
        COALESCE(SUM(ci.available_qty) FILTER (WHERE ci.channel = 'offline'), 0) as offline_available,
        COALESCE(SUM(ci.reserved_qty) FILTER (WHERE ci.channel = 'online'), 0) as online_reserved,
        COALESCE(SUM(ci.reserved_qty) FILTER (WHERE ci.channel = 'offline'), 0) as offline_reserved
    FROM channel_inventory ci
    LEFT JOIN (
        SELECT DISTINCT item_id, item_name FROM channel_sales WHERE store_id = :store_id
    ) cs ON cs.item_id = ci.item_id
    WHERE ci.store_id = :store_id AND ci.snapshot_date = :snapshot_date
    GROUP BY ci.item_id
    ORDER BY ci.item_id
    """
    result = await db.execute(text(sql), {
        "store_id": store_id,
        "snapshot_date": snapshot_date,
    })
    rows = result.fetchall()

    return [
        ChannelInventoryItem(
            item_id=row[0],
            item_name=row[1],
            online_available=float(row[2]),
            offline_available=float(row[3]),
            online_reserved=float(row[4]),
            offline_reserved=float(row[5]),
        )
        for row in rows
    ]


async def get_unified_member_stats(
    db: AsyncSession,
    store_ids: Optional[List[int]],
    start_date: date,
    end_date: date,
) -> UnifiedMemberStats:
    params: dict = {"start": start_date, "end": end_date}
    store_filter = _build_store_filter(store_ids, params)

    # Total unique members and cross-channel %
    overview_sql = f"""
    WITH member_channels AS (
        SELECT
            member_id,
            COUNT(DISTINCT channel) as channel_count,
            SUM(total_amount) as total_spend
        FROM channel_sales
        WHERE sale_date BETWEEN :start AND :end
          AND member_id IS NOT NULL
          {store_filter}
        GROUP BY member_id
    )
    SELECT
        COUNT(*) as total_members,
        COUNT(*) FILTER (WHERE channel_count > 1) as cross_channel_members,
        COALESCE(AVG(total_spend), 0) as avg_ltv
    FROM member_channels
    """
    ov_result = await db.execute(text(overview_sql), params)
    ov_row = ov_result.fetchone()

    total_members = int(ov_row[0] or 0)
    cross_channel_members = int(ov_row[1] or 0)
    avg_ltv = float(ov_row[2] or 0)
    cross_channel_pct = round(
        cross_channel_members / total_members * 100, 2
    ) if total_members > 0 else 0.0

    # Per-channel stats
    params_with_today = {**params, "today": date.today()}
    channel_sql = f"""
    SELECT
        channel,
        COUNT(DISTINCT member_id) as member_count,
        CASE WHEN COUNT(DISTINCT member_id) > 0
            THEN COUNT(DISTINCT receipt_no)::float / COUNT(DISTINCT member_id)
            ELSE 0 END as avg_frequency,
        COALESCE(AVG(days_since_last), 0) as avg_recency_days,
        CASE WHEN COUNT(DISTINCT member_id) > 0
            THEN SUM(total_amount) / COUNT(DISTINCT member_id)
            ELSE 0 END as avg_spend
    FROM (
        SELECT
            channel,
            member_id,
            receipt_no,
            total_amount,
            (:today - MAX(sale_date)) as days_since_last
        FROM channel_sales
        WHERE sale_date BETWEEN :start AND :end
          AND member_id IS NOT NULL
          {store_filter}
        GROUP BY channel, member_id, receipt_no, total_amount
    ) sub
    GROUP BY channel
    ORDER BY channel
    """
    ch_result = await db.execute(text(channel_sql), params_with_today)
    ch_rows = ch_result.fetchall()

    by_channel = []
    for row in ch_rows:
        by_channel.append({
            "channel": row[0],
            "member_count": int(row[1]),
            "avg_frequency": round(float(row[2]), 2),
            "avg_recency_days": round(float(row[3]), 1),
            "avg_spend": round(float(row[4]), 2),
        })

    return UnifiedMemberStats(
        total_members=total_members,
        cross_channel_pct=cross_channel_pct,
        avg_ltv=round(avg_ltv, 2),
        by_channel=by_channel,
    )
