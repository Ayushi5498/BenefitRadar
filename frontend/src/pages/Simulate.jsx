import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { simulateTransaction, getCards } from '../api/client'
import StatusBadge from '../components/StatusBadge'

const CATEGORIES = [
    'electronics', 'clothing', 'sporting_goods', 'jewelry',
    'home_appliances', 'airline', 'hotel', 'restaurant', 'grocery',
    'gas_station', 'other',
]

const labelEl = (text) => (
    <label style={{ fontSize: '0.85rem', fontWeight: 600, color: '#374151', display: 'block', marginBottom: 4 }}>
        {text}
    </label>
)

const inputStyle = {
    width: '100%', padding: '0.55rem 0.75rem',
    border: '1px solid #e2e8f0', borderRadius: 8,
    fontSize: '0.9rem', color: '#0f172a', background: '#fff', outline: 'none',
}

// ── Stage result banner ────────────────────────────────────────────────────

function StageBanner({ passed, label, detail, detail2 }) {
    return (
        <div style={{
            padding: '0.65rem 0.9rem', borderRadius: 8,
            background: passed ? '#f0fdfa' : '#fef9c3',
            color: passed ? '#0d3d3a' : '#854d0e',
            fontSize: '0.84rem', marginBottom: '0.75rem',
            borderLeft: `3px solid ${passed ? '#0d9488' : '#eab308'}`,
        }}>
            <strong>{label}</strong> {detail}
            {detail2 && <div style={{ marginTop: 4, color: '#475569' }}>{detail2}</div>}
        </div>
    )
}

export default function Simulate() {
    const navigate = useNavigate()
    const [cards, setCards] = useState([])
    const [form, setForm] = useState({
        card_id: '',
        merchant_name: '',
        merchant_category: '',
        amount_usd: '',
        travel_booking_ref: '',
        store_refused_return: false,
        flight_delay_minutes: '',
    })
    const [loading, setLoading] = useState(false)
    const [result, setResult] = useState(null)
    const [error, setError] = useState(null)

    useEffect(() => {
        getCards().then((d) => {
            setCards(d.cards || [])
            if (d.cards?.length > 0) setForm((f) => ({ ...f, card_id: d.cards[0].id }))
        })
    }, [])

    const set = (k, v) => setForm((f) => ({ ...f, [k]: v }))

    const handleSubmit = async (e) => {
        e.preventDefault()
        setLoading(true)
        setResult(null)
        setError(null)

        const payload = {}
        if (form.card_id) payload.card_id = form.card_id
        if (form.merchant_name) payload.merchant_name = form.merchant_name
        if (form.merchant_category) payload.merchant_category = form.merchant_category
        if (form.amount_usd) payload.amount_usd = parseFloat(form.amount_usd)
        if (form.travel_booking_ref) payload.travel_booking_ref = form.travel_booking_ref
        if (form.store_refused_return) payload.store_refused_return = true
        if (form.flight_delay_minutes) payload.flight_delay_minutes = parseInt(form.flight_delay_minutes)

        try {
            const res = await simulateTransaction(payload)
            setResult(res)
        } catch (e) {
            setError(e.response?.data?.detail || 'Simulation failed.')
        } finally {
            setLoading(false)
        }
    }

    const isAirline = form.merchant_category === 'airline'

    return (
        <div style={{ maxWidth: 700, margin: '0 auto' }}>
            <div style={{ marginBottom: '1.5rem' }}>
                <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: '#0d3d3a' }}>
                    Simulate a Purchase
                </h1>
                <p style={{ color: '#64748b', marginTop: 4, fontSize: '0.9rem' }}>
                    Trigger the detection pipeline live. Leave fields blank for a randomised purchase.
                </p>
            </div>

            {/* Form */}
            <form
                onSubmit={handleSubmit}
                style={{
                    background: '#fff', border: '1px solid #e2e8f0',
                    borderRadius: 14, padding: '1.5rem', marginBottom: '1.5rem',
                }}
            >
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                    <div>
                        {labelEl('Card')}
                        <select style={inputStyle} value={form.card_id} onChange={(e) => set('card_id', e.target.value)}>
                            {cards.map((c) => (
                                <option key={c.id} value={c.id}>{c.cardholder_name} (••{c.last_four})</option>
                            ))}
                        </select>
                    </div>

                    <div>
                        {labelEl('Merchant Category')}
                        <select style={inputStyle} value={form.merchant_category} onChange={(e) => set('merchant_category', e.target.value)}>
                            <option value="">Random</option>
                            {CATEGORIES.map((c) => (
                                <option key={c} value={c}>{c.replace(/_/g, ' ')}</option>
                            ))}
                        </select>
                    </div>

                    <div>
                        {labelEl('Merchant Name')}
                        <input
                            style={inputStyle}
                            placeholder="e.g. TechMart (optional)"
                            value={form.merchant_name}
                            onChange={(e) => set('merchant_name', e.target.value)}
                        />
                    </div>

                    <div>
                        {labelEl('Amount (USD)')}
                        <input
                            style={inputStyle} type="number" min="0" step="0.01"
                            placeholder="e.g. 249.99 (optional)"
                            value={form.amount_usd}
                            onChange={(e) => set('amount_usd', e.target.value)}
                        />
                    </div>

                    {isAirline && (
                        <>
                            <div>
                                {labelEl('Booking Reference')}
                                <input
                                    style={inputStyle} placeholder="e.g. BKXY99"
                                    value={form.travel_booking_ref}
                                    onChange={(e) => set('travel_booking_ref', e.target.value)}
                                />
                            </div>
                            <div>
                                {labelEl('Flight Delay (minutes)')}
                                <input
                                    style={inputStyle} type="number" min="0"
                                    placeholder="e.g. 480 for 8h delay"
                                    value={form.flight_delay_minutes}
                                    onChange={(e) => set('flight_delay_minutes', e.target.value)}
                                />
                            </div>
                        </>
                    )}

                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', paddingTop: '1.5rem' }}>
                        <input
                            type="checkbox" id="refusedReturn"
                            checked={form.store_refused_return}
                            onChange={(e) => set('store_refused_return', e.target.checked)}
                            style={{ width: 16, height: 16, accentColor: '#0d9488' }}
                        />
                        <label htmlFor="refusedReturn" style={{ fontSize: '0.88rem', color: '#374151', cursor: 'pointer' }}>
                            Store refused return
                        </label>
                    </div>
                </div>

                <button
                    type="submit"
                    disabled={loading}
                    style={{
                        marginTop: '1.25rem', width: '100%', padding: '0.85rem',
                        background: loading ? '#94a3b8' : '#0d9488', color: '#fff',
                        border: 'none', borderRadius: 10, fontSize: '1rem', fontWeight: 700,
                        cursor: loading ? 'not-allowed' : 'pointer', transition: 'background 0.2s',
                    }}
                >
                    {loading ? 'Running detection pipeline…' : '⚡ Simulate Purchase'}
                </button>
            </form>

            {error && (
                <div style={{ background: '#fee2e2', color: '#991b1b', padding: '0.75rem 1rem', borderRadius: 8, marginBottom: '1rem', fontSize: '0.88rem' }}>
                    {error}
                </div>
            )}

            {result && (
                <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 14, padding: '1.5rem' }}>
                    <h2 style={{ fontSize: '1rem', fontWeight: 700, marginBottom: '1rem', color: '#0f172a' }}>
                        Detection Pipeline Result
                    </h2>

                    {/* Transaction row */}
                    <div style={{ marginBottom: '0.85rem' }}>
                        <div style={{ fontSize: '0.78rem', fontWeight: 700, color: '#64748b', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                            Transaction
                        </div>
                        <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', fontSize: '0.88rem', color: '#0f172a', alignItems: 'center' }}>
                            <span><strong>{result.transaction?.merchant_name}</strong></span>
                            <span>${result.transaction?.amount_usd?.toFixed(2)}</span>
                            <span style={{ textTransform: 'capitalize' }}>{result.transaction?.merchant_category?.replace(/_/g, ' ')}</span>
                            <StatusBadge status={result.transaction?.status} />
                        </div>
                    </div>

                    {/* Stage 1 */}
                    <StageBanner
                        passed={result.filter_passed}
                        label="Stage 1 — Rules Filter:"
                        detail={result.filter_reason}
                    />

                    {/* Duplicate skipped banner */}
                    {result.duplicate_skipped && (
                        <div style={{
                            padding: '0.65rem 0.9rem', borderRadius: 8, background: '#fef3c7',
                            color: '#92400e', fontSize: '0.84rem', marginBottom: '0.75rem',
                            borderLeft: '3px solid #f59e0b',
                        }}>
                            <strong>⚠ Duplicate Skipped:</strong> {result.duplicate_reason}
                        </div>
                    )}

                    {/* Stage 2 */}
                    {result.filter_passed && !result.duplicate_skipped && (
                        result.match ? (
                            <StageBanner
                                passed={true}
                                label="Stage 2 — Match:"
                                detail={`${result.match.benefit_type?.replace(/_/g, ' ')} (confidence: ${(result.match.confidence_score * 100).toFixed(0)}%)`}
                                detail2={`${result.match.reason?.trigger} — ${result.match.reason?.coverage_window}`}
                            />
                        ) : (
                            <StageBanner
                                passed={false}
                                label="Stage 2 — Match:"
                                detail="No qualifying benefit found for this transaction."
                            />
                        )
                    )}

                    {/* Stage 3 + CTA */}
                    {result.claim && (
                        <>
                            <StageBanner
                                passed={true}
                                label="Stage 3 — Claim Pre-filled:"
                                detail={`$${result.claim.amount_usd?.toFixed(2)} claim drafted for ${result.claim.benefit_type}.`}
                            />
                            <button
                                onClick={() => navigate(`/claims/${result.claim.id}`)}
                                style={{
                                    width: '100%', padding: '0.75rem', background: '#0d9488', color: '#fff',
                                    border: 'none', borderRadius: 10, fontWeight: 700, cursor: 'pointer', fontSize: '0.95rem',
                                }}
                            >
                                Review &amp; Submit Claim →
                            </button>
                        </>
                    )}
                </div>
            )}
        </div>
    )
}
