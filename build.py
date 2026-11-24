"""Pack src/engine.py into a tiny self-extracting main.py.

The entry file is a latin-1 Python source whose single executable line
decompresses an embedded LZMA stream (via the stdlib ``lzma`` module) and
``exec``s it.  Because the host file is decoded as latin-1, the compressed
bytes can live directly inside a string literal as long as the few characters
that are special to the tokenizer (newline, carriage return, backslash, quote,
and a NUL that could be confused with an octal escape) are escaped.  Every
other byte -- including high bytes and stray control codes -- is stored raw,
which keeps the literal short.  Several LZMA tuning knobs are tried and the
smallest stream that still round-trips is kept.
"""
import lzma
import sys

SOURCE = "src/engine.py"
OUTPUT = "main.py"
BUDGET = 4096
HEADER = "#coding:l1\n"
SHELL_HEAD = "import lzma;exec(lzma.decompress('"
SHELL_TAIL = "'.encode('l1')))"


def tunings(source_bytes):
    """Yield (blob) candidates across a grid of LZMA parameters."""
    dict_sizes = (4096, 8192, 12288, 16384, 32768, 65536)
    nice_lengths = (273, 128, 96, 64, 32, 16)
    matchers = (lzma.MF_BT4, lzma.MF_BT3, lzma.MF_BT2, lzma.MF_HC4, lzma.MF_HC3)
    for dict_size in dict_sizes:
        for lc in range(0, 5):
            for lp in range(0, 5):
                if lc + lp > 4:
                    continue
                for pb in (0, 1, 2):
                    for nice in nice_lengths:
                        for matcher in matchers:
                            spec = [{
                                "id": lzma.FILTER_LZMA1,
                                "dict_size": dict_size,
                                "lc": lc,
                                "lp": lp,
                                "pb": pb,
                                "mode": lzma.MODE_NORMAL,
                                "nice_len": nice,
                                "mf": matcher,
                            }]
                            try:
                                yield lzma.compress(
                                    source_bytes,
                                    format=lzma.FORMAT_ALONE,
                                    filters=spec,
                                )
                            except lzma.LZMAError:
                                continue


def escape_for_literal(blob):
    """Return the body of a latin-1 string literal that evaluates to *blob*.

    Only tokenizer-significant bytes are escaped; everything else (control
    characters, high bytes) is emitted raw so the result stays compact.
    """
    body = bytearray()
    n = len(blob)
    for i, byte in enumerate(blob):
        if byte == 0x5C:
            body += b"\\\\"
        elif byte == 0x27:
            body += b"\\'"
        elif byte == 0x0A:
            body += b"\\n"
        elif byte == 0x0D:
            body += b"\\r"
        elif byte == 0x00:
            # a bare \0 would swallow a following octal digit
            if i + 1 < n and 0x30 <= blob[i + 1] <= 0x37:
                body += b"\\x00"
            else:
                body += b"\\0"
        else:
            body.append(byte)
    return bytes(body)


def render(blob):
    literal = escape_for_literal(blob)
    packed = HEADER.encode() + SHELL_HEAD.encode() + literal + SHELL_TAIL.encode() + b"\n"
    return packed


def main():
    with open(SOURCE, "rb") as handle:
        source_bytes = handle.read()

    best = None
    for blob in tunings(source_bytes):
        if best is None or len(blob) < len(best):
            best = blob

    if best is None:
        raise SystemExit("no viable LZMA stream produced")

    packed = render(best)

    recovered = lzma.decompress(best, format=lzma.FORMAT_ALONE)
    assert recovered == source_bytes, "packed stream does not reproduce the source"
    compile(packed.decode("latin-1"), OUTPUT, "exec")

    with open(OUTPUT, "wb") as handle:
        handle.write(packed)

    print(f"{OUTPUT}: {len(packed)} bytes (budget {BUDGET})")
    if len(packed) > BUDGET:
        print("OVER BUDGET", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
