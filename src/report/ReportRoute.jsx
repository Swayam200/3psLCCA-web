/**
 * /project/:projectId/report — the HTML report as its own full-page route
 * (outside the project layout so the browser can paginate it for printing).
 */
import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { projectStorageService } from '../lib/projectStorageService';
import { normalizeProjectData } from '../utils/projectSchema';
import ReportPage from './ReportPage.jsx';

const ReportRoute = () => {
    const { projectId } = useParams();
    const [state, setState] = useState({ status: 'loading', project: null });

    useEffect(() => {
        let active = true;
        // eslint-disable-next-line react-hooks/set-state-in-effect -- reset while the new project loads
        setState({ status: 'loading', project: null });
        projectStorageService.loadProject(projectId)
            .then((saved) => {
                if (!active) return;
                setState(saved
                    ? { status: 'ready', project: normalizeProjectData(saved) }
                    : { status: 'missing', project: null });
            })
            .catch(() => active && setState({ status: 'missing', project: null }));
        return () => { active = false; };
    }, [projectId]);

    if (state.status === 'loading') {
        return (
            <div className="d-flex justify-content-center align-items-center" style={{ height: '100vh' }}>
                <div className="spinner-border text-primary" role="status">
                    <span className="visually-hidden">Loading project…</span>
                </div>
            </div>
        );
    }
    if (state.status === 'missing') {
        return (
            <div className="p-5 text-center">
                <h4>Project not found</h4>
                <p>This project is not available in this browser.</p>
                <Link to="/">Back to projects</Link>
            </div>
        );
    }
    return <ReportPage projectId={projectId} projectData={state.project} />;
};

export default ReportRoute;
