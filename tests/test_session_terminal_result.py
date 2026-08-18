from iris.session_transport import _event_text


def test_structured_agent_result_is_rendered_for_slack():
    assert _event_text('{"type":"result","result":"finished safely"}') == "finished safely"
    assert _event_text('{"type":"assistant","message":{"content":[{"text":"progress"}]}}') == "progress"
