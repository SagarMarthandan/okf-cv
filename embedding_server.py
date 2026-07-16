"""
embedding_server.py — Local daemon that holds the SentenceTransformer model
in memory, serving embedding requests over a TCP socket on 127.0.0.1.

Eliminates redundant model loads (~21s each on CPU) across multiple
zvec_hybrid_search.py invocations in a single pipeline run. Auto-started by
zvec_hybrid_search.py when needed; auto-shuts down after 30 min of inactivity.

Protocol (JSON-line over TCP — one request per connection, newline-delimited):
  Client -> {"method": "ping"}
  Server -> {"pong": true, "error": null}
  Client -> {"method": "embed_batch", "texts": ["text1", "text2"]}
  Server -> {"embeddings": [[...], [...]], "error": null}

State file: okf/.embedding_server.json  (port + PID for client coordination)
Log file:   okf/.embedding_server.log   (also gitignored via *.log)

Usage (manual):
  python embedding_server.py            # start daemon (foreground)
  python embedding_server.py --stop     # stop running daemon
  python embedding_server.py --status   # check if running
"""
import json
import os
import socket
import socketserver
import sys
import threading
import time

from config import EMBEDDING_MODEL_NAME, SKILL_DIR

# ─── Config ───────────────────────────────────────────────────────────────────

IDLE_TIMEOUT = 30 * 60  # 30 minutes — shut down after this many seconds of no requests
PORT_RANGE = list(range(54321, 54326))  # try 54321 first, fall back to 54322-54325
STATE_FILE = os.path.join(SKILL_DIR, "okf", ".embedding_server.json")
LOG_FILE = os.path.join(SKILL_DIR, "okf", ".embedding_server.log")

# ─── Model holder ─────────────────────────────────────────────────────────────

_model = None
_model_ready = threading.Event()
_model_lock = threading.Lock()  # Serialize model.encode() calls
_last_request_time = time.time()


def _log(msg):
    """Log to stdout (redirected to log file when auto-started)."""
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def _load_model():
    """Load the SentenceTransformer model (called in the main thread)."""
    global _model
    try:
        import torch
        torch.set_num_threads(1)  # Avoid PyTorch cross-thread crashes on CPU
        from sentence_transformers import SentenceTransformer
        _log(f"Loading SentenceTransformer model '{EMBEDDING_MODEL_NAME}'...")
        _model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        _log("Model loaded successfully. Ready to serve embed requests.")
        _model_ready.set()
    except Exception as e:
        _log(f"FATAL: Failed to load model: {e}")
        import traceback
        traceback.print_exc()
        os._exit(1)


# ─── Request handler ──────────────────────────────────────────────────────────

class EmbeddingHandler(socketserver.BaseRequestHandler):
    """Handle one TCP connection: read one JSON-line request, send one response."""

    def handle(self):
        global _last_request_time
        _last_request_time = time.time()
        try:
            data = self._readline()
            if not data:
                return
            req = json.loads(data.decode('utf-8'))
            method = req.get("method", "")

            if method == "ping":
                resp = {"pong": True, "error": None}

            elif method == "embed_batch":
                texts = req.get("texts", [])
                # Block until model is loaded (the daemon loads the model in the
                # main thread before calling serve_forever, so this returns
                # immediately for requests after startup).
                _model_ready.wait()
                with _model_lock:
                    embeddings = _model.encode(texts, show_progress_bar=False)
                resp = {
                    "embeddings": [[float(x) for x in emb] for emb in embeddings],
                    "error": None,
                }

            else:
                resp = {"error": f"Unknown method: {method}"}

            self._send(resp)
            _last_request_time = time.time()

        except Exception as e:
            try:
                self._send({"error": str(e)})
            except Exception:
                pass

    def _readline(self):
        """Read until newline (one JSON-line request)."""
        data = b""
        while b"\n" not in data:
            chunk = self.request.recv(65536)
            if not chunk:
                break
            data += chunk
        return data.strip()

    def _send(self, obj):
        """Send one JSON-line response."""
        self.request.sendall((json.dumps(obj) + "\n").encode('utf-8'))


class EmbeddingTCPServer(socketserver.TCPServer):
    """Single-threaded TCP server.

    PyTorch on Windows CPU crashes when model.encode() is called from a
    different thread than the one that loaded the model. Single-threaded
    mode ensures both load and encode happen in the main thread.
    """
    allow_reuse_address = True


# ─── Idle watchdog ────────────────────────────────────────────────────────────

def _idle_watchdog():
    """Shut down the daemon after IDLE_TIMEOUT seconds of no requests."""
    while True:
        time.sleep(30)
        if time.time() - _last_request_time > IDLE_TIMEOUT:
            _log(f"Idle for {IDLE_TIMEOUT // 60} min. Shutting down.")
            os._exit(0)


# ─── State file ───────────────────────────────────────────────────────────────

def _write_state(port):
    """Write the daemon's port + PID to the state file for client coordination."""
    state = {"port": port, "pid": os.getpid(), "started": time.time()}
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f)


def _read_state():
    """Read the daemon state file. Returns dict or None."""
    try:
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _clear_state():
    """Remove the state file (on shutdown)."""
    try:
        os.remove(STATE_FILE)
    except OSError:
        pass


# ─── Main ─────────────────────────────────────────────────────────────────────

def _start_server():
    """Bind to an available port, load model in main thread, serve requests.

    The model MUST be loaded and used in the same thread — PyTorch on Windows
    CPU segfaults when model.encode() is called from a different thread than
    the one that loaded the model. We use a single-threaded server so both
    load and encode happen in the main thread.
    """
    # Redirect stdout/stderr to the log file ourselves (not via Popen).
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    log_fd = open(LOG_FILE, 'a')
    sys.stdout = log_fd
    sys.stderr = log_fd

    # Find an available port in the range
    server = None
    chosen_port = None
    for port in PORT_RANGE:
        try:
            server = EmbeddingTCPServer(("127.0.0.1", port), EmbeddingHandler)
            chosen_port = port
            break
        except OSError:
            continue

    if server is None:
        _log(f"FATAL: No available port in range {PORT_RANGE[0]}-{PORT_RANGE[-1]}")
        sys.exit(1)

    _log(f"Listening on 127.0.0.1:{chosen_port}")
    _write_state(chosen_port)

    # Start idle watchdog (daemon thread — OK, it only calls os._exit)
    threading.Thread(target=_idle_watchdog, daemon=True).start()

    # Load model in the MAIN thread (blocking, ~21s). The socket is already
    # open so clients can connect, but requests won't be handled until
    # serve_forever() starts. The client's retry loop handles this delay.
    _load_model()

    _log("Server ready. Waiting for requests...")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        _log("Shutdown via KeyboardInterrupt.")
    except Exception as e:
        _log(f"FATAL: serve_forever crashed: {e}")
        import traceback
        traceback.print_exc()
        sys.stdout.flush()
    finally:
        _clear_state()
        _log("Daemon exiting.")


def _stop_daemon():
    """Stop a running daemon by killing its PID."""
    state = _read_state()
    if state is None:
        print("No embedding server state file found. Daemon may not be running.")
        return
    pid = state.get("pid")
    port = state.get("port")
    if pid:
        try:
            os.kill(pid, 9)  # SIGKILL on Unix, TerminateProcess on Windows
            print(f"Killed daemon on port {port} (PID {pid}).")
        except (ProcessLookupError, OSError) as e:
            print(f"Could not kill PID {pid}: {e}")
    _clear_state()
    print("Daemon stopped.")


def _status():
    """Check if the daemon is running and responsive."""
    state = _read_state()
    if state is None:
        print("No state file found. Daemon not running.")
        return False
    port = state.get("port")
    pid = state.get("pid")
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=3) as s:
            s.sendall(b'{"method": "ping"}\n')
            data = b""
            while b"\n" not in data:
                chunk = s.recv(4096)
                if not chunk:
                    break
                data += chunk
            resp = json.loads(data.decode())
            if resp.get("pong"):
                print(f"Daemon running on port {port} (PID {pid}).")
                return True
    except (ConnectionRefusedError, socket.timeout, OSError):
        pass
    print(f"State file exists (port {port}, PID {pid}) but daemon is not responding.")
    return False


def main():
    args = sys.argv[1:]
    if "--stop" in args:
        _stop_daemon()
        return
    if "--status" in args:
        _status()
        return
    _start_server()


if __name__ == "__main__":
    main()
