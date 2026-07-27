#!/usr/bin/env python3
"""Regression test for the anchored save-trigger patterns (issue #1, bug 1)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from engram_user_prompt import extract_save_content


def test_no_false_positive_on_mid_sentence_mentions():
    assert extract_save_content("do you know about engram command") == (None, None)
    assert extract_save_content(
        "No, instead, create an issue in the engram github with all the details"
    ) == (None, None)
    assert extract_save_content("I want to remember this trip forever") == (None, None)


def test_legit_triggers_still_fire():
    assert extract_save_content("remember: buy milk")[0] == "buy milk"
    assert extract_save_content("engram: this is a note")[0] == "this is a note"
    assert extract_save_content("save: important thing")[0] == "important thing"


if __name__ == "__main__":
    test_no_false_positive_on_mid_sentence_mentions()
    test_legit_triggers_still_fire()
    print("OK")
