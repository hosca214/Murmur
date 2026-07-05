"""Detect the frontmost app and pick a cleanup mode to match its tone,
the way Wispr Flow adapts style per app (casual in Slack, formal in Mail)."""
import logging

logger = logging.getLogger(__name__)

# Bundle-id prefixes → cleanup mode. Checked with str.startswith so
# variants (beta builds, Setapp editions) still match.
BUNDLE_MODE_PREFIXES: tuple[tuple[str, str], ...] = (
    # Chat apps → casual
    ("com.tinyspeck.slackmacgap", "chat"),
    ("com.apple.mobilesms", "chat"),
    ("com.apple.imessage", "chat"),
    ("com.hnc.discord", "chat"),
    ("net.whatsapp.whatsapp", "chat"),
    ("ru.keepcoder.telegram", "chat"),
    ("org.telegram", "chat"),
    ("com.facebook.archon", "chat"),          # Messenger
    ("com.microsoft.teams", "chat"),
    ("us.zoom.xos", "chat"),
    ("com.signal", "chat"),
    ("org.whispersystems.signal", "chat"),
    # Email clients → formal
    ("com.apple.mail", "email"),
    ("com.microsoft.outlook", "email"),
    ("com.readdle.smartemail", "email"),      # Spark
    ("it.bloop.airmail", "email"),
    ("com.superhuman", "email"),
    ("com.mimestream", "email"),
    # Notes / writing apps → structured notes
    ("com.apple.notes", "notes"),
    ("md.obsidian", "notes"),
    ("notion.id", "notes"),
    ("com.notion", "notes"),
    ("net.shinyfrog.bear", "notes"),
    ("com.evernote", "notes"),
    ("com.agiletortoise.drafts", "notes"),
)


def mode_for_bundle(bundle_id: str, default: str) -> str:
    bid = (bundle_id or "").lower()
    if not bid:
        return default
    for prefix, mode in BUNDLE_MODE_PREFIXES:
        if bid.startswith(prefix):
            return mode
    return default


def detect_mode(default: str) -> str:
    """Return the cleanup mode matching the frontmost app, or `default`."""
    try:
        from AppKit import NSWorkspace

        app = NSWorkspace.sharedWorkspace().frontmostApplication()
        bundle_id = str(app.bundleIdentifier() or "") if app else ""
    except Exception:
        logger.debug("Frontmost app detection failed", exc_info=True)
        return default
    mode = mode_for_bundle(bundle_id, default)
    if mode != default:
        logger.info("Auto mode: %s → %s", bundle_id, mode)
    return mode
