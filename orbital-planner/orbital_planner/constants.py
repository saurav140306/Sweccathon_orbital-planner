"""Physical constants for 2D Earth-centered inertial frame."""

import math

MU_EARTH_KM3_S2 = 398_600.0
EARTH_RADIUS_KM = 6_371.0
DEFAULT_DT_S = 10.0

# Moon (Luna) — used when target.kind == "moon"
MU_MOON_KM3_S2 = 4_902.800_066  # km³/s² (GM)
MOON_RADIUS_KM = 1_737.4

# Visual / kinematic: Earth sidereal rotation (~86164 s)
EARTH_SIDEREAL_PERIOD_S = 86_164.0
EARTH_SPIN_RAD_S = 2.0 * math.pi / EARTH_SIDEREAL_PERIOD_S

# Default satellite body spin on canvas (rad/s) — not used in scoring
DEFAULT_BODY_SPIN_RAD_S = 0.12
