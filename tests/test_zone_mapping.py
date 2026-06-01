# PROMPT:
# Generate tests for polygon-based CCTV zone mapping.
# CHANGES MADE:
# Added bottom-center helper validation for person bounding boxes.

from pipeline.zone_mapper import bottom_center, point_in_polygon


def test_bottom_center():
    assert bottom_center((10, 20, 30, 60)) == (20, 60)


def test_point_in_polygon():
    polygon = [[0, 0], [10, 0], [10, 10], [0, 10]]
    assert point_in_polygon((5, 5), polygon)
    assert not point_in_polygon((15, 5), polygon)
