
from enum import Enum


class Role(str, Enum):
    ADMIN = "admin"
    DOCTOR = "doctor"
    NURSE = "nurse"
    OPERATOR = "operator"


ROLE_PERMISSIONS = {
    Role.ADMIN: {
        "patients:read",
        "beds:read",
        "staff:read",
        "equipment:read",
        "allocation:recommend",
        "allocation:approve",
        "metrics:read",
        "audit:read",
        "surge:simulate",
        "users:manage",
    },
    Role.DOCTOR: {
        "patients:read",
        "beds:read",
        "allocation:recommend",
        "allocation:approve",
    },
    Role.NURSE: {
        "patients:read",
        "beds:read",
        "equipment:read",
    },
    Role.OPERATOR: {
        "patients:read",
        "beds:read",
        "staff:read",
        "equipment:read",
        "metrics:read",
        "audit:read",
        "surge:simulate",
    },
}
