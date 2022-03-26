import lib.utils as utils


class TestUtils:
    def test_grid_to_coordinates(self):
        assert utils.grid_to_coordinates("CM87vl") == (37.4634447, -122.2256803)

    def test_coordinates_to_grid(self):
        assert utils.coordinates_to_grid(37.4634447, -122.2256803) == "CM87vl"
