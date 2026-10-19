"""Conservative display-only cleanup; never rewrite stored or confirmed answers."""
import re


_CUE = (
    r"(?:(?:(?:brief|short|long)\s+)?pause|"
    r"(?:woman|women|man|men|female|male)\s+(?:speaking|speaker|voice)|"
    r"speaker\s*\d+|laughter|laughing|breathing|sighs?|background\s+noise|music)"
)
_BRACKETED = (
    r"(?<![\w\"'`\[\{(])(?:\[\s*" + _CUE + r"\s*\]|\{\s*" + _CUE
    + r"\s*\}|\(\s*" + _CUE + r"\s*\))(?=$|[\s.,!?;:\[\{(])"
)
_TOKEN = r"(?:<\|speaker:\d+\|>|" + _BRACKETED + r")"
_ANNOTATIONS = re.compile(r"[ \t]*" + _TOKEN + r"(?:[ \t]*" + _TOKEN + r")*[ \t]*", re.IGNORECASE)
_CODE = re.compile(r"(```[\s\S]*?```|`[^`\n]*`)")


def clean_transcript(raw: str) -> str:
    """Hide recognised standalone audio cues, preserving code and unknown text.

    This is only a suggested review draft. The exact provider original remains
    available to the learner; their subsequent edits are never cleaned again.
    """
    def clean_segment(text):
        def remove(match):
            before = text[match.start() - 1] if match.start() else ""
            after = text[match.end()] if match.end() < len(text) else ""
            return " " if before and after and not before.isspace() and not after.isspace() and after not in ".,!?;:)]}" else ""
        return _ANNOTATIONS.sub(remove, text)

    return "".join(part if index % 2 else clean_segment(part)
        for index, part in enumerate(_CODE.split(raw))).strip()
