"""Test script for embedding_server.py daemon — ping + embed + batch + fallback.

Run: python tests/test_daemon.py
Requires the daemon to be running (auto-started by zvec_hybrid_search.py).
"""
import json
import os
import socket
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import SKILL_DIR

STATE_FILE = os.path.join(SKILL_DIR, "okf", ".embedding_server.json")


def daemon_request(req, timeout=120):
    """Send a JSON-line request to the daemon, return response dict."""
    with open(STATE_FILE, 'r') as f:
        state = json.load(f)
    port = state['port']
    with socket.create_connection(("127.0.0.1", port), timeout=timeout) as s:
        s.sendall((json.dumps(req) + "\n").encode())
        data = b""
        while b"\n" not in data:
            chunk = s.recv(65536)
            if not chunk:
                break
            data += chunk
    return json.loads(data.decode())


def main():
    # 1. Ping test
    print("1. Ping test...")
    resp = daemon_request({"method": "ping"}, timeout=10)
    assert resp.get("pong") is True, f"Ping failed: {resp}"
    print(f"   OK: {resp}")

    # 2. Single embed test
    print("2. Single embed test...")
    t = time.time()
    resp = daemon_request({"method": "embed_batch", "texts": ["hello world"]}, timeout=120)
    elapsed = time.time() - t
    assert resp.get("error") is None, f"Embed failed: {resp}"
    embs = resp["embeddings"]
    assert len(embs) == 1, f"Expected 1 embedding, got {len(embs)}"
    assert len(embs[0]) == 384, f"Expected dim 384, got {len(embs[0])}"
    print(f"   OK: dim={len(embs[0])}, time={elapsed:.3f}s")

    # 3. Batch embed test
    print("3. Batch embed test (3 texts)...")
    t = time.time()
    resp = daemon_request({"method": "embed_batch", "texts": ["text one", "text two", "text three"]}, timeout=30)
    elapsed = time.time() - t
    assert resp.get("error") is None, f"Batch embed failed: {resp}"
    embs = resp["embeddings"]
    assert len(embs) == 3, f"Expected 3 embeddings, got {len(embs)}"
    print(f"   OK: {len(embs)} embeddings, time={elapsed:.3f}s")

    # 4. zvec_hybrid_search integration test
    print("4. zvec_hybrid_search.get_embedding via daemon...")
    from zvec_hybrid_search import get_embedding, get_embeddings_batch
    vec = get_embedding("test sentence for embedding")
    assert len(vec) == 384, f"Expected dim 384, got {len(vec)}"
    print(f"   OK: dim={len(vec)}")

    vecs = get_embeddings_batch(["text one", "text two"])
    assert len(vecs) == 2, f"Expected 2 embeddings, got {len(vecs)}"
    print(f"   OK: {len(vecs)} embeddings")

    print("\nAll daemon tests passed!")


if __name__ == "__main__":
    main()
