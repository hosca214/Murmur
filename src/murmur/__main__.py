from murmur import paths, settings as settings_mod
from murmur.app import MurmurApp


def _is_first_run() -> bool:
    return not paths.config_path().exists() or not paths.env_path().exists()


def main() -> None:
    if _is_first_run():
        settings_mod.save(settings_mod.load())
        from murmur.onboarding import OnboardingWindow
        OnboardingWindow(on_finish=lambda: None).run()
    MurmurApp().run()


if __name__ == "__main__":
    main()
