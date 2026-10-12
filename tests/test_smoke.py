import re

import carbon_scheduler


def test_version_is_semver():
    assert re.fullmatch(r"\d+\.\d+\.\d+", carbon_scheduler.__version__)
