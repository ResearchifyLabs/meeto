import unittest

from meeto.meet.participant_scraper import ParticipantInfo, ParticipantScraper


class TestParticipantScraper(unittest.TestCase):
    def test_handle_update_adds_participants(self):
        scraper = ParticipantScraper.__new__(ParticipantScraper)
        scraper._participants = {}
        scraper._running = True

        import asyncio

        async def run():
            await scraper._handle_update(
                None,
                [
                    {
                        "participant_id": "pid1",
                        "display_name": "Alice",
                        "email": "alice@example.com",
                        "avatar_url": "https://img/alice",
                    }
                ],
            )

        asyncio.run(run())

        self.assertIn("pid1", scraper._participants)
        p = scraper._participants["pid1"]
        self.assertEqual(p.display_name, "Alice")
        self.assertEqual(p.email, "alice@example.com")
        self.assertEqual(p.avatar_url, "https://img/alice")

    def test_handle_update_merges_existing(self):
        scraper = ParticipantScraper.__new__(ParticipantScraper)
        scraper._participants = {
            "pid1": ParticipantInfo(
                participant_id="pid1",
                display_name="Alice",
                first_seen_at=1000.0,
                last_seen_at=1000.0,
            )
        }
        scraper._running = True

        import asyncio

        async def run():
            await scraper._handle_update(
                None,
                [{"participant_id": "pid1", "email": "alice@example.com"}],
            )

        asyncio.run(run())

        p = scraper._participants["pid1"]
        self.assertEqual(p.display_name, "Alice")
        self.assertEqual(p.email, "alice@example.com")

    def test_handle_update_skips_invalid(self):
        scraper = ParticipantScraper.__new__(ParticipantScraper)
        scraper._participants = {}
        scraper._running = True

        import asyncio

        async def run():
            await scraper._handle_update(None, None)
            await scraper._handle_update(None, "not a list")
            await scraper._handle_update(None, [{"no_pid": True}])
            await scraper._handle_update(None, [42])

        asyncio.run(run())

        self.assertEqual(len(scraper._participants), 0)

    def test_get_participants_returns_copy(self):
        scraper = ParticipantScraper.__new__(ParticipantScraper)
        scraper._participants = {"pid1": ParticipantInfo(participant_id="pid1", display_name="Alice")}
        result = scraper.get_participants()
        self.assertIn("pid1", result)
        result["pid2"] = "injected"
        self.assertNotIn("pid2", scraper._participants)

    def test_stop_sets_flag(self):
        scraper = ParticipantScraper.__new__(ParticipantScraper)
        scraper._running = True
        scraper.stop()
        self.assertFalse(scraper._running)
