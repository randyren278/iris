"""Recording stub that replaces the AppleScript sender in tests."""


class FakeSender:
    """Drop-in for Config.sender. Records instead of sending."""

    def __init__(self):
        self.sent = []

    def __call__(self, handle, text):
        self.sent.append((handle, text))
        return True

    @property
    def texts(self):
        return [t for _, t in self.sent]

    def last(self):
        return self.sent[-1] if self.sent else None
