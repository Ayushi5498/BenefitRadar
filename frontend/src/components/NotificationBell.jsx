import React, { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getNotifications, markNotificationRead, markAllNotificationsRead } from '../api/client'

export default function NotificationBell({ pollInterval = 6000 }) {
    const navigate = useNavigate()
    const [data, setData] = useState({ notifications: [], unread_count: 0 })
    const [open, setOpen] = useState(false)
    const ref = useRef(null)

    const fetchNotifications = () =>
        getNotifications({ limit: 20 })
            .then(setData)
            .catch(() => { })

    // Poll every pollInterval ms
    useEffect(() => {
        fetchNotifications()
        const id = setInterval(fetchNotifications, pollInterval)
        return () => clearInterval(id)
    }, [pollInterval])

    // Close dropdown on outside click
    useEffect(() => {
        const handler = (e) => {
            if (ref.current && !ref.current.contains(e.target)) setOpen(false)
        }
        document.addEventListener('mousedown', handler)
        return () => document.removeEventListener('mousedown', handler)
    }, [])

    const handleClick = async (notif) => {
        if (!notif.read) {
            await markNotificationRead(notif.id)
            fetchNotifications()
        }
        setOpen(false)
        navigate(`/claims/${notif.claim_id}`)
    }

    const handleMarkAllRead = async (e) => {
        e.stopPropagation()
        await markAllNotificationsRead()
        fetchNotifications()
    }

    const unread = data.unread_count || 0

    return (
        <div ref={ref} style={{ position: 'relative' }}>
            {/* Bell button */}
            <button
                onClick={() => setOpen((o) => !o)}
                aria-label={`Notifications${unread > 0 ? `, ${unread} unread` : ''}`}
                style={{
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    position: 'relative',
                    padding: '4px 6px',
                    display: 'flex',
                    alignItems: 'center',
                    color: open ? '#2dd4bf' : '#94a3b8',
                    transition: 'color 0.15s',
                }}
            >
                {/* Bell SVG */}
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
                    <path d="M13.73 21a2 2 0 0 1-3.46 0" />
                </svg>
                {/* Badge */}
                {unread > 0 && (
                    <span style={{
                        position: 'absolute',
                        top: 0,
                        right: 0,
                        background: '#ef4444',
                        color: '#fff',
                        borderRadius: 99,
                        fontSize: '0.6rem',
                        fontWeight: 700,
                        minWidth: 16,
                        height: 16,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        padding: '0 3px',
                        lineHeight: 1,
                    }}>
                        {unread > 9 ? '9+' : unread}
                    </span>
                )}
            </button>

            {/* Dropdown */}
            {open && (
                <div style={{
                    position: 'absolute',
                    right: 0,
                    top: 'calc(100% + 8px)',
                    width: 320,
                    background: '#fff',
                    border: '1px solid #e2e8f0',
                    borderRadius: 12,
                    boxShadow: '0 8px 24px rgba(0,0,0,0.12)',
                    zIndex: 1000,
                    overflow: 'hidden',
                }}>
                    {/* Header */}
                    <div style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        padding: '0.75rem 1rem',
                        borderBottom: '1px solid #f1f5f9',
                    }}>
                        <span style={{ fontWeight: 700, fontSize: '0.9rem', color: '#0f172a' }}>
                            Notifications {unread > 0 && <span style={{ color: '#0d9488' }}>({unread} new)</span>}
                        </span>
                        {unread > 0 && (
                            <button
                                onClick={handleMarkAllRead}
                                style={{
                                    background: 'none',
                                    border: 'none',
                                    color: '#0d9488',
                                    fontSize: '0.75rem',
                                    cursor: 'pointer',
                                    fontWeight: 600,
                                    padding: 0,
                                }}
                            >
                                Mark all read
                            </button>
                        )}
                    </div>

                    {/* List */}
                    <div style={{ maxHeight: 340, overflowY: 'auto' }}>
                        {data.notifications.length === 0 ? (
                            <div style={{ padding: '1.5rem', textAlign: 'center', color: '#94a3b8', fontSize: '0.85rem' }}>
                                No notifications yet
                            </div>
                        ) : (
                            data.notifications.map((n) => (
                                <div
                                    key={n.id}
                                    onClick={() => handleClick(n)}
                                    style={{
                                        padding: '0.75rem 1rem',
                                        borderBottom: '1px solid #f8fafc',
                                        cursor: 'pointer',
                                        background: n.read ? '#fff' : '#f0fdfa',
                                        display: 'flex',
                                        gap: '0.6rem',
                                        alignItems: 'flex-start',
                                        transition: 'background 0.1s',
                                    }}
                                    onMouseEnter={(e) => (e.currentTarget.style.background = '#f0fdfa')}
                                    onMouseLeave={(e) => (e.currentTarget.style.background = n.read ? '#fff' : '#f0fdfa')}
                                >
                                    {/* Unread dot */}
                                    <span style={{
                                        width: 8,
                                        height: 8,
                                        borderRadius: '50%',
                                        background: n.read ? 'transparent' : '#0d9488',
                                        flexShrink: 0,
                                        marginTop: 5,
                                    }} />
                                    <div style={{ flex: 1, minWidth: 0 }}>
                                        <p style={{
                                            margin: 0,
                                            fontSize: '0.83rem',
                                            color: '#0f172a',
                                            fontWeight: n.read ? 400 : 600,
                                            lineHeight: 1.4,
                                        }}>
                                            {n.message}
                                        </p>
                                        <p style={{ margin: '3px 0 0', fontSize: '0.72rem', color: '#94a3b8' }}>
                                            {new Date(n.created_at).toLocaleString()}
                                        </p>
                                    </div>
                                </div>
                            ))
                        )}
                    </div>
                </div>
            )}
        </div>
    )
}
