from datetime import datetime, timedelta
from typing import Callable, Dict, List, Optional

from simulator.events.event_queue import EventQueue
from simulator.hospital.state import HospitalState
from simulator.hospital.allocation_rules import decide_bed, AllocationDecision
from simulator.patients.patient import Patient

BED_CLEANING_MINUTES = 25  


class SimulationEngine:
    def __init__(self, state: HospitalState, patients: List[Patient]):
        self.state = state
        self.patients: Dict[str, Patient] = {p.patient_id: p for p in patients}
        self.queue = EventQueue()
        self.admitted_count = 0
        self.discharged_count = 0

    def seed_arrivals(self) -> None:
        """Converts every loaded patient into a PATIENT_ARRIVAL event."""
        for patient in self.patients.values():
            self.queue.schedule(
                patient.arrival_time, "PATIENT_ARRIVAL", {"patient_id": patient.patient_id}
            )


    def _handle_arrival(self, patient_id: str) -> None:
        patient = self.patients[patient_id]
        decision = decide_bed(patient, self.state)
        if decision is not None:
            self._admit(patient, decision)
        else:
            self.state.waiting_queue.append(patient_id)

    def _admit(self, patient: Patient, decision: AllocationDecision) -> None:
        bed = self.state.beds[decision.bed_id]
        bed.status = "OCCUPIED"

        if decision.equipment_id is not None:
            self.state.equipment[decision.equipment_id].status = "IN_USE"

        patient.status = "ADMITTED"
        patient.bed_id = decision.bed_id
        patient.equipment_id = decision.equipment_id
        patient.admission_time = self.state.current_time
        self.state.admitted_patients[patient.patient_id] = decision.bed_id
        self.admitted_count += 1

        los_minutes = patient.predicted_los * 24 * 60
        discharge_time = self.state.current_time + timedelta(minutes=los_minutes)
        self.queue.schedule(
            discharge_time, "PATIENT_DISCHARGE", {"patient_id": patient.patient_id}
        )

    def _handle_discharge(self, patient_id: str) -> None:
        patient = self.patients[patient_id]
        bed = self.state.beds[patient.bed_id]

        patient.status = "DISCHARGED"
        patient.discharge_time = self.state.current_time
        self.discharged_count += 1
        del self.state.admitted_patients[patient_id]

        if patient.equipment_id is not None:
            self.state.equipment[patient.equipment_id].status = "AVAILABLE"

        bed.status = "CLEANING"
        release_time = self.state.current_time + timedelta(minutes=BED_CLEANING_MINUTES)
        self.queue.schedule(release_time, "BED_RELEASE", {"bed_id": bed.bed_id})

    def _handle_bed_release(self, bed_id: str) -> None:
        self.state.beds[bed_id].status = "AVAILABLE"
        self._retry_waiting_queue()

    def _retry_waiting_queue(self) -> None:
        """After a bed frees up, re-attempt allocation for waiting patients,
        oldest-first, looping until a full pass makes no further progress."""
        progressed = True
        while progressed and self.state.waiting_queue:
            progressed = False
            for patient_id in list(self.state.waiting_queue):
                patient = self.patients[patient_id]
                decision = decide_bed(patient, self.state)
                if decision is not None:
                    self.state.waiting_queue.remove(patient_id)
                    self._admit(patient, decision)
                    progressed = True

    def run(self, max_time: Optional[datetime] = None,
             on_tick: Optional[Callable[[HospitalState], None]] = None) -> None:
        """
        Runs until the event queue drains (or max_time is reached).
        on_tick(state), if provided, is called after every event
        """
        while not self.queue.is_empty():
            event = self.queue.pop()
            if max_time is not None and event.timestamp > max_time:
                break

            self.state.current_time = event.timestamp

            if event.event_type == "PATIENT_ARRIVAL":
                self._handle_arrival(event.payload["patient_id"])
            elif event.event_type == "PATIENT_DISCHARGE":
                self._handle_discharge(event.payload["patient_id"])
            elif event.event_type == "BED_RELEASE":
                self._handle_bed_release(event.payload["bed_id"])

            if on_tick is not None:
                on_tick(self.state)
