import React from 'react'
import { Routes, Route, NavLink } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import ClaimDetail from './pages/ClaimDetail'
import Simulate from './pages/Simulate'
import Metrics from './pages/Metrics'
import NotificationBell from './components/NotificationBell'

const styles = {
    nav: {
        background: '#0d3d3a',
        padding: '0 2rem',
        display: 'flex',
        alignItems: 'center',
        gap: '2rem',
        height: 60,
    },
    brand: {
        color: '#2dd4bf',
        fontWeight: 700,
        fontSize: '1.25rem',
        textDecoration: 'none',
        letterSpacing: '-0.5px',
    },
    link: {
        color: '#94a3b8',
        textDecoration: 'none',
        fontSize: '0.9rem',
        fontWeight: 500,
        padding: '4px 0',
        borderBottom: '2px solid transparent',
        transition: 'color 0.2s, border-color 0.2s',
    },
    activeLink: {
        color: '#2dd4bf',
        borderBottom: '2px solid #2dd4bf',
    },
    main: {
        maxWidth: 1100,
        margin: '0 auto',
        padding: '2rem 1.5rem',
    },
}

export default function App() {
    return (
        <>
            <nav style={styles.nav}>
                <NavLink to="/" style={styles.brand}>BenefitRadar</NavLink>
                <NavLink
                    to="/"
                    end
                    style={({ isActive }) => ({ ...styles.link, ...(isActive ? styles.activeLink : {}) })}
                >
                    Dashboard
                </NavLink>
                <NavLink
                    to="/simulate"
                    style={({ isActive }) => ({ ...styles.link, ...(isActive ? styles.activeLink : {}) })}
                >
                    Simulate Purchase
                </NavLink>
                <NavLink
                    to="/metrics"
                    style={({ isActive }) => ({ ...styles.link, ...(isActive ? styles.activeLink : {}) })}
                >
                    Metrics
                </NavLink>
                {/* Bell pushed to the far right */}
                <div style={{ marginLeft: 'auto' }}>
                    <NotificationBell pollInterval={6000} />
                </div>
            </nav>
            <main style={styles.main}>
                <Routes>
                    <Route path="/" element={<Dashboard />} />
                    <Route path="/claims/:id" element={<ClaimDetail />} />
                    <Route path="/simulate" element={<Simulate />} />
                    <Route path="/metrics" element={<Metrics />} />
                </Routes>
            </main>
        </>
    )
}
