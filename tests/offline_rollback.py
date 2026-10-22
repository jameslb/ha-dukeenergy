"""Test the prepared rollback's original startup ordering without services."""

import unittest

import offline_startup as offline


class RollbackBoot(unittest.IsolatedAsyncioTestCase):
    """Rollback restores first-refresh gating before Core readiness."""

    setUp = offline.Startup.setUp

    async def test_boot_uses_original_first_refresh_order(self) -> None:
        """Offline rollback restores actual first refresh before sensors at boot."""
        self.hass.is_running = False
        assert await offline.INTEGRATION.async_setup_entry(self.hass, self.entry)
        assert self.events == ["auth", "ledger", "refresh", "sensors"]


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for cls in [offline.Dependency, offline.Manifest, offline.Statistics, RollbackBoot]:
        suite.addTests(loader.loadTestsFromTestCase(cls))
    for name in loader.getTestCaseNames(offline.Startup):
        if name not in [
            "test_boot_defers_before_auth_or_statistics",
            "test_retry_after_running_uses_unchanged_setup",
        ]:
            suite.addTest(offline.Startup(name))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not result.wasSuccessful())
