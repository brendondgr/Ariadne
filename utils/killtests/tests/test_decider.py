"""Live probe of the decider on :7500 (skipped when it is not running)."""
import pytest

from utils.killtests.decider import DeciderClient, keyed

ITEMS = [
    ("The sky is blue.", "What colour is the sky?", ["red", "blue", "green"], 1),
    ("Paris is the capital of France.", "Which city is the capital of France?", ["Berlin", "Paris", "Rome"], 1),
    ("APT29 is a Russian threat group also known as Cozy Bear.", "Which group is Cozy Bear?", ["APT28", "APT29", "Lazarus Group"], 1),
    ("Water freezes at 0 degrees Celsius.", "At what temperature does water freeze?", ["0 C", "50 C", "100 C"], 0),
    ("The meeting is on Tuesday.", "When is the meeting?", ["Monday", "Tuesday", "Friday"], 1),
    ("Phishing is sending deceptive messages to steal credentials.", "Which technique sends deceptive messages?", ["Phishing", "Rootkit", "Fuzzing"], 0),
    ("A cat has four legs.", "How many legs does a cat have?", ["two", "four", "six"], 1),
    ("SQL injection inserts SQL into queries.", "Which attack inserts SQL into queries?", ["XSS", "SQL Injection", "CSRF"], 1),
    ("The file was deleted.", "What happened to the file?", ["it was deleted", "it was renamed", "it was copied"], 0),
    ("Mimikatz dumps credentials from memory.", "What does Mimikatz do?", ["dumps credentials", "encrypts disks", "scans ports"], 0),
]


def _client():
    c = DeciderClient()
    try:
        c.health()
    except Exception:
        pytest.skip("decider on :7500 not reachable")
    return c


def test_obvious_items_pick_the_right_option():
    c = _client()
    right = 0
    for state, q, opts, gold in ITEMS * 2:  # 20 calls
        options, keys = keyed(opts, none_option="none of these")
        ch = c.choose(state, q, options)
        assert abs(sum(ch.probabilities.values()) - 1.0) < 1e-3
        right += ch.choice == keys[gold]
    assert right >= 19
