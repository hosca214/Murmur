from murmur.ui.bar import MenuBar


def main() -> None:
    app = MenuBar(
        on_mode_change=lambda m: print("mode:", m),
        on_pause_toggle=lambda: print("pause toggled"),
        on_privacy_toggle=lambda: print("privacy toggled"),
        on_open_settings=lambda: print("settings"),
        on_rerun_onboarding=lambda: print("rerun"),
        on_quit=lambda: app.quit_application(),
        on_diagnostics=lambda: "diagnostics-placeholder",
    )
    app.set_active_mode("email")
    app.run()


if __name__ == "__main__":
    main()
