"""Shared diagnostics state for the LLM proxy.

``_diag_loop_ref`` is populated at app startup (server.py's startup hook)
with the running event loop, so the stack-dump watcher thread in
``__main__.py`` can enumerate asyncio tasks even when the loop is frozen.
"""

_diag_loop_ref: dict = {"loop": None}
