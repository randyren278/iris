"""Safe, bounded delivery through Messages' AppleScript interface."""
import subprocess
import time


# Handle and message are deliberately supplied as argv, never interpolated into
# this source. That keeps quotes, newlines, and AppleScript-looking text inert.
_SCRIPT = r'''
on run argv
    if (count of argv) is not 2 then error "expected handle and message"
    set targetHandle to item 1 of argv
    set msgText to item 2 of argv
    tell application "Messages"
        with timeout of 15 seconds
            set accountRef to 1st account whose service type = iMessage
            send msgText to participant targetHandle of accountRef
        end timeout
    end tell
end run
'''

_CHAT_SCRIPT = r'''
on run argv
    if (count of argv) is not 2 then error "expected message and chat guid"
    tell application "Messages" to send (item 1 of argv) to chat id (item 2 of argv)
end run
'''


def _send(command, *, attempts, retry_delay, runner, sleeper):
    """Run one argument-safe AppleScript command with bounded retries."""
    if attempts < 1:
        raise ValueError("attempts must be at least one")
    for attempt in range(attempts):
        try:
            result = runner(command, capture_output=True, text=True,
                            check=False)
            if result.returncode == 0:
                return True
        except OSError:
            pass
        if attempt + 1 < attempts:
            sleeper(retry_delay * (2 ** attempt))
    return False


def send(handle, text, *, attempts=3, retry_delay=0.5, runner=subprocess.run,
         sleeper=time.sleep):
    """Send one iMessage to a handle, retrying transient failures a bounded time.

    Returns ``True`` after Messages accepts the send and ``False`` after all
    attempts fail. Invalid values are rejected before launching a subprocess.
    ``runner`` and ``sleeper`` are injectable to keep unit tests off Messages.
    """
    if not isinstance(handle, str) or not handle:
        raise ValueError("handle must be a non-empty string")
    if not isinstance(text, str):
        raise ValueError("text must be a string")
    command = ["/usr/bin/osascript", "-e", _SCRIPT, handle, text]
    return _send(command, attempts=attempts, retry_delay=retry_delay,
                 runner=runner, sleeper=sleeper)


def send_to_chat(chat_guid, text, *, attempts=3, retry_delay=0.5,
                 runner=subprocess.run, sleeper=time.sleep):
    """Reply to an existing Messages chat by its stable database GUID."""
    if not isinstance(chat_guid, str) or not chat_guid:
        raise ValueError("chat_guid must be a non-empty string")
    if not isinstance(text, str):
        raise ValueError("text must be a string")
    command = ["/usr/bin/osascript", "-e", _CHAT_SCRIPT, text, chat_guid]
    return _send(command, attempts=attempts, retry_delay=retry_delay,
                 runner=runner, sleeper=sleeper)
