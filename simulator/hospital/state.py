from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class Bed:
    bed_id: str
    bed_type: str            
    ward: str
    status: str              
    isolation_capable: bool


@dataclass
class StaffMember:
    staff_id: str
    role: str
    skill_level: str
    shift: str
    workload: str             


@dataclass
class Equipment:
    equipment_id: str
    type: str                  
    status: str                 
    location: str


@dataclass
class HospitalState:
    beds: Dict[str, Bed] = field(default_factory=dict)
    staff: Dict[str, StaffMember] = field(default_factory=dict)
    equipment: Dict[str, Equipment] = field(default_factory=dict)

    current_time: Optional[datetime] = None
    waiting_queue: List[str] = field(default_factory=list)              
    admitted_patients: Dict[str, str] = field(default_factory=dict)     


    def beds_by_type(self, bed_type: str) -> List[Bed]:
        return [b for b in self.beds.values() if b.bed_type == bed_type]

    def available_beds_by_type(self, bed_type: str) -> List[Bed]:
        return [b for b in self.beds_by_type(bed_type) if b.status == "AVAILABLE"]

    def available_ventilators(self) -> List[Equipment]:
        return [e for e in self.equipment.values()
                if e.type == "VENTILATOR" and e.status == "AVAILABLE"]

    def snapshot(self) -> dict:
        """A point-in-time summary of hospital occupancy ."""
        summary = {}
        for bed_type in ("ICU", "STEP_DOWN", "WARD"):
            beds = self.beds_by_type(bed_type)
            occupied = sum(1 for b in beds if b.status == "OCCUPIED")
            cleaning = sum(1 for b in beds if b.status == "CLEANING")
            total = len(beds)
            summary[bed_type] = {
                "occupied": occupied,
                "cleaning": cleaning,
                "available": total - occupied - cleaning,
                "total": total,
            }

        vents_total = sum(1 for e in self.equipment.values() if e.type == "VENTILATOR")
        vents_available = len(self.available_ventilators())

        return {
            "time": self.current_time,
            "beds": summary,
            "waiting_count": len(self.waiting_queue),
            "ventilators": {"available": vents_available, "total": vents_total},
        }
