from __future__ import annotations

from croqui_engine.generators.dependency_report_generator import generate_dependency_report


def main() -> None:
    path = generate_dependency_report()
    print(path)


if __name__ == "__main__":
    main()
