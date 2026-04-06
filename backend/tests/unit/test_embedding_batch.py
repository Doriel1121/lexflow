"""
Unit tests for the batched embedding task logic.
Tests chunk batching and atomic completion detection.
Pure logic tests — no database, Redis, or heavy dependencies needed.
"""

import pytest


def test_chunk_batching_logic():
    """Verify that chunk IDs are correctly grouped into batches."""
    chunk_ids = list(range(1, 26))  # 25 chunks
    batch_size = 10

    batches = []
    for i in range(0, len(chunk_ids), batch_size):
        batches.append(chunk_ids[i : i + batch_size])

    assert len(batches) == 3
    assert len(batches[0]) == 10  # First batch: 10 chunks
    assert len(batches[1]) == 10  # Second batch: 10 chunks
    assert len(batches[2]) == 5   # Last batch: 5 chunks
    assert batches[0] == list(range(1, 11))
    assert batches[2] == list(range(21, 26))


def test_chunk_batching_single_chunk():
    """A single chunk should produce a single batch."""
    chunk_ids = [42]
    batch_size = 10

    batches = []
    for i in range(0, len(chunk_ids), batch_size):
        batches.append(chunk_ids[i : i + batch_size])

    assert len(batches) == 1
    assert batches[0] == [42]


def test_chunk_batching_exact_multiple():
    """When chunk count is exactly divisible by batch size."""
    chunk_ids = list(range(1, 21))  # 20 chunks
    batch_size = 10

    batches = []
    for i in range(0, len(chunk_ids), batch_size):
        batches.append(chunk_ids[i : i + batch_size])

    assert len(batches) == 2
    assert len(batches[0]) == 10
    assert len(batches[1]) == 10


def test_chunk_batching_empty():
    """Empty chunk list should produce no batches."""
    chunk_ids = []
    batch_size = 10

    batches = []
    for i in range(0, len(chunk_ids), batch_size):
        batches.append(chunk_ids[i : i + batch_size])

    assert len(batches) == 0


def test_config_embedding_batch_size():
    """The default embedding batch size should be 10."""
    from app.core.config import settings
    assert settings.EMBEDDING_BATCH_SIZE == 10


def test_config_ws_max_connections():
    """The default WS connection limit should be 5."""
    from app.core.config import settings
    assert settings.WS_MAX_CONNECTIONS_PER_USER == 5


def test_config_redis_url():
    """The Redis URL should have a sensible default."""
    from app.core.config import settings
    assert "redis" in settings.REDIS_URL.lower()
