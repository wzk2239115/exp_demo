#!/usr/bin/env python3
"""remote_io.py — remote-target interaction wrapper; prevents "fire PoCs repeatedly with no output".

Wraps: socket connect + timeout/retry, output buffering, stderr capture,
binary-safe transfer, and output-channel verification (normal vs abnormal input
comparison to see whether stdout/stderr are forwarded).

Usage (inside the container):
    from remote_io import RemoteTarget
    t = RemoteTarget("1.2.3.4", 8000)
    # verify the output channel first (do it on the first connection)
    t.verify_channel()
    # send a PoC and get output
    resp = t.send(b"\\xff\\xff\\xff\\xff" + open("poc","rb").read(), timeout=5)
    # large files: chunked base64 or HTTP pull
    t.upload_b64(open("exploit","rb").read(), dest="/tmp/exploit")
"""
from __future__ import annotations
import base64, socket, sys, time, os

class RemoteTarget:
    def __init__(self, host: str, port: int, verbose: bool = True):
        self.host, self.port, self.verbose = host, port, verbose
        self.channel = {"stdout": None, "stderr": None}  # None=unknown, True=forwarded, False=not forwarded

    def _log(self, *a):
        if self.verbose:
            print("[remote_io]", *a, file=sys.stderr, flush=True)

    def _connect(self, timeout: float = 10.0) -> socket.socket:
        s = socket.create_connection((self.host, self.port), timeout=timeout)
        s.settimeout(timeout)
        return s

    def verify_channel(self, timeout: float = 5.0) -> dict:
        """Normal vs abnormal input comparison to confirm the output channel. Do this on
        the first remote connection; don't blindly fire PoCs.

        Send a normal input and see if stdout echoes; then send an input that triggers
        stderr and see whether stderr is forwarded. Use exit code / file side effects /
        timing differences as criteria when nothing is echoed.
        """
        results = {}
        # Normal input: watch stdout
        try:
            s = self._connect(timeout)
            s.sendall(b"AAAA\n")
            time.sleep(0.5)
            try:
                data = s.recv(4096)
                self.channel["stdout"] = bool(data) and b"AAAA" not in data  # echo != banner
                results["stdout_echo"] = bool(data)
                results["stdout_sample"] = data[:80]
            except socket.timeout:
                self.channel["stdout"] = False
                results["stdout_echo"] = False
            s.close()
        except Exception as e:
            results["stdout_error"] = str(e)

        # Abnormal input (trigger crash/stderr)
        try:
            s = self._connect(timeout)
            s.sendall(b"\xff\xff\xff\xff\n")  # illegal magic
            time.sleep(0.5)
            try:
                data = s.recv(4096)
                self.channel["stderr"] = bool(data)
                results["stderr_seen"] = bool(data)
                results["stderr_sample"] = data[:80]
            except socket.timeout:
                self.channel["stderr"] = False
                results["stderr_seen"] = False
            s.close()
        except Exception as e:
            results["stderr_error"] = str(e)

        self._log("channel verification:", results)
        if not self.channel["stdout"]:
            self._log("stdout not forwarded -> don't debug via stdout; use exit code / file side effects / timing")
        if not self.channel["stderr"]:
            self._log("stderr not forwarded -> don't rely on stderr; same as above")
        return results

    def send(self, payload: bytes, timeout: float = 10.0, read_secs: float = 2.0) -> bytes:
        """Send a payload, read output for read_secs seconds. Retries 3 times on failure."""
        last_err = None
        for attempt in range(3):
            try:
                s = self._connect(timeout)
                if payload:
                    s.sendall(payload)
                buf = b""
                end = time.time() + read_secs
                while time.time() < end:
                    try:
                        chunk = s.recv(4096)
                        if not chunk:
                            break
                        buf += chunk
                    except socket.timeout:
                        break
                s.close()
                self._log(f"send attempt {attempt+1}: {len(buf)} bytes back")
                return buf
            except Exception as e:
                last_err = e
                self._log(f"send attempt {attempt+1} fail: {e}")
                time.sleep(0.5 * (attempt + 1))
        raise ConnectionError(f"send failed after 3 tries: {last_err}")

    def send_with_size(self, poc: bytes, timeout: float = 10.0) -> bytes:
        """Many target protocols: send an 8-byte hex length first, then the poc."""
        size_hex = f"{len(poc):08x}".encode()
        return self.send(size_hex + poc, timeout=timeout)

    def upload_b64(self, data: bytes, dest: str = "/tmp/upload",
                   chunk: int = 8000, timeout: float = 5.0) -> bool:
        """Binary-safe transfer: chunked base64, reassembled server-side. Bypasses size limits.

        Assumes the server can run a shell (file transfer after RCE, or the protocol
        allows command injection). Without RCE, use an HTTP pull instead.
        """
        b64 = base64.b64encode(data).decode()
        self._log(f"upload {len(data)} bytes -> {dest} ({len(b64)} b64 chars, {chunk}/chunk)")
        for i in range(0, len(b64), chunk):
            c = b64[i:i+chunk]
            cmd = f"printf '{c}' >> {dest}.b64\n".encode()
            try:
                self.send(cmd, timeout=timeout, read_secs=0.5)
            except Exception as e:
                self._log(f"upload chunk {i} fail: {e}")
                return False
            time.sleep(0.1)
        self.send(f"base64 -d {dest}.b64 > {dest}; rm {dest}.b64\n".encode(),
                  timeout=timeout, read_secs=1.0)
        self._log(f"upload done -> {dest}")
        return True

    def probe_exit_code(self, payload: bytes, timeout: float = 5.0) -> int | None:
        """With no echo, use the exit code as the signal (append `; echo $?` to the payload)."""
        resp = self.send(payload + b"; echo EXITCODE:$?\n", timeout=timeout, read_secs=1.0)
        for line in resp.split(b"\n"):
            if b"EXITCODE:" in line:
                try:
                    return int(line.split(b"EXITCODE:")[1].strip()[:3])
                except (ValueError, IndexError):
                    pass
        return None

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(1)
    t = RemoteTarget(sys.argv[1], int(sys.argv[2]))
    t.verify_channel()
    if len(sys.argv) > 3 and os.path.isfile(sys.argv[3]):
        t.send_with_size(open(sys.argv[3], "rb").read())
