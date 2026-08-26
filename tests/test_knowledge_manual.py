from django.test import SimpleTestCase


class KnowledgeManualTests(SimpleTestCase):
    def test_manual_catalog_covers_every_registered_module(self):
        from base.ui.registry import get_modules
        from knowledge.manual_catalog import manual_entries

        module_slugs = {module.slug for module in get_modules()}
        entries = manual_entries()
        manual_slugs = {entry['metadata']['module_slug'] for entry in entries}

        assert module_slugs == manual_slugs
        assert all(entry.get('manual_content') for entry in entries)
        assert all(entry.get('chat_eligible') is True for entry in entries)

    def test_external_seed_sources_are_not_chat_eligible(self):
        from knowledge.source_catalog import SEED_SOURCES

        external_sources = [
            entry for entry in SEED_SOURCES if entry['source_type'] != 'system_manual'
        ]

        assert external_sources
        assert all(not entry.get('chat_eligible', False) for entry in external_sources)
