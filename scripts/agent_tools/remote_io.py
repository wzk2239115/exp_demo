#!/usr/bin/env python3
"""remote_io.py — 远程靶机交互封装,防"无输出反复发 PoC"。

封装:socket 连接+超时重试、输出缓冲、stderr 捕获、二进制安全传输、
输出通道验证(正常 vs 异常输入对比,确认 stdout/stderr 转不转发)。

用法(在容器内):
    from remote_io import RemoteTarget
    t = RemoteTarget("1.2.3.4", 8000)
    # 先验证输出通道(第一次连就做)
    t.verify_channel()
    # 发 PoC 拿输出
    resp = t.send(b"\\xff\\xff\\xff\\xff" + open("poc","rb").read(), timeout=5)
    # 大文件:分块 base64 或 HTTP 拉
    t.upload_b64(open("exploit","rb").read(), dest="/tmp/exploit")
"""
from __future__ import annotations
import base64, socket, sys, time, os

class RemoteTarget:
    def __init__(self, host: str, port: int, verbose: bool = True):
        self.host, self.port, self.verbose = host, port, verbose
        self.channel = {"stdout": None, "stderr": None}  # None=未知, True=转发, False=不转发

    def _log(self, *a):
        if self.verbose:
            print("[remote_io]", *a, file=sys.stderr, flush=True)

    def _connect(self, timeout: float = 10.0) -> socket.socket:
        s = socket.create_connection((self.host, self.port), timeout=timeout)
        s.settimeout(timeout)
        return s

    def verify_channel(self, timeout: float = 5.0) -> dict:
        """正常 vs 异常输入对比,确认输出通道。第一次连远程就做,别闷头发 PoC。

        发一个正常输入看 stdout 有无回显;再发一个会触发 stderr 的输入看 stderr 转不转发。
        退出码/文件副作用/时序差作为无回显时的判据。
        """
        results = {}
        # 正常输入:看 stdout
        try:
            s = self._connect(timeout)
            s.sendall(b"AAAA\n")
            time.sleep(0.5)
            try:
                data = s.recv(4096)
                self.channel["stdout"] = bool(data) and b"AAAA" not in data  # 回显≠banner
                results["stdout_echo"] = bool(data)
                results["stdout_sample"] = data[:80]
            except socket.timeout:
                self.channel["stdout"] = False
                results["stdout_echo"] = False
            s.close()
        except Exception as e:
            results["stdout_error"] = str(e)

        # 异常输入(触发崩溃/stderr)
        try:
            s = self._connect(timeout)
            s.sendall(b"\xff\xff\xff\xff\n")  # 非法 magic
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

        self._log("通道验证:", results)
        if not self.channel["stdout"]:
            self._log("stdout 不转发 → 别靠 stdout 调试,用退出码/文件副作用/时序差")
        if not self.channel["stderr"]:
            self._log("stderr 不转发 → 别靠 stderr,同上")
        return results

    def send(self, payload: bytes, timeout: float = 10.0, read_secs: float = 2.0) -> bytes:
        """发 payload,读 read_secs 秒输出。失败重试 3 次。"""
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
        """很多靶场协议:先发 8 字节 hex 长度,再发 poc。"""
        size_hex = f"{len(poc):08x}".encode()
        return self.send(size_hex + poc, timeout=timeout)

    def upload_b64(self, data: bytes, dest: str = "/tmp/upload",
                   chunk: int = 8000, timeout: float = 5.0) -> bool:
        """二进制安全传输:分块 base64,服务端拼回。绕大小限制。

        假设服务端能执行 shell(已 RCE 后期传文件,或协议允许命令注入)。
        无 RCE 时用 HTTP 拉取替代。
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
        """无回显时,用退出码判断(payload 后加 `; echo $?`)。"""
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
