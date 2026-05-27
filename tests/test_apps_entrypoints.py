from notes_recovery.apps import dashboard


def test_dashboard_entrypoints_present() -> None:
    assert callable(dashboard.main)
    assert callable(dashboard.run_dashboard)
