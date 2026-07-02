from services.payload_cache import PayloadCache


def test_cache_set_and_get():
    cache = PayloadCache(maxsize=2)
    cache.set('{"a": 1}', "encoded1")
    assert cache.get('{"a": 1}') == "encoded1"

    # Miss
    assert cache.get('{"b": 2}') is None

def test_cache_lru_eviction():
    cache = PayloadCache(maxsize=2)
    cache.set("A", "encA")
    cache.set("B", "encB")
    cache.set("C", "encC")  # Evicts A

    assert cache.get("A") is None
    assert cache.get("B") == "encB"
    assert cache.get("C") == "encC"

def test_cache_update_existing():
    cache = PayloadCache(maxsize=2)
    cache.set("A", "encA")
    cache.set("A", "encA-new")
    # Should move to end and update
    cache.set("B", "encB") # B is MRU, A is LRU
    cache.set("C", "encC") # C is MRU, B is LRU. A is evicted.

    assert cache.get("A") is None
    assert cache.get("B") == "encB"
    assert cache.get("C") == "encC"

def test_cache_stats_and_clear():
    cache = PayloadCache(maxsize=10)
    cache.set("A", "encA")
    cache.get("A") # hit
    cache.get("B") # miss

    stats = cache.stats()
    assert stats["size"] == 1
    assert stats["maxsize"] == 10
    assert stats["hits"] == 1
    assert stats["misses"] == 1
    assert stats["hit_rate_pct"] == 50.0

    cache.clear()
    stats = cache.stats()
    assert stats["size"] == 0
    assert stats["hits"] == 0
