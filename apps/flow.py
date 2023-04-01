import logging
from datetime import datetime, time, timedelta

import asyncpg

from dev.enum import TimeType
from utility.utils import get_dt_now, time_in_range


async def register_flow_account(user_id: int, pool: asyncpg.Pool) -> None:
    """Register a user's flow account.

    Args:
        user_id (int): The user's ID.
        pool (asyncpg.Pool): The database pool.
    """
    default = get_dt_now() - timedelta(days=1)
    await pool.execute(
        "INSERT INTO flow_accounts (user_id, morning, noon, night) VALUES ($1, $2, $3, $4) ON CONFLICT DO NOTHING",
        user_id,
        default,
        default,
        default,
    )


async def flow_transaction(user_id: int, amount: int, pool: asyncpg.Pool) -> None:
    """Transfer flow from the bank to a user's flow account.

    Args:
        user_id (int): The user's ID.
        amount (int): The amount of flow to transfer.
        pool (asyncpg.Pool): The database pool.
    """
    logging.info(f"Transferring {amount} flow to {user_id}")
    await register_flow_account(user_id, pool)
    await pool.execute(
        "UPDATE flow_accounts SET flow = flow + $1 WHERE user_id = $2", amount, user_id
    )
    await pool.execute("UPDATE bank SET flow = flow - $1", amount)


async def remove_flow_account(user_id: int, pool: asyncpg.Pool) -> None:
    """Remove a user's flow account.

    Args:
        user_id (int): The user's ID.
        pool (asyncpg.Pool): The database pool.
    """
    logging.info(f"Removing flow account for {user_id}")
    flow = await get_user_flow(user_id, pool)
    await flow_transaction(user_id, flow, pool)
    await pool.execute("DELETE FROM flow_accounts WHERE user_id = $1", user_id)


async def get_user_flow(user_id: int, pool: asyncpg.Pool) -> int:
    """Get a user's flow balance.

    Args:
        user_id (int): The user's ID.
        pool (asyncpg.Pool): The database pool.

    Returns:
        int: The user's flow balance.
    """
    await register_flow_account(user_id, pool)
    return await pool.fetchval(
        "SELECT flow FROM flow_accounts WHERE user_id = $1", user_id
    )


async def get_blank_flow(pool: asyncpg.Pool) -> int:
    """Get the amount of flow in the bank.

    Args:
        pool (asyncpg.Pool): The database pool.

    Returns:
        int: The amount of flow in the bank.
    """
    return await pool.fetchval("SELECT flow FROM bank")


async def free_flow(
    user_id: int, start: time, end: time, time_type: TimeType, pool: asyncpg.Pool
) -> bool:
    """Give a user free flow if the current time is in the range [start, end], and the last time they got free flow was not today. Returns True if the user got free flow, False otherwise.

    Args:
        user_id (int): The user's ID.
        start (time): Beginning of the time range.
        end (time): End of the time range.
        time_type (TimeType): Morning, noon, or night.
        pool (asyncpg.Pool): The database pool.

    Returns:
        bool: True if the user got free flow, False otherwise.
    """
    await register_flow_account(user_id, pool)
    now = get_dt_now()
    if time_in_range(start, end, now.time()):
        last_give: datetime = await pool.fetchval(
            f"SELECT {time_type.value} FROM flow_accounts WHERE user_id = $1", user_id
        )
        if last_give is not None and last_give.day != now.day:
            logging.info(
                f"Free flow for {user_id}, lastgive is {last_give} ({time_type.value})"
            )
            await flow_transaction(user_id, 1, pool)
            await pool.execute(
                f"UPDATE flow_accounts SET {time_type.value} = $1 WHERE user_id = $2",
                now,
                user_id,
            )
            return True
    return False
