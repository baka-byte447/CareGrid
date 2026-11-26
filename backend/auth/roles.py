
from enum import Enum


class Role(str, Enum):
    ADMIN = "admin"
    DOCTOR = "doctor"
    NURSE = "nurse"
    OPERATOR = "operator"


ROLE_PERMISSIONS = {
    Role.ADMIN: {
        "patients:read",
        "patients:intake",
        "patients:discharge",
        "patients:transfer",
        "beds:read",
        "beds:create",
        "beds:release",
        "beds:clean",
        "staff:read",
        "equipment:read",
        "equipment:assign",
        "equipment:release",
        "allocation:recommend",
        "allocation:approve",
        "allocation:reject",
        "metrics:read",
        "audit:read",
        "surge:simulate",
        "users:manage",
    },
    Role.DOCTOR: {
        "patients:read",
        "patients:intake",
        "patients:discharge",
        "patients:transfer",
        "beds:read",
        "beds:release",
        "equipment:assign",
        "equipment:release",
        "allocation:recommend",
        "allocation:approve",
        "allocation:reject",
        "metrics:read",
    },
    Role.NURSE: {
        "patients:read",
        "patients:intake",
        "beds:read",
        "beds:release",
        "beds:clean",
        "equipment:read",
        "equipment:assign",
        "equipment:release",
        "metrics:read",
    },
    Role.OPERATOR: {
        "patients:read",
        "beds:read",
        "beds:clean",
        "staff:read",
        "equipment:read",
        "metrics:read",
        "audit:read",
        "surge:simulate",
    },
}
