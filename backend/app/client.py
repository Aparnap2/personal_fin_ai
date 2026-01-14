"""Supabase client wrapper."""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import os
from supabase import Client, AsyncClient, create_client, ClientOptions


def get_supabase_client() -> Client:
    """Get synchronous Supabase client."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY")

    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY required")

    return create_client(url, key)


async def get_async_supabase_client() -> AsyncClient:
    """Get async Supabase client."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY")

    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY required")

    options = ClientOptions(
        schema="public",
        auto_refresh_token=True,
    )

    return await create_client(url, key, options)


@asynccontextmanager
async def get_supabase() -> AsyncGenerator[AsyncClient, None]:
    """Context manager for async Supabase client."""
    client = await get_async_supabase_client()
    try:
        yield client
    finally:
        pass
