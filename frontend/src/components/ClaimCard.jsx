import React from 'react'
import { useNavigate } from 'react-router-dom'
import StatusBadge from './StatusBadge'

const BENEFIT_ICONS = {
    'Purchase Protection': '🛡️',
    'Return Protection': '↩️',
    'Travel Delay Insurance': '✈️',
}

export default function ClaimCard({ claim }) {
    const navigate = useNavigate()
    const icon = BENEFIT_ICONS[claim.benefit_type] || '📋'
    const date = new Date(claim.purchased_at).toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
    })

    return (
        <div
            onClick={() => navigate(`/claims/${claim.id}`)}
            style={{
                background: '#fff',
                border: '1px solid #e2e8f0',
                borderRadius: 12,
                padding: '1.1rem 1.25rem',
                cursor: 'pointer',
                transition: 'box-shadow 0.15s, border-color 0.15s',
                display: 'flex',
                alignItems: 'center',
                gap: '1rem',
            }}
            onMouseEnter={(e) => {
                e.currentTarget.style.boxShadow = '0 4px 16px rgba(13,61,58,0.10)'
                e.currentTarget.style.borderColor = '#2dd4bf'
            }}
            onMouseLeave={(e) => {
                e.currentTarget.style.boxShadow = 'none'
                e.currentTarget.style.borderColor = '#e2e8f0'
            }}
        >
            <div
                style={{
                    width: 44,
                    height: 44,
                    borderRadius: 10,
                    background: '#f0fdfa',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '1.4rem',
                    flexShrink: 0,
                }}
            >
                {icon}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontWeight: 600, fontSize: '0.95rem', color: '#0f172a' }}>
                    {claim.merchant_name}
                </div>
                <div style={{ fontSize: '0.82rem', color: '#64748b', marginTop: 2 }}>
                    {claim.benefit_type} · {date}
                </div>
            </div>
            <div style={{ textAlign: 'right', flexShrink: 0 }}>
                <div style={{ fontWeight: 700, fontSize: '1rem', color: '#0f172a' }}>
                    ${claim.amount_usd?.toFixed(2)}
                </div>
                <div style={{ marginTop: 4 }}>
                    <StatusBadge status={claim.status} />
                </div>
            </div>
        </div>
    )
}
