import React, { useEffect, useState, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getClaim, submitClaim, approveClaim } from '../api/client'
import StatusBadge from '../components/StatusBadge'

// ── helpers ──────────────────────────────────────────────────────────────────

const fieldRow = (label, value) => (
    <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        padding: '0.65rem 0',
        borderBottom: '1px solid #f1f5f9',
        fontSize: '0.9rem',
    }}>
        <span style={{ color: '#64748b' }}>{label}</span>
        <span style={{ fontWeight: 500, color: '#0f172a', textAlign: 'right', maxWidth: '60%' }}>
            {value ?? '—'}
        </span>
    </div>
)

// Status tracker — mirrors the "You track it" screen from PDF Slide 8
const STEPS = ['detected', 'submitted', 'under_review', 'approved']

function StatusTracker({ status }) {
    const rejected = status === 'rejected'
    const activeIdx = rejected ? 2 : STEPS.indexOf(status)

    return (
        <div style={{ margin: '1rem 0' }}>
            {STEPS.map((step, idx) => {
                const done = idx < activeIdx || (idx === activeIdx && !rejected)
                const active = idx === activeIdx && !rejected
                const label = { detected: 'Found', submitted: 'Submitted', under_review: 'Being Reviewed', approved: 'Approved' }[step]
                return (
                    <div key={step} style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: 10 }}>
                        <div style={{
                            width: 22, height: 22, borderRadius: '50%',
                            background: done ? '#0d9488' : active ? '#99f6e4' : '#e2e8f0',
                            border: active ? '2px solid #0d9488' : 'none',
                            flexShrink: 0,
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            fontSize: '0.7rem', color: '#fff',
                        }}>
                            {done && '✓'}
                        </div>
                        <span style={{
                            fontSize: '0.88rem',
                            fontWeight: active || done ? 600 : 400,
                            color: done || active ? '#0f172a' : '#94a3b8',
                        }}>
                            {label}
                        </span>
                    </div>
                )
            })}
            {rejected && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginTop: 4 }}>
                    <div style={{
                        width: 22, height: 22, borderRadius: '50%', background: '#ef4444',
                        flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontSize: '0.7rem', color: '#fff',
                    }}>✕</div>
                    <span style={{ fontSize: '0.88rem', fontWeight: 600, color: '#ef4444' }}>Rejected</span>
                </div>
            )}
        </div>
    )
}

// ── main component ────────────────────────────────────────────────────────────

export default function ClaimDetail() {
    const { id } = useParams()
    const navigate = useNavigate()
    const [claim, setClaim] = useState(null)
    const [loading, setLoading] = useState(true)
    const [actionLoading, setActionLoading] = useState(false)
    const [message, setMessage] = useState(null)

    // Track whether the user edited any pre-filled field (for metrics Item 3)
    const [edited, setEdited] = useState(false)
    // Editable copies of pre-filled fields
    const [editAmount, setEditAmount] = useState('')
    const originalAmount = useRef(null)

    const load = () =>
        getClaim(id)
            .then((c) => {
                setClaim(c)
                if (originalAmount.current === null) {
                    originalAmount.current = c.amount_usd
                    setEditAmount(String(c.amount_usd))
                }
            })
            .catch(console.error)
            .finally(() => setLoading(false))

    useEffect(() => { load() }, [id])

    const handleAmountChange = (v) => {
        setEditAmount(v)
        if (parseFloat(v) !== originalAmount.current) setEdited(true)
        else setEdited(false)
    }

    const handleSubmit = async () => {
        setActionLoading(true)
        try {
            // Pass `edited` flag so the backend can track pre-fill accuracy (Item 3)
            const res = await submitClaim(id, { edited })
            setMessage({ type: 'success', text: res.message })
            await load()
        } catch (e) {
            setMessage({ type: 'error', text: e.response?.data?.detail || 'Failed to submit.' })
        } finally {
            setActionLoading(false)
        }
    }

    const handleApprove = async (approved) => {
        setActionLoading(true)
        try {
            const res = await approveClaim(id, approved)
            setMessage({ type: 'success', text: res.message })
            await load()
        } catch (e) {
            setMessage({ type: 'error', text: e.response?.data?.detail || 'Failed.' })
        } finally {
            setActionLoading(false)
        }
    }

    if (loading) return <div style={{ color: '#94a3b8', padding: '3rem', textAlign: 'center' }}>Loading...</div>
    if (!claim) return <div style={{ padding: '3rem', textAlign: 'center' }}>Claim not found.</div>

    const date = new Date(claim.purchased_at).toLocaleDateString('en-US', {
        month: 'long', day: 'numeric', year: 'numeric',
    })

    const canSubmit = claim.status === 'detected'
    const canApprove = ['submitted', 'under_review'].includes(claim.status)
    const isApproved = claim.status === 'approved'

    const inputStyle = {
        width: '100%',
        padding: '0.45rem 0.65rem',
        border: `1px solid ${edited ? '#f59e0b' : '#e2e8f0'}`,
        borderRadius: 6,
        fontSize: '0.88rem',
        color: '#0f172a',
        background: edited ? '#fffbeb' : '#fff',
        outline: 'none',
    }

    return (
        <div style={{ maxWidth: 680, margin: '0 auto' }}>
            <button
                onClick={() => navigate('/')}
                style={{ background: 'none', border: 'none', color: '#0d9488', cursor: 'pointer', fontSize: '0.88rem', marginBottom: '1rem', padding: 0 }}
            >
                ← Back to Dashboard
            </button>

            {/* Header */}
            <div style={{ marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <h1 style={{ fontSize: '1.4rem', fontWeight: 700, color: '#0d3d3a' }}>Claim Details</h1>
                <StatusBadge status={claim.status} />
                {claim.edited && (
                    <span style={{ fontSize: '0.72rem', color: '#f59e0b', fontWeight: 600, background: '#fffbeb', padding: '2px 8px', borderRadius: 99, border: '1px solid #fde68a' }}>
                        Edited
                    </span>
                )}
            </div>

            {message && (
                <div style={{
                    padding: '0.75rem 1rem', borderRadius: 8, marginBottom: '1rem',
                    background: message.type === 'success' ? '#dcfce7' : '#fee2e2',
                    color: message.type === 'success' ? '#166534' : '#991b1b',
                    fontSize: '0.88rem',
                }}>
                    {message.text}
                </div>
            )}

            {edited && canSubmit && (
                <div style={{
                    padding: '0.65rem 1rem', borderRadius: 8, marginBottom: '1rem',
                    background: '#fffbeb', color: '#92400e', fontSize: '0.83rem',
                    border: '1px solid #fde68a',
                }}>
                    ⚠️ You've changed a pre-filled field. The edited flag will be sent with your claim for reporting.
                </div>
            )}

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
                {/* Claim fields */}
                <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 12, padding: '1.25rem' }}>
                    <h2 style={{ fontSize: '0.95rem', fontWeight: 700, marginBottom: '0.5rem', color: '#0f172a' }}>
                        Claim Information
                    </h2>
                    <p style={{ fontSize: '0.8rem', color: '#64748b', marginBottom: '0.75rem' }}>
                        {claim.benefit_description}
                    </p>

                    {fieldRow('Store', claim.merchant_name)}

                    {/* Amount — editable so we can track pre-fill accuracy */}
                    <div style={{
                        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                        padding: '0.65rem 0', borderBottom: '1px solid #f1f5f9', fontSize: '0.9rem',
                    }}>
                        <span style={{ color: '#64748b' }}>Amount</span>
                        {canSubmit ? (
                            <input
                                type="number"
                                step="0.01"
                                value={editAmount}
                                onChange={(e) => handleAmountChange(e.target.value)}
                                style={{ ...inputStyle, width: 120, textAlign: 'right' }}
                            />
                        ) : (
                            <span style={{ fontWeight: 500 }}>${claim.amount_usd?.toFixed(2)}</span>
                        )}
                    </div>

                    {fieldRow('Date', date)}
                    {fieldRow('Benefit', claim.benefit_type)}
                    {fieldRow('Coverage Cap', `$${claim.coverage_cap_usd?.toFixed(2)}`)}
                    {claim.travel_booking_ref && fieldRow('Booking Ref', claim.travel_booking_ref)}
                    {claim.store_refused_return && fieldRow('Return Refused', 'Yes')}
                    {isApproved && fieldRow('Payout', `$${claim.payout_amount_usd?.toFixed(2)}`)}
                    {claim.reviewer_notes && fieldRow('Notes', claim.reviewer_notes)}
                </div>

                {/* Status tracker */}
                <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 12, padding: '1.25rem' }}>
                    <h2 style={{ fontSize: '0.95rem', fontWeight: 700, marginBottom: '0.75rem', color: '#0f172a' }}>
                        Claim Status
                    </h2>
                    <StatusTracker status={claim.status} />
                    {isApproved && (
                        <div style={{
                            marginTop: '1rem', fontSize: '0.83rem', color: '#166534',
                            background: '#dcfce7', padding: '0.6rem 0.9rem', borderRadius: 8,
                        }}>
                            ${claim.payout_amount_usd?.toFixed(2)} back in your account in 3–5 business days.
                        </div>
                    )}
                </div>
            </div>

            {/* Actions */}
            {canSubmit && (
                <button
                    onClick={handleSubmit}
                    disabled={actionLoading}
                    style={{
                        width: '100%', padding: '0.85rem',
                        background: '#0d9488', color: '#fff', border: 'none',
                        borderRadius: 10, fontSize: '1rem', fontWeight: 700,
                        cursor: 'pointer', opacity: actionLoading ? 0.6 : 1,
                    }}
                >
                    {actionLoading ? 'Submitting...' : 'Submit Claim'}
                </button>
            )}

            {canApprove && (
                <div style={{ display: 'flex', gap: '0.75rem' }}>
                    <button
                        onClick={() => handleApprove(true)}
                        disabled={actionLoading}
                        style={{
                            flex: 1, padding: '0.75rem', background: '#0d9488', color: '#fff',
                            border: 'none', borderRadius: 10, fontWeight: 700, cursor: 'pointer',
                            opacity: actionLoading ? 0.6 : 1,
                        }}
                    >
                        ✓ Approve (Demo)
                    </button>
                    <button
                        onClick={() => handleApprove(false)}
                        disabled={actionLoading}
                        style={{
                            flex: 1, padding: '0.75rem', background: '#fff', color: '#ef4444',
                            border: '1px solid #ef4444', borderRadius: 10, fontWeight: 700,
                            cursor: 'pointer', opacity: actionLoading ? 0.6 : 1,
                        }}
                    >
                        ✕ Reject (Demo)
                    </button>
                </div>
            )}
        </div>
    )
}
