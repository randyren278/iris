from types import SimpleNamespace

import pytest

from iris.sender import _CHAT_SCRIPT, _SCRIPT, _send, send, send_to_chat


def result(code):
    return SimpleNamespace(returncode=code)


def test_low_level_sender_succeeds_first_try_without_sleep():
    calls, sleeps = [], []
    assert _send(["cmd"], attempts=3, retry_delay=0.5,
                 runner=lambda command, **kwargs: calls.append((command, kwargs)) or result(0),
                 sleeper=sleeps.append) is True
    assert len(calls) == 1
    assert calls[0][1] == {"capture_output": True, "text": True, "check": False}
    assert sleeps == []


def test_low_level_sender_retries_failures_with_exponential_backoff():
    codes = iter((1, 2, 0))
    sleeps = []
    assert _send(["cmd"], attempts=3, retry_delay=0.25,
                 runner=lambda *_args, **_kwargs: result(next(codes)), sleeper=sleeps.append) is True
    assert sleeps == [0.25, 0.5]


def test_low_level_sender_treats_oserror_as_retryable_and_returns_false_after_bound():
    attempts, sleeps = [], []

    def fail(*_args, **_kwargs):
        attempts.append("try")
        raise OSError("osascript unavailable")

    assert _send(["cmd"], attempts=3, retry_delay=1, runner=fail, sleeper=sleeps.append) is False
    assert attempts == ["try", "try", "try"]
    assert sleeps == [1, 2]


def test_low_level_sender_requires_at_least_one_attempt():
    with pytest.raises(ValueError, match="attempts must be at least one"):
        _send(["cmd"], attempts=0, retry_delay=1, runner=lambda *_a, **_k: result(0), sleeper=lambda _x: None)


def test_handle_sender_keeps_user_values_in_argv_not_script_source():
    captured = []
    handle = 'dangerous " handle'
    text = 'tell application "Finder"\nrm -rf /'
    assert send(handle, text, attempts=1,
                runner=lambda command, **_kwargs: captured.append(command) or result(0),
                sleeper=lambda _x: None) is True
    command = captured[0]
    assert command[:3] == ["/usr/bin/osascript", "-e", _SCRIPT]
    assert command[-2:] == [handle, text]
    assert handle not in _SCRIPT
    assert text not in _SCRIPT


def test_chat_sender_orders_message_and_stable_guid_as_argv():
    captured = []
    assert send_to_chat("iMessage;-;chat", "hello", attempts=1,
                        runner=lambda command, **_kwargs: captured.append(command) or result(0),
                        sleeper=lambda _x: None) is True
    assert captured[0] == ["/usr/bin/osascript", "-e", _CHAT_SCRIPT, "hello", "iMessage;-;chat"]


@pytest.mark.parametrize("handle", ["", None, 3, True])
def test_handle_sender_rejects_invalid_handle(handle):
    with pytest.raises(ValueError, match="handle must be a non-empty string"):
        send(handle, "text")


@pytest.mark.parametrize("chat_guid", ["", None, 3, True])
def test_chat_sender_rejects_invalid_guid(chat_guid):
    with pytest.raises(ValueError, match="chat_guid must be a non-empty string"):
        send_to_chat(chat_guid, "text")


@pytest.mark.parametrize("text", [None, 3, True])
def test_senders_reject_nontext_message(text):
    with pytest.raises(ValueError, match="text must be a string"):
        send("handle", text)
    with pytest.raises(ValueError, match="text must be a string"):
        send_to_chat("guid", text)


def test_empty_message_is_allowed_because_transport_can_represent_it():
    calls = []
    assert send("handle", "", attempts=1,
                runner=lambda command, **_kwargs: calls.append(command) or result(0),
                sleeper=lambda _x: None) is True
    assert calls[0][-1] == ""
