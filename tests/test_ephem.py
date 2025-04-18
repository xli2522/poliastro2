from unittest import mock

from astropy import units as u
from astropy.coordinates import (
    ICRS,
    BarycentricMeanEcliptic,
    CartesianDifferential,
    CartesianRepresentation,
)
from astropy.tests.helper import assert_quantity_allclose
from astropy.time import Time
import numpy as np
import pytest

from poliastro2.worldview.solar_sys.bodies import Earth, Venus
from poliastro2.core.ephem import Ephem, SincInterpolator, SplineInterpolator
from poliastro2.core.frames import Planes
from poliastro2.core.orbit import Orbit
from poliastro2.warnings import TimeScaleWarning

AVAILABLE_INTERPOLATORS = [SincInterpolator(), SplineInterpolator()]
AVAILABLE_PLANES = Planes.__members__.values()


def assert_coordinates_allclose(
    actual, desired, rtol=1e-7, atol_scale=None, **kwargs
):
    if atol_scale is None:
        atol_scale = 0

    assert_quantity_allclose(
        actual.xyz,
        desired.xyz,
        rtol,
        atol=atol_scale * desired.xyz.unit,
        **kwargs,
    )
    if "s" in desired.differentials:
        assert_quantity_allclose(
            actual.differentials["s"].d_xyz,
            desired.differentials["s"].d_xyz,
            rtol=rtol,
            atol=atol_scale * desired.differentials["s"].d_xyz.unit,
            **kwargs,
        )


@pytest.fixture
def epochs():
    return Time(
        [
            "2020-03-01 12:00:00",
            "2020-03-02 12:00:00",
            "2020-03-03 12:00:00",
            "2020-03-04 12:00:00",
        ],
        scale="tdb",
    )


@pytest.fixture
def coordinates():
    return CartesianRepresentation(
        [(1, 0, 0), (0.9, 0.1, 0), (0.8, 0.2, 0), (0.7, 0.3, 0)] * u.au,
        xyz_axis=1,
        differentials=CartesianDifferential(
            [(0, 1, 0), (-0.1, 0.9, 0), (-0.2, 0.8, 0), (-0.3, 0.7, 0)]
            * (u.au / u.day),
            xyz_axis=1,
        ),
    )


@pytest.mark.parametrize("plane", AVAILABLE_PLANES)
def test_ephem_has_given_plane(epochs, coordinates, plane):
    ephem = Ephem(epochs, coordinates, plane)

    assert ephem.plane is plane


def test_ephem_fails_if_dimensions_are_not_correct(epochs, coordinates):
    unused_plane = Planes.EARTH_EQUATOR
    with pytest.raises(ValueError) as excinfo:
        Ephem(epochs[0], coordinates, unused_plane)
    assert (
        "Coordinates and epochs must have dimension 1, got 0 and 1"
        in excinfo.exconly()
    )


@pytest.mark.parametrize("interpolator", AVAILABLE_INTERPOLATORS)
def test_ephem_sample_no_arguments_returns_exactly_same_input(
    epochs, coordinates, interpolator
):
    unused_plane = Planes.EARTH_EQUATOR
    ephem = Ephem(coordinates, epochs, unused_plane)

    result_coordinates = ephem.sample(interpolator=interpolator)

    # Exactly the same
    assert np.all(result_coordinates == coordinates)


@pytest.mark.parametrize("interpolator", AVAILABLE_INTERPOLATORS)
def test_ephem_sample_scalar_epoch_returns_1_dimensional_coordinates(
    epochs, coordinates, interpolator
):
    unused_plane = Planes.EARTH_EQUATOR
    ephem = Ephem(coordinates, epochs, unused_plane)

    result_coordinates = ephem.sample(epochs[0], interpolator=interpolator)

    # Exactly the same
    assert result_coordinates.ndim == 1


def test_ephem_str_matches_expected_representation(epochs, coordinates):
    plane = Planes.EARTH_EQUATOR
    ephem = Ephem(coordinates, epochs, plane)

    expected_str = (
        "Ephemerides at 4 epochs "
        "from 2020-03-01 12:00:00.000 (TDB) to 2020-03-04 12:00:00.000 (TDB)"
    )

    assert repr(ephem) == str(ephem) == expected_str


@pytest.mark.parametrize("interpolator", AVAILABLE_INTERPOLATORS)
def test_ephem_sample_scalar_epoch_and_coordinates_returns_exactly_same_input(
    epochs, coordinates, interpolator
):
    unused_plane = Planes.EARTH_EQUATOR
    coordinates = coordinates[0].reshape(-1)
    epochs = epochs[0].reshape(-1)
    ephem = Ephem(coordinates, epochs, unused_plane)

    result_coordinates = ephem.sample(epochs[0], interpolator=interpolator)

    # Exactly the same
    assert result_coordinates == coordinates


@pytest.mark.parametrize("interpolator", AVAILABLE_INTERPOLATORS)
def test_ephem_sample_same_epochs_returns_same_input(
    epochs, coordinates, interpolator
):
    unused_plane = Planes.EARTH_EQUATOR
    ephem = Ephem(coordinates, epochs, unused_plane)

    result_coordinates = ephem.sample(epochs, interpolator=interpolator)

    # TODO: Should it return exactly the same?
    assert_coordinates_allclose(
        result_coordinates, coordinates, atol_scale=1e-17
    )


@pytest.mark.parametrize("interpolator", AVAILABLE_INTERPOLATORS)
def test_ephem_sample_existing_epochs_returns_corresponding_input(
    epochs, coordinates, interpolator
):
    unused_plane = Planes.EARTH_EQUATOR
    ephem = Ephem(coordinates, epochs, unused_plane)

    result_coordinates = ephem.sample(epochs[::2], interpolator=interpolator)

    # Exactly the same
    assert_coordinates_allclose(
        result_coordinates, coordinates[::2], atol_scale=1e-17
    )


def test_rv_no_parameters_returns_input_vectors(coordinates, epochs):
    unused_plane = Planes.EARTH_EQUATOR
    ephem = Ephem(coordinates, epochs, unused_plane)

    expected_r = coordinates.get_xyz(xyz_axis=1)
    expected_v = coordinates.differentials["s"].get_d_xyz(xyz_axis=1)

    r, v = ephem.rv()

    assert_quantity_allclose(r, expected_r)
    assert_quantity_allclose(v, expected_v)


def test_rv_scalar_epoch_returns_scalar_vectors(coordinates, epochs):
    unused_plane = Planes.EARTH_EQUATOR
    ephem = Ephem(coordinates, epochs, unused_plane)

    expected_r = coordinates.get_xyz(xyz_axis=1)[0]
    expected_v = coordinates.differentials["s"].get_d_xyz(xyz_axis=1)[0]

    r, v = ephem.rv(epochs[0])

    assert_quantity_allclose(r, expected_r)
    assert_quantity_allclose(v, expected_v)


@pytest.mark.parametrize("interpolator", AVAILABLE_INTERPOLATORS)
@pytest.mark.parametrize(
    "plane, FrameClass, rtol",
    [
        (Planes.EARTH_EQUATOR, ICRS, 1e-7),
        (Planes.EARTH_ECLIPTIC, BarycentricMeanEcliptic, 1e-5),
    ],
)
def test_ephem_from_body_has_expected_properties(
    interpolator, plane, FrameClass, rtol
):
    epochs = Time(
        [
            "2020-03-01 12:00:00",
            "2020-03-17 00:00:00.000",
            "2020-04-01 12:00:00.000",
        ],
        scale="tdb",
    )
    equatorial_coordinates = CartesianRepresentation(
        [
            (-1.40892271e08, 45067626.83900666, 19543510.68386639),
            (-1.4925067e08, 9130104.71634121, 3964948.59999307),
            (-1.46952333e08, -27413113.24215863, -11875983.21773582),
        ]
        * u.km,
        xyz_axis=1,
        differentials=CartesianDifferential(
            [
                (-10.14262131, -25.96929533, -11.25810932),
                (-2.28639444, -27.3906416, -11.87218591),
                (5.67814544, -26.84316701, -11.63720607),
            ]
            * (u.km / u.s),
            xyz_axis=1,
        ),
    )

    expected_coordinates = (
        ICRS(equatorial_coordinates)
        .transform_to(FrameClass())
        .represent_as(CartesianRepresentation, CartesianDifferential)
    )

    earth = Ephem.from_body(Earth, epochs, plane=plane)
    coordinates = earth.sample(interpolator=interpolator)

    assert earth.epochs is epochs
    assert_coordinates_allclose(coordinates, expected_coordinates, rtol=rtol)


def test_from_body_non_tdb_epochs_warning(epochs):
    unused_body = Earth
    epochs = Time.now()  # This uses UTC scale

    warning_pattern = "Input time was converted to scale='tdb'"
    with pytest.warns(TimeScaleWarning, match=warning_pattern):
        Ephem.from_body(unused_body, epochs)


def test_from_body_scalar_epoch_uses_reshaped_epochs():
    expected_epochs = Time(["2020-03-01 12:00:00"], scale="tdb")
    epochs = expected_epochs[0]

    unused_plane = Planes.EARTH_EQUATOR
    ephem = Ephem.from_body(Earth, epochs, plane=unused_plane)

    assert ephem.epochs == expected_epochs


@mock.patch("poliastro2.core.ephem.Horizons")
@pytest.mark.parametrize(
    "attractor,location_str",
    [(None, "@ssb"), (Earth, "500@399"), (Venus, "500@299")],
)
@pytest.mark.parametrize(
    "plane,refplane_str",
    [(Planes.EARTH_EQUATOR, "earth"), (Planes.EARTH_ECLIPTIC, "ecliptic")],
)
def test_ephem_from_horizons_calls_horizons_with_correct_parameters(
    horizons_mock, attractor, location_str, plane, refplane_str
):
    unused_name = "Strange Object"
    unused_id_type = "id_type"
    epochs = Time(["2020-03-01 12:00:00"], scale="tdb")

    horizons_mock().vectors.return_value = {
        "x": [1] * u.au,
        "y": [0] * u.au,
        "z": [0] * u.au,
        "vx": [0] * (u.au / u.day),
        "vy": [1] * (u.au / u.day),
        "vz": [0] * (u.au / u.day),
    }
    expected_coordinates = CartesianRepresentation(
        [(1, 0, 0)] * u.au,
        xyz_axis=1,
        differentials=CartesianDifferential(
            [(0, 1, 0)] * (u.au / u.day), xyz_axis=1
        ),
    )

    ephem = Ephem.from_horizons(
        unused_name,
        epochs,
        attractor=attractor,
        plane=plane,
        id_type=unused_id_type,
    )

    horizons_mock.assert_called_with(
        id=unused_name,
        location=location_str,
        epochs=epochs.jd,
        id_type=unused_id_type,
    )
    horizons_mock().vectors.assert_called_once_with(refplane=refplane_str)

    coordinates = ephem.sample()

    assert_coordinates_allclose(coordinates, expected_coordinates)


@mock.patch("poliastro2.core.ephem.Horizons")
def test_from_horizons_scalar_epoch_uses_reshaped_epochs(horizons_mock):
    unused_name = "Strange Object"
    unused_id_type = "id_type"
    unused_plane = Planes.EARTH_EQUATOR
    unused_location_str = "500@399"
    unused_attractor = Earth

    expected_epochs = Time(["2020-03-01 12:00:00"], scale="tdb")
    epochs = expected_epochs[0]

    horizons_mock().vectors.return_value = {
        "x": [1] * u.au,
        "y": [0] * u.au,
        "z": [0] * u.au,
        "vx": [0] * (u.au / u.day),
        "vy": [1] * (u.au / u.day),
        "vz": [0] * (u.au / u.day),
    }

    Ephem.from_horizons(
        unused_name,
        epochs,
        attractor=unused_attractor,
        plane=unused_plane,
        id_type=unused_id_type,
    )

    horizons_mock.assert_called_with(
        id=unused_name,
        location=unused_location_str,
        epochs=expected_epochs.jd,
        id_type=unused_id_type,
    )


def test_from_orbit_scalar_epoch_uses_reshaped_epochs():
    r = [-6045, -3490, 2500] * u.km
    v = [-3.457, 6.618, 2.533] * u.km / u.s
    orb = Orbit.from_vectors(Earth, r, v)
    expected_epochs = Time(["2020-01-02 12:00:00"])
    epoch = expected_epochs[0]

    unused_plane = Planes.EARTH_EQUATOR
    ephem = Ephem.from_orbit(orbit=orb, epochs=epoch, plane=unused_plane)

    assert ephem.epochs == expected_epochs


@pytest.mark.parametrize("interpolator", AVAILABLE_INTERPOLATORS)
@pytest.mark.parametrize("rtol", [1e-7, 1e-5])
def test_from_orbit_has_desired_properties(interpolator, rtol):
    epochs = Time(
        [
            "2020-02-01 12:00:00",
            "2020-02-13 12:00:00",
            "2020-03-04 12:00:00",
            "2020-03-17 12:00:00",
        ]
    )
    expected_coordinates = CartesianRepresentation(
        [
            (336.77109079, -1447.38211842, -743.72094119),
            (-1133.43957703, 449.41297342, 3129.10416554),
            (201.42480053, -1978.64139325, -287.25776291),
            (-1084.94556884, -1713.5357774, 3298.72284309),
        ]
        * u.km,
        xyz_axis=1,
        differentials=CartesianDifferential(
            [
                (-2.68502706, -14.85798508, 9.66683585),
                (1.36841306, 7.30080155, -4.88822441),
                (-3.46999908, -10.04899184, 11.19715233),
                (-1.46069855, 5.88696886, 3.28112281),
            ]
            * (u.km / u.s),
            xyz_axis=1,
        ),
    )

    r = [-1000, -2000, 3100] * u.km
    v = [-1.836, 5.218, 4.433] * u.km / u.s
    orb = Orbit.from_vectors(Earth, r, v)

    unused_plane = Planes.EARTH_EQUATOR
    ephem = Ephem.from_orbit(orbit=orb, epochs=epochs, plane=unused_plane)
    coordinates = ephem.sample()

    assert ephem.epochs is epochs
    assert_coordinates_allclose(coordinates, expected_coordinates, rtol=rtol)
