MAX_LENGTH = 200


class TitleError(Exception):
    pass


def make(words: list[str]) -> str:
    title = " ".join(words).strip()
    if not title:
        raise TitleError("title is empty")
    if len(title) > MAX_LENGTH:
        raise TitleError(f"title is longer than {MAX_LENGTH} characters")
    return title
