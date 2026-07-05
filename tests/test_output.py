from unittest.mock import call

from murmur import output


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


def test_paste_schedules_clipboard_restore(mocker):
    mocker.patch("murmur.output.pyperclip.paste", return_value="user stuff")
    mocker.patch("murmur.output.pyperclip.copy")
    mocker.patch("murmur.output._post_cmd_key")
    mocker.patch("murmur.output.time.sleep")
    timer = mocker.patch("murmur.output.threading.Timer")
    output.paste_text("hello")
    timer.assert_called_once()
    args = timer.call_args
    assert args[0][1] is output._restore_clipboard
    assert args[1]["args"] == ("user stuff", "hello")


def test_no_restore_when_clipboard_was_empty(mocker):
    mocker.patch("murmur.output.pyperclip.paste", return_value="")
    mocker.patch("murmur.output.pyperclip.copy")
    mocker.patch("murmur.output._post_cmd_key")
    mocker.patch("murmur.output.time.sleep")
    timer = mocker.patch("murmur.output.threading.Timer")
    output.paste_text("hello")
    timer.assert_not_called()


def test_restore_only_when_clipboard_unchanged(mocker):
    paste = mocker.patch("murmur.output.pyperclip.paste", return_value="hello")
    copy = mocker.patch("murmur.output.pyperclip.copy")
    output._restore_clipboard("user stuff", "hello")
    copy.assert_called_once_with("user stuff")

    copy.reset_mock()
    paste.return_value = "something the user copied meanwhile"
    output._restore_clipboard("user stuff", "hello")
    copy.assert_not_called()
