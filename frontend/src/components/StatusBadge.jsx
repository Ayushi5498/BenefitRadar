import React from 'react'

const STATUS_COLORS = {
    detected: { bg: '#dbeafe', text: '#1d4ed8' },
    submitted: { bg: '#fef9c3', text: '#854d0e' },
    under_review: { bg: '#ffedd5', text: '#9a3412' },
    approved: { bg: '#dcfce7', text: '#166534' },
    rejected: { bg: '#fee2e2', text: '#991b1b' },
    processed: { bg: '#dcfce7', text: '#166534' },
    pending: { bg: '#f1f5f9', text: '#475569' },
    skipped: { bg: '#f1f5f9', text: '#94a3b8' },
    claim_drafted: { bg: '#ede9fe', text: '#5b21b6' },
}

const STATUS_LABELS = {
    detected: 'Found',
    submitted: 'Submitted',
    under_review: 'Being Reviewed',
    approved: 'Approved',
    rejected: 'Rejected',
    processed: 'Processed',
    pending: 'Pending',
    skipped: 'Skipped',
    claim_drafted: 'Claim Drafted',
}

export default function StatusBadge({ status }) {
    const s = status?.toLowerCase() || 'pending'
    const colors = STATUS_COLORS[s] || { bg: '#f1f5f9', text: '#475569' }
    return (
        <span
            style={{
                background: colors.bg,
                color: colors.text,
                padding: '3px 10px',
                borderRadius: 99,
                fontSize: '0.78rem',
                fontWeight: 600,
                letterSpacing: '0.3px',
                whiteSpace: 'nowrap',
            }}
        >
            {STATUS_LABELS[s] || s}
        </span>
    )
}
