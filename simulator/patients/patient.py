from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class Patient:
    patient_id: str
    age_group: str
    acuity: int
    specialty: str
    predicted_los: float       
    isolation_required: bool
    ventilator_required: bool
    arrival_time: datetime

    status: str = "WAITING"
    bed_id: Optional[str] = None
    equipment_id: Optional[str] = None
    admission_time: Optional[datetime] = None
    discharge_time : Optional[datetime] = None

    @property
    def wait_minutes(self) -> Optional[float]:
        if self.admission_time is None:
            return None
        return (self.admission_time- self.arrival_time).total_seconds()/ 60.0

    @classmethod
    def from_csv_row(cls, row:dict) -> "Patient":
        return cls(
            patient_id=row["patient_id"],
            age_group=row["age_group"],
            acuity=int(row["acuity"]),
            specialty=row["specialty"],
            predicted_los=float(row["predicted_los"]),
            isolation_required=row["isolation_required"].strip().upper() == "YES",
            ventilator_required=row["ventilator_required"].strip().upper() == "YES",
            arrival_time=datetime.strptime(row["arrival_time"], "%Y-%m-%d %H:%M:%S"),
        )