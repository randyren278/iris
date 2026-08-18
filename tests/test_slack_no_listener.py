import inspect

from iris.slack import SocketModeEventSource


def test_socket_mode_source_does_not_create_a_network_listener():
    source = inspect.getsource(SocketModeEventSource)

    assert "HTTPServer" not in source
    assert "socket.bind" not in source
