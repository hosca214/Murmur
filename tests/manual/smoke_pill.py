import time

from murmur.ui.pill import Pill


def main() -> None:
    p = Pill()
    for phase in ("Listening…", "Transcribing…", "Polishing…"):
        p.show(phase)
        time.sleep(2)
    p.hide()
    time.sleep(1)


if __name__ == "__main__":
    main()
