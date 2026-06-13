import pandas as pd
import numpy as np
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
from app.config import get_settings
from app.services.cleaning_service import clean_dataframe

settings = get_settings()


async def process_import_file(task_id: int, file_path: str, data_type: str):
    engine = create_async_engine(settings.DATABASE_URL)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        try:
            await db.execute(
                text("UPDATE import_tasks SET status='processing', started_at=:now WHERE id=:id"),
                {"id": task_id, "now": datetime.now(timezone.utc)},
            )
            await db.commit()

            if file_path.endswith(".csv"):
                total_rows = sum(1 for _ in open(file_path, encoding="utf-8")) - 1
            else:
                df_temp = pd.read_excel(file_path)
                total_rows = len(df_temp)

            await db.execute(
                text("UPDATE import_tasks SET total_rows=:total WHERE id=:id"),
                {"id": task_id, "total": total_rows},
            )
            await db.commit()

            chunk_size = settings.CHUNK_SIZE
            processed = 0
            success = 0
            errors = 0
            duplicates = 0

            if file_path.endswith(".csv"):
                reader = pd.read_csv(file_path, chunksize=chunk_size, encoding="utf-8")
            else:
                df_full = pd.read_excel(file_path)
                reader = [df_full[i:i + chunk_size] for i in range(0, len(df_full), chunk_size)]

            for chunk in reader:
                cleaned, chunk_errors, chunk_dupes = clean_dataframe(chunk, data_type)
                batch_success = await _insert_batch(db, cleaned, data_type)
                processed += len(chunk)
                success += batch_success
                errors += chunk_errors
                duplicates += chunk_dupes

                await db.execute(
                    text("""UPDATE import_tasks SET processed_rows=:p, success_rows=:s,
                            error_rows=:e, duplicate_rows=:d WHERE id=:id"""),
                    {"p": processed, "s": success, "e": errors, "d": duplicates, "id": task_id},
                )
                await db.commit()

                await _log_task(db, task_id, "info", f"已处理 {processed}/{total_rows} 行")

            await db.execute(
                text("UPDATE import_tasks SET status='completed', completed_at=:now WHERE id=:id"),
                {"id": task_id, "now": datetime.now(timezone.utc)},
            )
            await db.commit()

        except Exception as e:
            await db.execute(
                text("UPDATE import_tasks SET status='failed', error_details=:err WHERE id=:id"),
                {"id": task_id, "err": str(e)},
            )
            await db.commit()
            await _log_task(db, task_id, "error", f"导入失败: {str(e)}")
    await engine.dispose()


async def _insert_batch(db: AsyncSession, df: pd.DataFrame, data_type: str) -> int:
    if df.empty:
        return 0

    table_map = {
        "sales": "sales",
        "inventory": "inventory",
        "members": "members",
        "promotions": "promotions",
        "traffic": "traffic",
        "weather": "weather",
    }
    table = table_map.get(data_type)
    if not table:
        return 0

    records = df.where(pd.notnull(df), None).to_dict("records")
    columns = list(records[0].keys())
    col_str = ", ".join(columns)
    val_placeholders = ", ".join([f":{c}" for c in columns])

    conflict_keys = {
        "sales": "store_id, receipt_no, item_id",
        "inventory": "store_id, item_id, snapshot_date",
        "traffic": "store_id, traffic_date, hour",
        "weather": "city, weather_date",
    }

    if data_type in conflict_keys:
        sql = f"""INSERT INTO {table} ({col_str}) VALUES ({val_placeholders})
                  ON CONFLICT ({conflict_keys[data_type]}) DO NOTHING"""
    else:
        sql = f"INSERT INTO {table} ({col_str}) VALUES ({val_placeholders})"

    inserted = 0
    for record in records:
        try:
            await db.execute(text(sql), record)
            inserted += 1
        except Exception:
            pass
    await db.commit()
    return inserted


async def _log_task(db: AsyncSession, task_id: int, level: str, message: str):
    await db.execute(
        text("INSERT INTO task_logs (task_id, level, message, created_at) VALUES (:tid, :lvl, :msg, :now)"),
        {"tid": task_id, "lvl": level, "msg": message, "now": datetime.now(timezone.utc)},
    )
    await db.commit()
