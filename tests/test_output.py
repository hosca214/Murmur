import pytest

from murmur import output


@pytest.fixture(autouse=True)
def reset_pending_restore():
    with output._restore_lock:
        output._pending_previous = None
        output._pending_timer = None
    yield
    with output._restore_lock:
        if output._pending_timer is not None:
            output._pending_timer.cancel()
        output._pending_previous = None
        output._pending_timer = None


def test_paste_empty_text_is_noop(mocker):
    copy = mocker.patch("murmur.output.pyperclip.copy")
    post = mocker.patch("murmur.output._post_cmd_key")
    output.paste_text("")
    copy.assert_not_called()
    post.assert_not_called()


def test_paste_copies_then_pastes(mocker):
    mocker.patch("murmur.output.pyperclip.paste", return_value="")
    copy = mocker.patch("murmur.output.pyperclip.copy")
    post = mocker.patch("murmur.output._post_cmd_key")
    mocker.patch("murmur.output.time.sleep")
    output.paste_text("hello")
    copy.assert_called_once_with("hello")
    post.assert_called_once_with(output._KEY_V)


def test_paste_schedules_clipboard_restore_after_10s(mocker):
    mocker.patch("murmur.output.pyperclip.paste", return_value="user stuff")
    mocker.patch("murmur.output.pyperclip.copy")
    mocker.patch("murmur.output._post_cmd_key")
    mocker.patch("murmur.output.time.sleep")
    timer = mocker.patch("murmur.output.threading.Timer")
    output.paste_text("hello")
    timer.assert_called_once()
    args = timer.call_args
    # The delay is load-bearing: it is the manual-paste safety window
    assert args[0][0] == output._CLIPBOARD_RESTORE_DELAY_S
    assert output._CLIPBOARD_RESTORE_DELAY_S == 10.0
    assert args[0][1] is output._restore_clipboard_cb
    assert args[1]["args"] == ("user stuff", "hello")


def test_no_restore_when_clipboard_was_empty(mocker):
    mocker.patch("murmur.output.pyperclip.paste", return_value="")
    mocker.patch("murmur.output.pyperclip.copy")
    mocker.patch("murmur.output._post_cmd_key")
    mocker.patch("murmur.output.time.sleep")
    timer = mocker.patch("murmur.output.threading.Timer")
    output.paste_text("hello")
    timer.assert_not_called()


def test_chained_pastes_keep_users_original_clipboard(mocker):
    # Copy "ACCT-1234", dictate A, then dictate B inside the restore window:
    # the pending restore must hand ACCT-1234 forward, not dictation A.
    paste = mocker.patch("murmur.output.pyperclip.paste", return_value="ACCT-1234")
    mocker.patch("murmur.output.pyperclip.copy")
    mocker.patch("murmur.output._post_cmd_key")
    mocker.patch("murmur.output.time.sleep")
    timer = mocker.patch("murmur.output.threading.Timer")
    output.paste_text("dictation A")
    first_timer = timer.return_value
    paste.return_value = "dictation A"  # clipboard now holds our own paste
    output.paste_text("dictation B")
    first_timer.cancel.assert_called_once()
    assert timer.call_args[1]["args"] == ("ACCT-1234", "dictation B")


def test_restore_only_when_clipboard_unchanged(mocker):
    paste = mocker.patch("murmur.output.pyperclip.paste", return_value="hello")
    copy = mocker.patch("murmur.output.pyperclip.copy")
    output._restore_clipboard_cb("user stuff", "hello")
    copy.assert_called_once_with("user stuff")

    copy.reset_mock()
    paste.return_value = "something the user copied meanwhile"
    output._restore_clipboard_cb("user stuff", "hello")
    copy.assert_not_called()
