"""Manual: opens TextEdit and pastes a sentence at the cursor."""
import subprocess
import time

from murmur.output import paste_text


def main() -> None:
    subprocess.run(["open", "-a", "TextEdit"])
    print("Switch to TextEdit and place cursor. Pasting in 4 seconds...")
    time.sleep(4)
    paste_text("Hello from Murmur!")
    print("Done.")


if __name__ == "__main__":
    main()
