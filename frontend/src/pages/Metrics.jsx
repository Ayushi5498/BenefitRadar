import React, { useEffect, useState } from 'react'
import {
    BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from 'recharts'
import { getMetricsSummary } from '../api/client'

// ── helpers ─────────────────────────────────────────────────────────────────

function StatCard({ label, value, sub, accent = false }) {
    return (
        <div style={{
            background: '#fff',
            border: `1px solid ${accent ? '#99f6e4' : '#e2e8f0'}`,
            borderRadius: 12,
            padding: '1.25rem 1.5rem',
            flex: '1 1 160px',
            minWidth: 150,
        }}>
            <div style={{
                fontSize: '2rem',
                fontWeight: 700,
                color: accent ? '#0d9488' : '#0f172a',
                lineHeight: 1,
            }}>
                {value}
            </div>
            <div style={{ fontSize: '0.83rem', color: '#64748b', marginTop: 6, fontWeight: 500 }}>
                {label}
            </div>
            {sub && (
                <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: 3 }}>
                    {sub}
                </div>
            )}
        </div>
    )
}

const BENEFIT_COLORS = {
    'Purchase Protection': '#0d9488',
    'Return Protection': '#6366f1',
    'Travel Delay Insurance': '#f59e0b',
}

const BENEFIT_LABELS = {
    purchase_protection: 'Purchase Protection',
    return_protection: 'Return Protection',
    travel_delay: 'Travel Delay Insurance',
}

// Custom tooltip for the bar chart
function CustomTooltip({ active, payload, label }) {
    if (!active || !payload?.length) return null
    return (
        <div style={{
            background: '#fff',
            border: '1px solid #e2e8f0',
            borderRadius: 8,
            padding: '0.6rem 0.9rem',
            fontSize: '0.83rem',
            boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
        }}>
            <strong>{label}</strong>: {payload[0].value}
        </div>
    )
}

// ── component ────────────────────────────────────────────────────────────────

export default function Metrics() {
    const [data, setData] = useState(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)

    const load = () =>
        getMetricsSummary()
            .then(setData)
            .catch(() => setError('Could not load metrics.'))
            .finally(() => setLoading(false))

    useEffect(() => {
        load()
        const id = setInterval(load, 7000)   // refresh with dashboard polling
        return () => clearInterval(id)
    }, [])

    if (loading) return (
        <div style={{ textAlign: 'center', color: '#94a3b8', padding: '4rem' }}>Loading metrics…</div>
    )
    if (error) return (
        <div style={{ textAlign: 'center', color: '#ef4444', padding: '4rem' }}>{error}</div>
    )

    // ── derive bar chart data from benefit breakdown ──────────────────
    const benefitData = Object.entries(data.claims_by_benefit || {}).map(([k, v]) => ({
        name: BENEFIT_LABELS[k] || k,
        count: v,
    }))

    // ── pipeline funnel data ──────────────────────────────────────────
    const funnelData = [
        { name: 'Ingested', count: data.total_transactions },
        { name: 'Matched', count: data.total_matches },
        { name: 'Submitted', count: data.submitted_claims },
        { name: 'Approved', count: data.approved_claims },
    ]

    const section = (title, children) => (
        <div style={{
            background: '#fff',
            border: '1px solid #e2e8f0',
            borderRadius: 14,
            padding: '1.4rem 1.5rem',
            marginBottom: '1.25rem',
        }}>
            <h2 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#0f172a', marginBottom: '1rem' }}>
                {title}
            </h2>
            {children}
        </div>
    )

    return (
        <div style={{ maxWidth: 960, margin: '0 auto' }}>
            {/* Header */}
            <div style={{ marginBottom: '1.5rem' }}>
                <h1 style={{ fontSize: '1.6rem', fontWeight: 700, color: '#0d3d3a' }}>
                    Pipeline Metrics
                </h1>
                <p style={{ color: '#64748b', marginTop: 4, fontSize: '0.9rem' }}>
                    Live numbers from the detection pipeline — refreshes every 7 seconds.
                </p>
            </div>

            {/* ── Top stat cards ── */}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '1rem', marginBottom: '1.25rem' }}>
                <StatCard
                    label="Transactions Ingested"
                    value={data.total_transactions}
                    accent
                />
                <StatCard
                    label="Stage 1 Pass Rate"
                    value={`${data.filter_pass_rate_pct}%`}
                    sub="Passed rules filter"
                    accent
                />
                <StatCard
                    label="Stage 2 Match Rate"
                    value={`${data.match_rate_pct}%`}
                    sub="Became a benefit match"
                    accent
                />
                <StatCard
                    label="Pre-fill Accuracy"
                    value={`${data.prefill_accuracy_pct}%`}
                    sub="Submitted without editing"
                />
                <StatCard
                    label="Utilization Rate"
                    value={`${data.utilization_rate_pct}%`}
                    sub="Matches → approved claims"
                />
            </div>

            {/* ── Claim counts row ── */}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '1rem', marginBottom: '1.25rem' }}>
                <StatCard label="Total Matches Detected" value={data.total_matches} />
                <StatCard label="Claims Submitted" value={data.submitted_claims} />
                <StatCard label="Claims Approved" value={data.approved_claims} />
                <StatCard label="Claims Rejected" value={data.rejected_claims} />
            </div>

            {/* ── Pipeline funnel chart ── */}
            {section('Detection Pipeline Funnel', (
                <ResponsiveContainer width="100%" height={220}>
                    <BarChart data={funnelData} barSize={48}>
                        <XAxis
                            dataKey="name"
                            tick={{ fontSize: 12, fill: '#64748b' }}
                            axisLine={false}
                            tickLine={false}
                        />
                        <YAxis
                            tick={{ fontSize: 11, fill: '#94a3b8' }}
                            axisLine={false}
                            tickLine={false}
                            allowDecimals={false}
                        />
                        <Tooltip content={<CustomTooltip />} cursor={{ fill: '#f0fdfa' }} />
                        <Bar dataKey="count" radius={[6, 6, 0, 0]}>
                            {funnelData.map((_, i) => (
                                <Cell
                                    key={i}
                                    fill={['#0d9488', '#14b8a6', '#5eead4', '#99f6e4'][i]}
                                />
                            ))}
                        </Bar>
                    </BarChart>
                </ResponsiveContainer>
            ))}

            {/* ── Benefit breakdown chart ── */}
            {benefitData.length > 0 && section('Claims by Benefit Type', (
                <ResponsiveContainer width="100%" height={200}>
                    <BarChart data={benefitData} barSize={52}>
                        <XAxis
                            dataKey="name"
                            tick={{ fontSize: 11, fill: '#64748b' }}
                            axisLine={false}
                            tickLine={false}
                        />
                        <YAxis
                            tick={{ fontSize: 11, fill: '#94a3b8' }}
                            axisLine={false}
                            tickLine={false}
                            allowDecimals={false}
                        />
                        <Tooltip content={<CustomTooltip />} cursor={{ fill: '#f0fdfa' }} />
                        <Bar dataKey="count" radius={[6, 6, 0, 0]}>
                            {benefitData.map((entry, i) => (
                                <Cell
                                    key={i}
                                    fill={BENEFIT_COLORS[entry.name] || '#0d9488'}
                                />
                            ))}
                        </Bar>
                    </BarChart>
                </ResponsiveContainer>
            ))}

            {/* ── Target comparison ── */}
            {section('PDF Target vs. Actual', (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                    {[
                        { label: 'Spotting right purchases (match rate)', target: 90, actual: data.filter_pass_rate_pct },
                        { label: 'Getting the form right (pre-fill accuracy)', target: 85, actual: data.prefill_accuracy_pct },
                        { label: 'More benefits actually used (utilization)', target: 35, actual: data.utilization_rate_pct },
                    ].map(({ label, target, actual }) => (
                        <div key={label}>
                            <div style={{
                                display: 'flex',
                                justifyContent: 'space-between',
                                fontSize: '0.83rem',
                                marginBottom: 4,
                                color: '#475569',
                            }}>
                                <span>{label}</span>
                                <span style={{ fontWeight: 600, color: actual >= target ? '#0d9488' : '#f59e0b' }}>
                                    {actual}% <span style={{ color: '#94a3b8', fontWeight: 400 }}>/ {target}% target</span>
                                </span>
                            </div>
                            <div style={{ height: 8, background: '#f1f5f9', borderRadius: 99, overflow: 'hidden' }}>
                                <div style={{
                                    height: '100%',
                                    width: `${Math.min(actual, 100)}%`,
                                    background: actual >= target ? '#0d9488' : '#f59e0b',
                                    borderRadius: 99,
                                    transition: 'width 0.4s ease',
                                }} />
                            </div>
                        </div>
                    ))}
                </div>
            ))}
        </div>
    )
}
