"""Who is allowed to drive the gateway.

This is the whole security boundary of P3: an allowed handle can start agent
sessions on the operator's machine. Two rules follow from that.

**Exact match only.** No prefix, suffix, substring or normalisation. A handle
is a string from `handle.id` and must equal an allowlisted string byte for
byte. Anything looser lets `+15551234567-attacker@evil.com` match.

**Mutation is terminal-only.** Nothing reachable from an inbound message may
add an entry. The allowlist is immutable once constructed, so there is no
method for a message handler to call even if one were compromised.
"""


class Allowlist:
    def __init__(self, handles=()):
        # frozenset, so there is no add()/remove() to reach for from a
        # message-handling path (P3.3: mutation is terminal-only).
        self._handles = frozenset(handles)

    def __contains__(self, handle):
        return self.allows(handle)

    def __iter__(self):
        return iter(self._handles)

    def __len__(self):
        return len(self._handles)

    def allows(self, handle):
        """True only if `handle` exactly equals an allowlisted string."""
        if not isinstance(handle, str):
            return False
        return handle in self._handles

    @classmethod
    def from_config(cls, config):
        return cls(config.allowlist)
