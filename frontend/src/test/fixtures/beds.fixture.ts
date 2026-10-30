/**
 * TEST ONLY FIXTURE DATA
 * Not to be imported into any application or production code.
 */
import { Bed } from '@/api/schemas';

export const mockBeds: Bed[] = [
  {
    bed_id: 'ICU-01',
    bed_type: 'ICU',
    ward: 'ICU-A',
    status: 'AVAILABLE',
    isolation_capable: true,
  },
  {
    bed_id: 'ICU-02',
    bed_type: 'ICU',
    ward: 'ICU-A',
    status: 'OCCUPIED',
    isolation_capable: false,
  },
  {
    bed_id: 'SD-01',
    bed_type: 'STEP_DOWN',
    ward: 'Step-Down West',
    status: 'AVAILABLE',
    isolation_capable: false,
  },
  {
    bed_id: 'WARD-01',
    bed_type: 'WARD',
    ward: 'Ward 3 North',
    status: 'OCCUPIED',
    isolation_capable: false,
  },
];
