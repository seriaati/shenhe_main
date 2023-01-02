from datetime import datetime, time, timedelta

import aiosqlite
from dateutil import parser
from utility.utils import get_dt_now, time_in_range


async def check_flow_account(user_id: int, db: aiosqlite.Connection) -> bool:
    """Check if a user has a flow account."""
    async with db.execute(
        "SELECT * FROM flow_accounts WHERE user_id = ?", (user_id,)
    ) as cursor:
        return bool(await cursor.fetchone())


async def register_flow_account(user_id: int, db: aiosqlite.Connection) -> None:
    """Register a user's flow account."""
    default_time = datetime.utcnow() - timedelta(days=1)
    await db.execute(
        "INSERT INTO flow_accounts (user_id, flow, morning, noon, night) VALUES (?, ?, ?, ?, ?)",
        (user_id, 0, default_time, default_time, default_time),
    )
    await db.commit()


async def flow_transaction(user_id: int, amount: int, db: aiosqlite.Connection) -> None:
    """Change a user's flow balance."""
    check = await check_flow_account(user_id, db)
    if not check:
        await register_flow_account(user_id, db)
    await db.execute(
        "UPDATE flow_accounts SET flow = flow + ?, last_trans = ? WHERE user_id = ?",
        (amount, get_dt_now(), user_id),
    )
    await db.execute("UPDATE bank SET flow = flow - ?", (amount,))
    await db.commit()

async def remove_flow_account(user_id: int, db: aiosqlite.Connection) -> None:
    """Remove a user's flow account."""
    await db.execute("DELETE FROM flow_accounts WHERE user_id = ?", (user_id,))
    await db.commit()


async def get_user_flow(user_id: int, db: aiosqlite.Connection) -> int:
    """Get a user's flow balance."""
    check = await check_flow_account(user_id, db)
    if not check:
        await register_flow_account(user_id, db)
    async with db.execute(
        "SELECT flow FROM flow_accounts WHERE user_id = ?", (user_id,)
    ) as cursor:
        return (await cursor.fetchone())[0]


async def get_blank_flow(db: aiosqlite.Connection) -> int:
    """Get the blank flow balance."""
    async with db.execute("SELECT flow FROM bank") as cursor:
        return (await cursor.fetchone())[0]


async def free_flow(
    user_id: int, start: time, end: time, time_type: str, db: aiosqlite.Connection
) -> bool:
    check = await check_flow_account(user_id, db)
    if not check:
        await register_flow_account(user_id, db)
    now = get_dt_now()
    if time_in_range(start, end, now.time()):
        async with db.execute(
            f"SELECT {time_type} FROM flow_accounts WHERE user_id = ?",
            (user_id,),
        ) as c:
            last_give = (await c.fetchone())[0]
        if parser.parse(last_give).day != now.day:
            await flow_transaction(user_id, 1, db)
            await db.execute(
                f"UPDATE flow_accounts SET {time_type} = ? WHERE user_id = ?",
                (now, user_id),
            )
            await db.commit()
            return True
    return False
