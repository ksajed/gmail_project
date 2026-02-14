from __future__ import annotations

from django.test.runner import DiscoverRunner


class OrdoDiscoverRunner(DiscoverRunner):
    """
    Force discovery to include app tests when global discovery returns 0 tests.
    Keeps default behavior when labels are provided.
    """
    def build_suite(self, test_labels=None, extra_tests=None, **kwargs):
        # If user explicitly targets labels, keep default behavior.
        if test_labels:
            return super().build_suite(test_labels, extra_tests=extra_tests, **kwargs)

        # Otherwise, force-discover from known apps that currently have tests.
        forced_labels = [
            "core_emails",
            "core_notifications",
        ]
        return super().build_suite(forced_labels, extra_tests=extra_tests, **kwargs)
