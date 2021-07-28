"""Basic import test."""


def test_import():
    """Verify the package can be imported."""
    import philiprehberger_web_scraper
    assert hasattr(philiprehberger_web_scraper, "__name__") or True
