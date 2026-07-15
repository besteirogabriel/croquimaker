from __future__ import annotations

from croqui_engine.jobs.worker import run_once


def main() -> None:
    task = run_once()
    print(task or "Fila local vazia.")


if __name__ == "__main__":
    main()
