from __future__ import annotations

import sys
from typing import Union

Number = Union[int, float]


def add(a: Number, b: Number) -> float:
    return float(a + b)


def subtract(a: Number, b: Number) -> float:
    return float(a - b)


def multiply(a: Number, b: Number) -> float:
    return float(a * b)


def divide(a: Number, b: Number) -> float:
    return float(a / b)


def _parse_number(value: str) -> float:
    try:
        number = float(value)
    except ValueError as exc:
        raise ValueError(f"Invalid number: {value!r}") from exc

    if not number == number:
        raise ValueError(f"Invalid number: {value!r}")

    return number


def _print_usage() -> None:
    prog = sys.argv[0] if sys.argv else "calculator.py"
    sys.stderr.write(f"Usage: {prog} <add|subtract|multiply|divide> <a> <b>\n")


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    if len(argv) != 3:
        _print_usage()
        return 2

    op, a_str, b_str = argv

    try:
        a = _parse_number(a_str)
        b = _parse_number(b_str)

        if op == "add":
            result = add(a, b)
        elif op == "subtract":
            result = subtract(a, b)
        elif op == "multiply":
            result = multiply(a, b)
        elif op == "divide":
            result = divide(a, b)
        else:
            _print_usage()
            return 2

        sys.stdout.write(f"{result}\n")
        return 0
    except ZeroDivisionError as exc:
        sys.stderr.write(f"{exc}\n")
        return 1
    except ValueError as exc:
        sys.stderr.write(f"{exc}\n")
        return 2
    except Exception as exc:
        sys.stderr.write(f"{exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())