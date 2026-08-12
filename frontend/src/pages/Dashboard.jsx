import React, { useEffect, useState, useCallback } from 'react'
import { getClaims, getCards } from '../api/client'
import ClaimCard from '../components/ClaimCard'

const sectionStyle = {
    background: '#fff',
    border: '1px solid #e2e8f0',
    borderRadius: 16,
    padding: '1.5rem',
    marginBottom: '1.5rem',
}

const statBox = {
    background: '#f0fdfa',
    border: '1px solid #99f6e4',
    borderRadius: 12,
    padding: '1.25rem 1.5rem',
    flex: 1,
    minWidth: 140,
}

const POLL_MS = 6000   // refresh every 6 s — Item 4

export default function Dashboard() {
    const [claims, setClaims] = useState([])
    const [cards, setCards] = useState([])
    const [loading, setLoading] = useState(true)
    const [filter, setFilter] = useState('all')
    const [lastUpdated, setLastUpdated] = useState(null)

    const fetchAll = useCallback(() => {
        Promise.all([getClaims({ limit: 100 }), getCards()])
            .then(([claimsData, cardsData]) => {
                setClaims(claimsData.claims || [])
                setCards(cardsData.cards || [])
                setLastUpdated(new Date())
            })
            .catch(console.error)
            .finally(() => setLoading(false))
    }, [])

    // Initial load + polling
    useEffect(() => {
        fetchAll()
        const id = setInterval(fetchAll, POLL_MS)
        return () => clearInterval(id)
    }, [fetchAll])

    const filtered =
        filter === 'all' ? claims : claims.filter((c) => c.status === filter)

    const total = claims.length
    const approved = claims.filter((c) => c.status === 'approved').length
    const pending = claims.filter((c) =>
        ['detected', 'submitted', 'under_review'].includes(c.status)
    ).length
    const totalValue = claims.reduce((s, c) => s + (c.amount_usd || 0), 0)

    return (
        <div>
            {/* Header */}
            <div style={{ marginBottom: '1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', flexWrap: 'wrap', gap: '0.5rem' }}>
                <div>
                    <h1 style={{ fontSize: '1.6rem', fontWeight: 700, color: '#0d3d3a' }}>
                        Your Benefits Dashboard
                    </h1>
                    <p style={{ color: '#64748b', marginTop: 4, fontSize: '0.9rem' }}>
                        Coverage you already paid for — automatically found and claimed.
                    </p>
                </div>
                {lastUpdated && (
                    <span style={{ fontSize: '0.72rem', color: '#94a3b8' }}>
                        Live · updated {lastUpdated.toLocaleTimeString()}
                    </span>
                )}
            </div>

            {/* Stats */}
            <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem', flexWrap: 'wrap' }}>
                <div style={statBox}>
                    <div style={{ fontSize: '2rem', fontWeight: 700, color: '#0d9488' }}>{total}</div>
                    <div style={{ fontSize: '0.82rem', color: '#475569', marginTop: 2 }}>Benefits Found</div>
                </div>
                <div style={statBox}>
                    <div style={{ fontSize: '2rem', fontWeight: 700, color: '#0d9488' }}>{pending}</div>
                    <div style={{ fontSize: '0.82rem', color: '#475569', marginTop: 2 }}>In Progress</div>
                </div>
                <div style={statBox}>
                    <div style={{ fontSize: '2rem', fontWeight: 700, color: '#0d9488' }}>{approved}</div>
                    <div style={{ fontSize: '0.82rem', color: '#475569', marginTop: 2 }}>Approved</div>
                </div>
                <div style={statBox}>
                    <div style={{ fontSize: '2rem', fontWeight: 700, color: '#0d9488' }}>
                        ${totalValue.toFixed(0)}
                    </div>
                    <div style={{ fontSize: '0.82rem', color: '#475569', marginTop: 2 }}>Total Value</div>
                </div>
            </div>

            {/* Claims list */}
            <div style={sectionStyle}>
                <div style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    marginBottom: '1rem',
                    flexWrap: 'wrap',
                    gap: '0.5rem',
                }}>
                    <h2 style={{ fontSize: '1.05rem', fontWeight: 600, color: '#0f172a' }}>
                        Claims & Detected Benefits
                    </h2>
                    <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
                        {['all', 'detected', 'under_review', 'approved', 'rejected'].map((f) => (
                            <button
                                key={f}
                                onClick={() => setFilter(f)}
                                style={{
                                    padding: '4px 12px',
                                    borderRadius: 99,
                                    border: '1px solid',
                                    borderColor: filter === f ? '#0d9488' : '#e2e8f0',
                                    background: filter === f ? '#ccfbf1' : '#fff',
                                    color: filter === f ? '#0d3d3a' : '#64748b',
                                    fontSize: '0.78rem',
                                    fontWeight: 600,
                                    cursor: 'pointer',
                                }}
                            >
                                {f === 'all' ? 'All' : f.replace('_', ' ')}
                            </button>
                        ))}
                    </div>
                </div>

                {loading ? (
                    <div style={{ color: '#94a3b8', padding: '2rem', textAlign: 'center' }}>Loading...</div>
                ) : filtered.length === 0 ? (
                    <div style={{ color: '#94a3b8', padding: '2rem', textAlign: 'center' }}>
                        No claims found. Go to{' '}
                        <a href="/simulate" style={{ color: '#0d9488' }}>Simulate Purchase</a>{' '}
                        to generate some.
                    </div>
                ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
                        {filtered.map((c) => (
                            <ClaimCard key={c.id} claim={c} />
                        ))}
                    </div>
                )}
            </div>

            {/* Cards info */}
            {cards.length > 0 && (
                <div style={sectionStyle}>
                    <h2 style={{ fontSize: '1.05rem', fontWeight: 600, marginBottom: '0.8rem', color: '#0f172a' }}>
                        Your Cards
                    </h2>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                        {cards.map((card) => (
                            <div key={card.id} style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: '1rem',
                                padding: '0.7rem 0',
                                borderBottom: '1px solid #f1f5f9',
                            }}>
                                <div style={{
                                    width: 36, height: 24,
                                    background: '#0d3d3a',
                                    borderRadius: 4,
                                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                                    color: '#2dd4bf', fontSize: '0.65rem', fontWeight: 700,
                                }}>
                                    AMEX
                                </div>
                                <div>
                                    <div style={{ fontWeight: 600, fontSize: '0.9rem' }}>{card.cardholder_name}</div>
                                    <div style={{ fontSize: '0.78rem', color: '#64748b' }}>•••• {card.last_four}</div>
                                </div>
                                <div style={{ marginLeft: 'auto' }}>
                                    <a
                                        href={`/api/cards/${card.id}/entitlements`}
                                        target="_blank"
                                        rel="noreferrer"
                                        style={{ fontSize: '0.78rem', color: '#0d9488', textDecoration: 'none' }}
                                    >
                                        View entitlements →
                                    </a>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    )
}
