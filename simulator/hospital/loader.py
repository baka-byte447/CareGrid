import csv
from pathlib import Path
from typing import List

from simulator.hospital.state import HospitalState, Bed, StaffMember, Equipment
from simulator.patients.patient import Patient


def _read_csv(path: Path) -> List[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_hospital_state(data_dir: str, start_empty: bool = True) -> HospitalState:
    data_dir = Path(data_dir)
    state = HospitalState()

    for row in _read_csv(data_dir / "beds.csv"):
        bed = Bed(
            bed_id=row["bed_id"],
            bed_type=row["bed_type"],
            ward=row["ward"],
            status="AVAILABLE" if start_empty else row["status"],
            isolation_capable=row["isolation_capable"].strip().upper() == "YES",
        )
        state.beds[bed.bed_id] = bed

    for row in _read_csv(data_dir / "staff.csv"):
        staff = StaffMember(
            staff_id=row["staff_id"],
            role=row["role"],
            skill_level=row["skill_level"],
            shift=row["shift"],
            workload=row["workload"],
        )
        state.staff[staff.staff_id] = staff

    for row in _read_csv(data_dir / "equipment.csv"):
        eq = Equipment(
            equipment_id=row["equipment_id"],
            type=row["type"],
            status="AVAILABLE" if start_empty else row["status"],
            location=row["location"],
        )
        state.equipment[eq.equipment_id] = eq

    return state


def load_patients(data_dir: str, filename: str = "patients.csv") -> List[Patient]:
    """Loads the patient arrival list used to seed the event queue."""
    data_dir = Path(data_dir)
    rows = _read_csv(data_dir / filename)
    return [Patient.from_csv_row(row) for row in rows]
