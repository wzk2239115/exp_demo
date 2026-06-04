from collections.abc import Callable, Iterable, Iterator
from typing import TextIO


def iter_stream_lines(
    inp: Iterable[str | bytes] | TextIO,
    *,
    on_chunk: Callable[[str], None] | None = None,
) -> Iterator[str]:
    pending = ""
    for chunk in inp:
        decoded_chunk = (
            chunk.decode(errors="replace") if isinstance(chunk, bytes) else chunk
        )
        if on_chunk is not None:
            on_chunk(decoded_chunk)
        pending += decoded_chunk
        while "\n" in pending:
            line, pending = pending.split("\n", 1)
            yield line
    if pending:
        yield pending
