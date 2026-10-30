/**
 * TEST ONLY FIXTURE DATA
 * Not to be imported into any application or production code.
 */
import { Patient } from '@/api/schemas';

export const mockPatients: Patient[] = [
  {
    patient_id: 'PAT-001',
    age_group: '45-64',
    acuity: 5,
    specialty: 'Cardiology',
    predicted_los: 4.5,
    isolation_required: false,
    ventilator_required: true,
    arrival_time: '2026-03-14T08:30:00',
    current_status: 'WAITING',
  },
  {
    patient_id: 'PAT-002',
    age_group: '65+',
    acuity: 4,
    specialty: 'Pulmonology',
    predicted_los: 6.2,
    isolation_required: true,
    ventilator_required: false,
    arrival_time: '2026-03-14T09:15:00',
    current_status: 'WAITING',
  },
  {
    patient_id: 'PAT-003',
    age_group: '18-44',
    acuity: 2,
    specialty: 'Orthopedics',
    predicted_los: 2.1,
    isolation_required: false,
    ventilator_required: false,
    arrival_time: '2026-03-14T07:45:00',
    current_status: 'ADMITTED',
  },
];
