import typing

import asyncpg


async def delete_shop_item(
    name: str,
    pool: asyncpg.Pool,
) -> None:
    """Delete a shop item from the database.

    Args:
        name (str): Name of the shop item.
        pool (asyncpg.Pool): Database pool.
    """
    await pool.execute("DELETE FROM flow_shop WHERE name = $1", name)


async def create_shop_item(
    name: str,
    flow: int,
    pool: asyncpg.Pool,
) -> None:
    """Create a shop item in the database.

    Args:
        name (str): Name of the shop item.
        flow (int): Price of the shop item.
        pool (asyncpg.Pool): Database pool.
    """
    await pool.execute("INSERT INTO flow_shop VALUES ($1, $2)", name, flow)


async def get_item_names(pool: asyncpg.Pool) -> typing.List[str]:
    """Get all shop item names.

    Args:
        pool (asyncpg.Pool): Database pool.

    Returns:
        typing.List[str]: List of shop item names.
    """
    return await pool.fetchval("SELECT ARRAY(SELECT name FROM flow_shop)")
