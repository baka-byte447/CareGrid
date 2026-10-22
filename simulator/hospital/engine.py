from datetime import datetime, timedelta
from typing import Callable, Dict, List, Optional

from simulator.events.event_queue import EventQueue
from simulator.hospital.state import HospitalState
from simulator.hospital.allocation_rules import (
    AllocationDecision, decide_bed, validate_allocation,
)
from simulator.patients.patient import Patient

BED_CLEANING_MINUTES = 25  


class SimulationEngine:
    def __init__(self, state: HospitalState, patients: List[Patient]):
        self.state = state
        self.patients: Dict[str, Patient] = {p.patient_id: p for p in patients}
        self.queue = EventQueue()
        self.admitted_count = 0
        self.discharged_count = 0
        # External-decision mode is opt-in; the legacy run() path is unc    hanged.
        self._external_decision_mode = False
        self._pending_patient_id: Optional[str] = None
        self._deferred_waiters = set()
        self._last_event_time: Optional[datetime] = None

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
        discharge_time = self.state.current_time + timedelta(
            minutes=los_minutes
        )

        patient.discharge_time = discharge_time

        self.queue.schedule(
            discharge_time,
            "PATIENT_DISCHARGE",
            {"patient_id": patient.patient_id},
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


    def enable_external_decisions(self) -> None:
        """Enable event stepping for an external policy (e.g. a Gymnasium agent).

        Arrivals and newly available beds become decision points instead of being
        allocated automatically. The default run() behavior remains rule-based.
        """
        self._external_decision_mode = True
        self._pending_patient_id = None
        self._deferred_waiters.clear()

    @property
    def pending_patient_id(self) -> Optional[str]:
        return self._pending_patient_id

    def advance_to_decision(self, max_time: Optional[datetime] = None) -> Optional[str]:
        """Process events until a patient decision is required or the episode ends.

        Existing discharges and bed-cleaning events continue to be processed. A
        waiting patient is reconsidered when a bed is released, oldest first.
        """
        if not self._external_decision_mode:
            raise RuntimeError("Call enable_external_decisions() before stepping externally.")
        if self._pending_patient_id is not None:
            return self._pending_patient_id

        while not self.queue.is_empty():
            next_event = self.queue.peek()
            if max_time is not None and next_event.timestamp > max_time:
                self.state.current_time = max_time
                return None
            event = self.queue.pop()
            self.state.current_time = event.timestamp
            if self._last_event_time != event.timestamp:
                self._deferred_waiters.clear()
                self._last_event_time = event.timestamp

            if event.event_type == "PATIENT_ARRIVAL":
                patient_id = event.payload["patient_id"]
                # Ignore stale/duplicate arrival events instead of offering an
                # already admitted or discharged patient for another admission.
                patient = self.patients[patient_id]
                if patient.status == "WAITING" and patient_id not in self.state.admitted_patients:
                    self._pending_patient_id = patient_id
                    return patient_id
            elif event.event_type == "PATIENT_DISCHARGE":
                self._handle_discharge(event.payload["patient_id"])
            elif event.event_type == "BED_RELEASE":
                self.state.beds[event.payload["bed_id"]].status = "AVAILABLE"
                # Preserve queue order, but only ask the policy to act when at
                # least one complete, currently feasible allocation exists.
                for patient_id in self.state.waiting_queue:
                    if patient_id in self._deferred_waiters:
                        continue
                    patient = self.patients[patient_id]
                    if decide_bed(patient, self.state) is not None:
                        self._pending_patient_id = patient_id
                        return patient_id
        return None

    def defer_pending_patient(self) -> str:
        """Keep the pending patient waiting and avoid repeating the decision at this time."""
        if self._pending_patient_id is None:
            raise RuntimeError("There is no pending patient decision.")
        patient_id = self._pending_patient_id
        if patient_id not in self.state.waiting_queue:
            self.state.waiting_queue.append(patient_id)
        self._deferred_waiters.add(patient_id)
        self._pending_patient_id = None
        return patient_id

    def admit_pending_patient(self, decision: AllocationDecision) -> str:
        """Validate and admit the pending patient without partial mutation on error."""
        if not self._external_decision_mode:
            raise RuntimeError(
                "admit_pending_patient() requires external-decision mode; "
                "call enable_external_decisions() first."
            )
        if self._pending_patient_id is None:
            raise RuntimeError("There is no pending patient decision.")
        patient_id = self._pending_patient_id
        patient = self.patients.get(patient_id)
        if patient is None:
            raise RuntimeError(f"Pending patient {patient_id!r} does not exist in the engine.")

        # Validate every precondition before touching the waiting queue, patient,
        # bed/equipment state, counters, or pending-decision pointer.
        validate_allocation(patient, self.state, decision)
        if patient_id in self.state.waiting_queue:
            self.state.waiting_queue.remove(patient_id)
        self._admit(patient, decision)
        self._pending_patient_id = None
        self._deferred_waiters.discard(patient_id)
        return patient_id

    def run(
        self,
        max_time: Optional[datetime] = None,
        on_tick: Optional[Callable[[HospitalState], None]] = None,
    ) -> None:
        """
        Runs until the event queue drains or max_time is reached.
        Events beyond max_time remain in the queue.
        on_tick(state), if provided, is called after every processed event.
        """
        if self._external_decision_mode:
            raise RuntimeError(
                "run() is unavailable in external-decision mode. "
                "Use advance_to_decision() and submit an explicit action."
            )
        while not self.queue.is_empty():
            # Check the next event before removing it from the queue.
            if (
                max_time is not None
                and self.queue.peek().timestamp > max_time
            ):
                break

            event = self.queue.pop()

            self.state.current_time = event.timestamp

            if event.event_type == "PATIENT_ARRIVAL":
                self._handle_arrival(event.payload["patient_id"])
            elif event.event_type == "PATIENT_DISCHARGE":
                self._handle_discharge(event.payload["patient_id"])
            elif event.event_type == "BED_RELEASE":
                self._handle_bed_release(event.payload["bed_id"])

            if on_tick is not None:
                on_tick(self.state)
