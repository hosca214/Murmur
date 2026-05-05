from murmur.onboarding import OnboardingWindow


def main() -> None:
    w = OnboardingWindow(on_finish=lambda: print("onboarding done"))
    w.run()


if __name__ == "__main__":
    main()
