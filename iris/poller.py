"""Watch chat.db for newly arrived messages.

Read-only throughout: the database belongs to Messages.app and Iris is a guest
in it. Every connection is opened with `mode=ro` so a bug here cannot corrupt
the operator's message history.

Two invariants make the poller safe to restart:

  * Only inbound rows (`is_from_me = 0`) are yielded. Iris's own replies land
    in the same table and would otherwise be read back as commands.
  * A high-water ROWID is persisted, so a restart resumes rather than
    replaying. On a *first* run with no saved state the mark is initialised to
    the current MAX(ROWID) -- otherwise Iris would wake up and execute a
    backlog of 650k historical messages as if they had just arrived.
"""
import json
import pathlib
import sqlite3
import time

from iris.chatdb import message_body


_ECHO_WINDOW_SECONDS = 120


def _normalise_account(value):
    """Turn chat.db's ``E:``/``P:`` account values into a handle."""
    if not isinstance(value, str):
        return None
    if len(value) > 2 and value[1] == ":":
        value = value[2:]
    return value.lower() or None


class Message:
    __slots__ = ("rowid", "guid", "handle", "body", "date", "chat_guid",
                 "chat_style", "is_from_me", "is_self_chat")

    def __init__(self, rowid, guid, handle, body, date, chat_guid, chat_style,
                 is_from_me, is_self_chat):
        self.rowid = rowid
        self.guid = guid
        self.handle = handle
        self.body = body
        self.date = date
        self.chat_guid = chat_guid
        self.chat_style = chat_style
        self.is_from_me = bool(is_from_me)
        self.is_self_chat = is_self_chat

    def __repr__(self):
        body_len = len(self.body) if isinstance(self.body, str) else None
        return f"Message(rowid={self.rowid}, handle={self.handle!r}, body_len={body_len})"


class Poller:
    def __init__(self, chatdb, state_path, interval=2.0, self_chat_guid=None,
                 self_command_suffix=" - Iris"):
        self.chatdb = pathlib.Path(chatdb)
        self.state_path = pathlib.Path(state_path)
        self.interval = interval
        self.self_chat_guid = self_chat_guid
        self.self_command_suffix = self_command_suffix
        self._high_water = self._load_high_water()
        self._self_handles = self._load_self_handles()
        self._echoes = {}

    def _connect(self):
        return sqlite3.connect(f"file:{self.chatdb}?mode=ro", uri=True)

    def _load_high_water(self):
        try:
            return int(json.loads(self.state_path.read_text())["high_water"])
        except (FileNotFoundError, KeyError, ValueError):
            return None

    def _load_self_handles(self):
        """Discover the local Apple-account addresses from sent messages."""
        try:
            conn = self._connect()
            try:
                return self._self_handles_from_connection(conn)
            finally:
                conn.close()
        except sqlite3.Error:
            return frozenset()

    @staticmethod
    def _self_handles_from_connection(conn):
        rows = conn.execute(
            "select distinct account from message where account is not null "
            "and account != ''").fetchall()
        return frozenset(handle for (account,) in rows
                         if (handle := _normalise_account(account)))

    def track_echo(self, chat_guid, text):
        """Record a successful send so its inbound self-chat copy is ignored.

        Sends are queued per (chat_guid, text) rather than overwritten, so
        sending the same text twice in a row still suppresses both echoes.
        """
        if chat_guid and isinstance(text, str):
            now = time.monotonic()
            self._echoes.setdefault((chat_guid, text), []).append(now)
            for key, timestamps in tuple(self._echoes.items()):
                fresh = [t for t in timestamps if now - t <= _ECHO_WINDOW_SECONDS]
                if fresh:
                    self._echoes[key] = fresh
                else:
                    del self._echoes[key]

    def _consume_echo(self, chat_guid, text):
        key = (chat_guid, text)
        timestamps = self._echoes.get(key)
        if not timestamps or time.monotonic() - timestamps[0] > _ECHO_WINDOW_SECONDS:
            return False
        timestamps.pop(0)
        if not timestamps:
            del self._echoes[key]
        return True

    def _save_high_water(self, rowid):
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"high_water": rowid}))
        tmp.replace(self.state_path)  # atomic; a crash cannot truncate state
        self._high_water = rowid

    def _current_max_rowid(self, conn):
        row = conn.execute("select max(ROWID) from message").fetchone()
        return row[0] or 0

    def poll_once(self):
        """Return inbound messages that arrived since the last call."""
        conn = self._connect()
        try:
            if self._high_water is None:
                # First ever run: start at the tip, do not replay history.
                self._save_high_water(self._current_max_rowid(conn))
                return []

            rows = conn.execute(
                "select m.ROWID, m.guid, h.id, m.text, m.attributedBody, m.date, "
                "m.is_from_me, c.guid, c.style "
                "from message m "
                "join chat_message_join cmj on cmj.message_id = m.ROWID "
                "join chat c on c.ROWID = cmj.chat_id "
                "left join handle h on h.ROWID = m.handle_id "
                "where m.ROWID > ? order by m.ROWID",
                (self._high_water,)).fetchall()
            self._self_handles |= self._self_handles_from_connection(conn)

            # Advance past every row examined, including outbound and
            # undecodable ones -- otherwise they are re-examined forever.
            top = self._current_max_rowid(conn)
        finally:
            conn.close()

        messages = []
        for rowid, guid, handle, text, abody, date, is_from_me, chat_guid, chat_style in rows:
            body = message_body(text, abody)
            if body is None:
                continue  # undecodable (attachment-only, unknown layout)
            is_self_chat = (
                chat_style == 45
                and chat_guid == self.self_chat_guid
                and _normalise_account(handle) in self._self_handles
            )
            if is_from_me:
                # Some macOS/iMessage combinations keep a self-chat message
                # only as an outbound row. The terminal marker provides an
                # explicit, loop-free command envelope for that case.
                if not is_self_chat or not body.endswith(self.self_command_suffix):
                    continue
                body = body[:-len(self.self_command_suffix)].rstrip()
                if not body:
                    continue
            if is_self_chat and self._consume_echo(chat_guid, body):
                continue
            messages.append(Message(rowid, guid, handle, body, date, chat_guid,
                                    chat_style, is_from_me, is_self_chat))

        if top > self._high_water:
            self._save_high_water(top)
        return messages

    def run(self, handler, stop=None):
        """Poll forever, passing each new message to `handler`."""
        while not (stop and stop()):
            for message in self.poll_once():
                handler(message)
            time.sleep(self.interval)
