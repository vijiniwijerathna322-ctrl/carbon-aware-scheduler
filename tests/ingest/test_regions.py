from zoneinfo import ZoneInfoNotFoundError

import pytest

from carbon_scheduler.regions import Region, UnknownRegionError, load_regions


def test_regions_independent_of_cwd(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    assert load_regions()["CISO"].timezone == "America/Los_Angeles"
    with pytest.raises(UnknownRegionError, match="CISO"):
        load_regions()["../CISO"]


def test_region_validation():
    with pytest.raises(ZoneInfoNotFoundError):
        Region("CISO", "Invalid/Timezone", 36.7, -119.4)
    with pytest.raises(ValueError):
        Region("../CISO", "UTC", 0, 0)
    with pytest.raises(ValueError):
        Region("CISO", "UTC", 999, 0)
