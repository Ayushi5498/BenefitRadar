import axios from 'axios'

const api = axios.create({
    baseURL: '/api',
    timeout: 10000,
})

// ── Transactions ──────────────────────────────────────────────────────────────
export const simulateTransaction = (payload = {}) =>
    api.post('/transactions/simulate', payload).then((r) => r.data)

// ── Matches ───────────────────────────────────────────────────────────────────
export const getMatches = (params = {}) =>
    api.get('/matches', { params }).then((r) => r.data)

// ── Claims ────────────────────────────────────────────────────────────────────
export const getClaims = (params = {}) =>
    api.get('/claims', { params }).then((r) => r.data)

export const getClaim = (id) =>
    api.get(`/claims/${id}`).then((r) => r.data)

export const submitClaim = (id, payload = {}) =>
    api.post(`/claims/${id}/submit`, payload).then((r) => r.data)

export const approveClaim = (id, approved = true, notes = '') =>
    api.post(`/claims/${id}/approve`, { approved, reviewer_notes: notes }).then((r) => r.data)

// ── Cards ─────────────────────────────────────────────────────────────────────
export const getCards = () =>
    api.get('/cards').then((r) => r.data)

export const getEntitlements = (cardId) =>
    api.get(`/cards/${cardId}/entitlements`).then((r) => r.data)

// ── Notifications ─────────────────────────────────────────────────────────────
export const getNotifications = (params = {}) =>
    api.get('/notifications', { params }).then((r) => r.data)

export const markNotificationRead = (id) =>
    api.post(`/notifications/${id}/read`).then((r) => r.data)

export const markAllNotificationsRead = (params = {}) =>
    api.post('/notifications/read-all', null, { params }).then((r) => r.data)

// ── Metrics ───────────────────────────────────────────────────────────────────
export const getMetricsSummary = () =>
    api.get('/metrics/summary').then((r) => r.data)
