import sys

from astropy import units as u

from poliastro2.core.actions.propagate.enums import PropagatorKind
from poliastro2.core.twobody.states import ClassicalState
from poliastro2.math.propagation import danby_coe as danby_fast

from ._compat import OldPropagatorModule

sys.modules[__name__].__class__ = OldPropagatorModule


class DanbyPropagator:
    """Kepler solver for both elliptic and parabolic orbits based on Danby's algorithm.

    Notes
    -----
    This algorithm was developed by Danby in his paper *The solution of Kepler
    Equation* with DOI: https://doi.org/10.1007/BF01686811
    """

    kind = PropagatorKind.ELLIPTIC | PropagatorKind.HYPERBOLIC

    def propagate(self, state, tof):
        state = state.to_classical()

        nu = (
            danby_fast(
                state.attractor.k.to_value(u.km**3 / u.s**2),
                *state.to_value(),
                tof.to_value(u.s),
            )
            << u.rad
        )

        new_state = ClassicalState(
            state.attractor, state.to_tuple()[:5] + (nu,), state.plane
        )
        return new_state
