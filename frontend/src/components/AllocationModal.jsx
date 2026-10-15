/**
 * AllocationModal.jsx — Recommendation & Approval Dialog
 *
 * This is the core human-in-the-loop interaction of CareGrid RL.
 *
 * Flow:
 *   1. User clicks "Recommend" for a WAITING patient
 *   2. POST /allocation/recommend → system suggests best bed + reason
 *   3. Modal shows recommendation details with clinical justification
 *   4. User reviews and clicks "Approve Allocation"
 *   5. POST /allocation/approve → atomic DB transaction:
 *        • bed.status = OCCUPIED
 *        • patient.current_status = ADMITTED
 *        • ventilator reserved if needed
 *        • AuditLog entry written
 *   6. On 409 Conflict: show error (bed taken by another request)
 *
 * Props:
 *   patient   (Object)   - The patient being allocated
 *   onClose   (Function) - Close the modal
 *   onSuccess (Function) - Called after successful approval (to refresh)
 */

import { useState } from 'react'
import { recommendAllocation, approveAllocation } from '../services/api.js'
import { CheckCircle, AlertTriangle, BedDouble, Wind, Shield } from 'lucide-react'

const ACUITY_LABELS = { 1:'Non-urgent', 2:'Less Urgent', 3:'Urgent', 4:'Emergent', 5:'Critical' }

export default function AllocationModal({ patient, onClose, onSuccess }) {
  const [step, setStep]           = useState('idle')   // idle | loading | recommended | approving | done | error
  const [recommendation, setRec] = useState(null)
  const [errorMsg, setErrorMsg]   = useState('')

  async function handleRecommend() {
    setStep('loading')
    setErrorMsg('')
    try {
      const rec = await recommendAllocation(patient.patient_id)
      setRec(rec)
      setStep('recommended')
    } catch (e) {
      setErrorMsg(e.message)
      setStep('error')
    }
  }

  async function handleApprove() {
    setStep('approving')
    setErrorMsg('')
    try {
      await approveAllocation(patient.patient_id, recommendation.recommended_bed_id)
      setStep('done')
      setTimeout(() => {
        onSuccess()
        onClose()
      }, 1500)
    } catch (e) {
      setErrorMsg(e.message)
      setStep('error')
    }
  }

  return (
    <div className="modal-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal">
        {/* ── Header ── */}
        <div className="modal-title">Bed Allocation — {patient.patient_id}</div>
        <div className="modal-subtitle">
          Review and approve the resource allocation recommendation for this patient.
        </div>

        {/* ── Patient Info ── */}
        <div className="card" style={{ background: 'var(--bg-page)', boxShadow: 'none', padding: '14px' }}>
          <div className="info-row">
            <span className="info-label">Acuity</span>
            <span>
              <span className={`acuity-badge acuity-${patient.acuity}`}>{patient.acuity}</span>
              &nbsp;{ACUITY_LABELS[patient.acuity]}
            </span>
          </div>
          <div className="info-row">
            <span className="info-label">Specialty</span>
            <span className="info-value">{patient.specialty}</span>
          </div>
          <div className="info-row">
            <span className="info-label">Age Group</span>
            <span className="info-value">{patient.age_group}</span>
          </div>
          <div className="info-row">
            <span className="info-label">Predicted LOS</span>
            <span className="info-value">{patient.predicted_los} days</span>
          </div>
          <div className="info-row" style={{ marginTop: 6, gap: 6 }}>
            {patient.isolation_required && (
              <span className="badge badge-isolation"><Shield size={10} /> Isolation Required</span>
            )}
            {patient.ventilator_required && (
              <span className="badge badge-vent"><Wind size={10} /> Ventilator Required</span>
            )}
          </div>
        </div>

        <div className="modal-divider" />

        {/* ── Step: Idle ── */}
        {step === 'idle' && (
          <div style={{ textAlign: 'center', padding: '12px 0' }}>
            <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 16 }}>
              Click below to run the rule-based allocation engine and get a bed recommendation.
            </p>
            <button className="btn btn-primary" onClick={handleRecommend}>
              <BedDouble size={15} />
              Get Recommendation
            </button>
          </div>
        )}

        {/* ── Step: Loading ── */}
        {step === 'loading' && (
          <div className="loading-state" style={{ padding: 24 }}>
            <div className="spinner" />
            Running allocation engine…
          </div>
        )}

        {/* ── Step: Recommended ── */}
        {step === 'recommended' && recommendation && (
          <>
            {recommendation.status === 'RECOMMENDED' ? (
              <>
                <div className="recommendation-box">
                  <div className="rec-label">✓ Recommended Bed</div>
                  <div className="rec-bed">{recommendation.recommended_bed_id}</div>
                  <div className="rec-reason">{recommendation.reason}</div>
                  <div style={{ marginTop: 8, fontSize: 11, color: 'var(--brand-primary)' }}>
                    Algorithm: {recommendation.algorithm}
                  </div>
                </div>
                <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>
                  Once you approve, this allocation will be committed to the database and logged in the audit trail. This action cannot be undone.
                </p>
              </>
            ) : (
              <div className="error-box">
                <AlertTriangle size={14} style={{ display:'inline', marginRight: 4 }} />
                {recommendation.reason || 'No suitable bed found for this patient.'}
              </div>
            )}
          </>
        )}

        {/* ── Step: Approving ── */}
        {step === 'approving' && (
          <div className="loading-state" style={{ padding: 24 }}>
            <div className="spinner" />
            Committing allocation to database…
          </div>
        )}

        {/* ── Step: Done ── */}
        {step === 'done' && (
          <div style={{ display:'flex', flexDirection:'column', alignItems:'center', gap: 10, padding: 20 }}>
            <CheckCircle size={36} color="var(--status-available)" />
            <div style={{ fontWeight: 700, fontSize: 15 }}>Allocation Approved!</div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Audit log updated. Bed marked OCCUPIED.</div>
          </div>
        )}

        {/* ── Error ── */}
        {(step === 'error' || errorMsg) && step !== 'done' && (
          <div className="error-box" style={{ marginTop: 8 }}>
            <AlertTriangle size={14} style={{ display:'inline', marginRight: 4 }} />
            {errorMsg}
          </div>
        )}

        {/* ── Footer ── */}
        <div className="modal-footer">
          <button className="btn btn-ghost" onClick={onClose} disabled={step === 'approving' || step === 'done'}>
            Close
          </button>
          {step === 'recommended' && recommendation?.status === 'RECOMMENDED' && (
            <button className="btn btn-success" onClick={handleApprove}>
              <CheckCircle size={14} />
              Approve Allocation
            </button>
          )}
          {step === 'error' && (
            <button className="btn btn-primary" onClick={handleRecommend}>
              Try Again
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
