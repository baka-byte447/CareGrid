import { useQuery } from '@tanstack/react-query'
import { apiGet } from '@/api/client'

interface Activity {
  telemetry: { patient_id: string, observed_at: string, news2: number, risk: string, sofa?: number | null, transfer_requested: boolean }[]
  fhir_encounters: string[]
}

export function ClinicalActivity() {
  const query = useQuery({
    queryKey: ['clinical-activity'],
    queryFn: () => apiGet<Activity>('/clinical/activity'),
    refetchInterval: 30000,
  })
  return (
    <details className="rounded-xl border p-4">
      <summary>Clinical observations and FHIR encounters</summary>
      {query.isPending && <p>Loading clinical activity...</p>}
      {query.isError && <p role="alert">Clinical activity could not be loaded.</p>}
      {query.data && (
        <div className="mt-3 space-y-2">
          <h3>Latest NEWS2 observations</h3>
          {query.data.telemetry.length === 0 && <p>No observations recorded.</p>}
          {query.data.telemetry.map((row, i) => (
            <p key={i}>{row.patient_id} ? {new Date(row.observed_at).toLocaleString()} ? NEWS2 {row.news2}
              {row.sofa != null && ` ? Classic SOFA ${row.sofa}`}
              {' ? '}{row.risk.replace('_', ' ')}{row.transfer_requested && ' ? ICU review requested'}</p>
          ))}
          <h3>Imported encounters</h3>
          <p>{query.data.fhir_encounters.join(', ') || 'No FHIR encounters imported.'}</p>
        </div>
      )}
    </details>
  )
}
