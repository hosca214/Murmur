from murmur.frontmost import mode_for_bundle


def test_slack_maps_to_chat():
    assert mode_for_bundle("com.tinyspeck.slackmacgap", "email") == "chat"


def test_messages_maps_to_chat():
    assert mode_for_bundle("com.apple.MobileSMS", "email") == "chat"


def test_mail_maps_to_email():
    assert mode_for_bundle("com.apple.mail", "notes") == "email"


def test_outlook_maps_to_email():
    assert mode_for_bundle("com.microsoft.Outlook", "chat") == "email"


def test_notes_apps_map_to_notes():
    assert mode_for_bundle("com.apple.Notes", "email") == "notes"
    assert mode_for_bundle("md.obsidian", "email") == "notes"


def test_unknown_bundle_falls_back_to_default():
    assert mode_for_bundle("com.apple.Safari", "email") == "email"
    assert mode_for_bundle("com.apple.Safari", "chat") == "chat"


def test_empty_bundle_falls_back_to_default():
    assert mode_for_bundle("", "notes") == "notes"
    assert mode_for_bundle(None, "notes") == "notes"


def test_prefix_matching_catches_variants():
    assert mode_for_bundle("com.microsoft.teams2", "email") == "chat"
