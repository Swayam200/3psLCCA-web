const LCCA_API_BASE = (import.meta.env.VITE_LCCA_API_URL || 'http://localhost:8000').replace(/\/$/, '');

const requestJson = async (path, payload) => {
    const response = await fetch(`${LCCA_API_BASE}${path}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
    });

    if (!response.ok) {
        throw new Error(`Backend request failed with HTTP ${response.status}.`);
    }

    return response.json();
};

export const calculateLcca = ({ project, analysisPeriodYears, debug = false }) => {
    return requestJson('/api/lcca/calculate', {
        project,
        analysis_period_years: analysisPeriodYears,
        debug,
    });
};

export const validateLcca = ({ project, analysisPeriodYears, debug = false }) => {
    return requestJson('/api/lcca/validate', {
        project,
        analysis_period_years: analysisPeriodYears,
        debug,
    });
};

export const getLccaApiBase = () => LCCA_API_BASE;