#!/usr/bin/env python3
"""Put the committed distDir spelling back into frontend/next-env.d.ts.

Next rewrites that tracked file to point at whatever `distDir` the last build
used. The e2e run builds into `.next-e2e` (so `make check` works while
`make dev` holds `.next`), which would otherwise leave the file dirty after
every test run — and a committed `.next-e2e` spelling would point CI's
typecheck, which runs before any build, at a folder that never exists there.
"""

from __future__ import annotations

from pathlib import Path

TARGET = Path(__file__).resolve().parents[1] / "frontend" / "next-env.d.ts"


def main() -> None:
    if not TARGET.exists():
        return
    text = TARGET.read_text(encoding="utf-8")
    restored = text.replace("./.next-e2e/dev/types", "./.next/dev/types")
    if restored != text:
        TARGET.write_text(restored, encoding="utf-8")
        print(f"✔ {TARGET.name} back to the committed .next spelling")


if __name__ == "__main__":
    main()
