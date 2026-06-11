#!/usr/bin/env python3
"""UserPromptSubmit / BeforeAgent hook: auto-saves when user says 'remember this' etc.

Regex check is instant — the embedding model only loads when a trigger is matched,
so normal messages have zero overhead.

Compatible with: Claude Code (UserPromptSubmit), Antigravity CLI (BeforeAgent),
Cursor (beforeSubmitPrompt).
"""

import json
import re
import sys
from pathlib import Path

ENGRAM_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ENGRAM_DIR))

# Patterns that trigger an auto-save. Capture group 1 = content to save.
PATTERNS = [
    r"^remember[:\s]+(.+)",
    r"^note[:\s]+(.+)",
    r"^save[:\s]+(.+)",
    r"remember this[:\s]+(.+)",
    r"remember this$",               # "remember this" alone → save the previous context
    r"note (?:that|this)[:\s]+(.+)",
    r"save this[:\s]+(.+)",
    r"add to (?:my )?(?:brain|engram|notes|knowledge)[:\s]+(.+)",
    r"engram[:\s]+(.+)",             # "engram: ..." direct capture
]

CONTINUE = json.dumps({"continue": True})


def extract_save_content(prompt: str):
    """Return (content, tags) to save, or (None, None) if no trigger found."""
    text = prompt.strip()
    for pattern in PATTERNS:
        m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if m:
            try:
                content = m.group(1).strip()
            except IndexError:
                content = text  # pattern had no capture group
            if content:
                return content, None
    return None, None


def main():
    try:
        raw = sys.stdin.read()
        hook_input = json.loads(raw) if raw.strip() else {}
    except Exception:
        hook_input = {}

    # Different tools expose the prompt under different keys
    prompt = (
        hook_input.get("prompt")
        or hook_input.get("user_prompt")
        or hook_input.get("message")
        or ""
    )

    content, tags = extract_save_content(prompt)
    if not content:
        print(CONTINUE)
        return

    try:
        import yaml
        with open(ENGRAM_DIR / "config.yaml") as f:
            config = yaml.safe_load(f)

        db_path = ENGRAM_DIR / config["database"]["path"]

        from engram_db import EngramDatabase
        from engram_embeddings import EmbeddingGenerator

        backend = config["embeddings"].get("backend", "sentence-transformers")
        dim_key = "ollama_dimensions" if backend == "ollama" else "dimensions"
        dim = config["embeddings"].get(dim_key, 384)

        db = EngramDatabase(str(db_path), embedding_dim=dim)
        db.init_database()

        embedder = EmbeddingGenerator(config["embeddings"])
        embedding = embedder.generate_embedding(content)
        thought_id = db.insert_thought(content, embedding, tags=tags)
        db.close()

        notice = f"[Engram] Saved to knowledge base (ID: {thought_id}): \"{content[:80]}{'…' if len(content) > 80 else ''}\""
        print(json.dumps({
            "continue": True,
            "additionalContext": notice,
            "additional_context": notice,
        }))

    except Exception as e:
        print(json.dumps({"_engram_error": str(e)}), file=sys.stderr)
        print(CONTINUE)


if __name__ == "__main__":
    main()
