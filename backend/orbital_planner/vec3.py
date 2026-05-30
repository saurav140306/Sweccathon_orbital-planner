"""3D vector helpers — promote legacy 2D states to z=0."""

from __future__ import annotations

Vec3 = tuple[float, float, float]


def to_vec3(value: object) -> Vec3:
    if isinstance(value, (list, tuple)):
        if len(value) == 2:
            return (float(value[0]), float(value[1]), 0.0)
        if len(value) == 3:
            return (float(value[0]), float(value[1]), float(value[2]))
    raise ValueError("Expected length-2 or length-3 vector")


def vec3_mag(v: Vec3) -> float:
    return (v[0] ** 2 + v[1] ** 2 + v[2] ** 2) ** 0.5


def vec3_sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
