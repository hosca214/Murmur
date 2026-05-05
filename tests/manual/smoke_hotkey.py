"""Manual: prove tap vs hold detection."""
import time

from murmur.hotkey import HotkeyListener


def main() -> None:
    print("Press Right Option briefly = tap. Hold > 250ms = hold. Ctrl+C to quit.")
    listener = HotkeyListener(
        key_name="right_option",
        tap_threshold_ms=250,
        on_tap=lambda: print(">> TAP"),
        on_hold_start=lambda: print(">> HOLD start"),
        on_hold_end=lambda: print(">> HOLD end"),
    )
    listener.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        listener.stop()


if __name__ == "__main__":
    main()
