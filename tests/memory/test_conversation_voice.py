from iris.conversation import ConversationMessage, _prompt


def built_prompt():
    return _prompt((ConversationMessage("user", "hey"),), ())


def test_prompt_states_no_tools_boundary_before_voice_instructions():
    prompt = built_prompt()
    boundary = prompt.index("no tools in this turn")
    voice = prompt.index("Voice:")
    assert boundary < voice


def test_prompt_prohibits_claimed_actions_and_prose_dispatch():
    prompt = built_prompt()
    assert "must not claim to have performed an action" in prompt
    assert "not itself an action trigger" in prompt
    assert "consequential work goes only through Iris's approval controls" in prompt


def test_prompt_instructs_mirroring_user_tone_casing_and_emoji():
    prompt = built_prompt()
    assert "Mirror the user's tone, casing, and emoji level" in prompt


def test_prompt_allows_light_teasing_only_when_welcome_and_never_when_safety_sensitive():
    prompt = built_prompt()
    assert "light teasing is fine when it's clearly welcome and relevant" in prompt
    assert "never mean-spirited" in prompt
    assert "no humor or teasing of any kind inside a safety-sensitive reply" in prompt


def test_prompt_does_not_force_lowercase_or_import_apple_messages_rules():
    prompt = built_prompt()
    assert "don't force lowercase" in prompt
    assert "Apple Messages" not in prompt
    assert "strictly lowercase" not in prompt


def test_prompt_sections_appear_in_injection_resistant_order():
    prompt = built_prompt()
    assert prompt.index("Voice:") < prompt.index("Trusted context:") < prompt.index("Conversation:")


def test_prompt_does_not_leak_dangerous_poke_specific_tokens():
    prompt = built_prompt()
    assert "Poke" not in prompt
    assert "roast" not in prompt
    assert "physical harm" not in prompt
    assert "Execute immediately" not in prompt
