"""The instructions the language model is given, editable from Settings.

Every prompt has two parts. The instructions (how to judge, what to leave out, how to write) can be changed by the
user. The output format is fixed and always appended by the code, because the code has to read the reply: a user's
edit can change what the model does, never whether the reply can be parsed.
"""
from dataclasses import dataclass
from datetime import datetime, timezone

from .db import connect

MAX_CHARS = 20_000


@dataclass(frozen=True)
class Prompt:
    id: str
    title: str
    description: str
    used_when: str
    default: str  # the whole built-in prompt: instructions, then the output format
    marker: str  # where the output format starts inside `default`

    @property
    def default_instructions(self) -> str:
        return self.default.partition(self.marker)[0].rstrip()

    @property
    def output_format(self) -> str:
        head, sep, tail = self.default.partition(self.marker)
        return (sep + tail).strip()

    @property
    def joiner(self) -> str:
        """The whitespace between the instructions and the format in the built-in prompt, kept so an untouched prompt is sent exactly as written."""
        head = self.default.partition(self.marker)[0]
        return head[len(head.rstrip()):]


_REGISTRY: dict[str, Prompt] = {}


def register(prompt: Prompt) -> Prompt:
    """Called by the module that owns a prompt, so the text lives next to the code that depends on its format."""
    if prompt.marker not in prompt.default:
        raise ValueError(f"prompt {prompt.id}: the output-format marker is not in the text")
    _REGISTRY[prompt.id] = prompt
    return prompt


def all_prompts() -> list[Prompt]:
    return list(_REGISTRY.values())


def get(prompt_id: str) -> Prompt:
    try:
        return _REGISTRY[prompt_id]
    except KeyError:
        raise KeyError(f"unknown prompt '{prompt_id}'") from None


def _saved(prompt_id: str) -> str | None:
    with connect() as conn:
        row = conn.execute("SELECT value FROM app_settings WHERE name = ?", (f"prompt:{prompt_id}",)).fetchone()
    return row[0] if row else None


def instructions(prompt_id: str) -> tuple[str, bool]:
    """The instructions in use, and whether the user changed them."""
    saved = _saved(prompt_id)
    return (saved, True) if saved is not None else (get(prompt_id).default_instructions, False)


def system(prompt_id: str) -> str:
    """The full prompt sent to the model: the user's (or built-in) instructions, then the fixed output format."""
    text, _ = instructions(prompt_id)
    prompt = get(prompt_id)
    return f"{text.rstrip()}{prompt.joiner}{prompt.output_format}"


def save(prompt_id: str, text: str) -> None:
    get(prompt_id)
    text = text.strip()
    if not text:
        raise ValueError("The instructions can't be empty. Use Reset to default to go back to the built-in ones.")
    if len(text) > MAX_CHARS:
        raise ValueError(f"The instructions are too long ({len(text):,} characters). The limit is {MAX_CHARS:,}.")
    if text == get(prompt_id).default_instructions:  # nothing changed from the built-in text: don't keep a copy that would hide later improvements
        return reset(prompt_id)
    with connect() as conn:
        conn.execute("INSERT OR REPLACE INTO app_settings (name, value, updated_at) VALUES (?, ?, ?)",
                     (f"prompt:{prompt_id}", text, datetime.now(timezone.utc).isoformat()))


def reset(prompt_id: str) -> None:
    get(prompt_id)
    with connect() as conn:
        conn.execute("DELETE FROM app_settings WHERE name = ?", (f"prompt:{prompt_id}",))
