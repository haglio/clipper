def test_the_suite_renders_offscreen(qapp):
    """Agents run this suite on every commit, on the machine clipper is used
    from; it must render offscreen so no window flashes onto that screen.
    Guards conftest's QT_QPA_PLATFORM setting against being removed or set too
    late -- after the QApplication is built, it does nothing."""
    assert qapp.platformName() == "offscreen"
