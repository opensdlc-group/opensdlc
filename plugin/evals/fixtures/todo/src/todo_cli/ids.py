class IdError(Exception):
    pass


def parse(command: str, args: list[str]) -> int:
    if len(args) != 1:
        raise IdError(f"{command} takes exactly one id")
    text = args[0]
    if not (text and text.isascii() and text.isdigit()):
        raise IdError(f"id must be digits only: {text!r}")
    return int(text)
