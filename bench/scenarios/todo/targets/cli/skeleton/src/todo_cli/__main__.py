import sys


def main(argv: list[str]) -> int:
    print("usage: todo <command>", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
