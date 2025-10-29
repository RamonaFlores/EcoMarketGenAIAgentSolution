# src/app_cli.py
from __future__ import annotations
import sys
from textwrap import indent
from typing import Any, Dict
from src.rag.chain import answer  # usa build y ejecuta la cadena RAG

BANNER = """\
EcoMarket RAG • CLI
Escribe tu pregunta y presiona Enter (Ctrl+C para salir).
"""

def _print_sources(res: Dict[str, Any]) -> None:
    srcs = res.get("source_documents", []) or []
    if not srcs:
        print("Fuentes: (no hubo documentos recuperados)")
        return
    print("Fuentes:")
    for d in srcs:
        meta = d.metadata or {}
        print(f" - {meta.get('doc_type')} | {meta.get('source')} | last_updated={meta.get('last_updated')}")

def main() -> None:
    print(BANNER)
    while True:
        try:
            q = input("> ")
            if not q.strip():
                continue
            res = answer(q, k=4)
            print("\nRespuesta:\n")
            print(indent(res["result"], prefix="  "))
            print()
            _print_sources(res)
            print()
        except (KeyboardInterrupt, EOFError):
            print("\nChao 👋")
            sys.exit(0)
        except Exception as e:
            print(f"\n⚠️  Error: {e}\n", file=sys.stderr)

if __name__ == "__main__":
    main()