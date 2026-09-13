
import { Button } from 'react-bootstrap';

const Logs = ({ logs = [], onClearLogs }) => {

    const handleClear = () => {
        if (onClearLogs) onClearLogs();
    };

    return (
        <div className="d-flex flex-column h-100" style={{ 
            padding: '20px', 
            backgroundColor: 'var(--app-bg-main)',
            color: 'var(--app-text-primary)',
            fontFamily: '"Segoe UI", system-ui, sans-serif'
        }}>
            <div className="d-flex justify-content-between align-items-center" style={{ marginBottom: '15px' }}>
                <h5 style={{ margin: 0, fontWeight: 500 }}>Engine Logs</h5>
                
                <div className="d-flex align-items-center" style={{ gap: '15px' }}>
                    <div className="d-flex" style={{ gap: '10px', fontSize: '13px', color: 'var(--app-text-secondary)' }}>
                        <span>Chunks: <span style={{ color: 'var(--app-text-primary)' }}>15</span></span>
                        <span style={{ color: 'var(--app-border-mid)' }}>|</span>
                        <span>Pending: <span style={{ color: 'var(--app-text-primary)' }}>0</span></span>
                    </div>
                    
                    <Button 
                        variant="outline-secondary" 
                        size="sm" 
                        onClick={handleClear}
                        style={{ 
                            fontSize: '12px', 
                            padding: '2px 10px',
                            borderColor: 'var(--app-border-mid)',
                            color: 'var(--app-text-secondary)',
                            backgroundColor: 'var(--app-bg-card)'
                        }}
                    >
                        Clear
                    </Button>
                </div>
            </div>

            <div className="flex-grow-1 overflow-y-auto" style={{ 
                backgroundColor: 'var(--app-bg-alt)', 
                borderRadius: '6px',
                border: '1px solid var(--app-border-light)',
                padding: '15px',
                fontFamily: 'monospace',
                fontSize: '13px',
                lineHeight: '1.6',
                boxShadow: 'inset 0 2px 4px rgba(0,0,0,0.2)'
            }}>
                {logs.length === 0 ? (
                    <div className="text-center" style={{ color: 'var(--app-text-muted)', marginTop: '20px' }}>
                        No logs to display
                    </div>
                ) : (
                    logs.map((log, index) => (
                        <div key={index} style={{ marginBottom: '4px', wordBreak: 'break-all' }}>
                            <span style={{ color: 'var(--app-text-muted)', marginRight: '8px' }}>
                                {log.substring(0, 10)}
                            </span>
                            <span style={{ color: 'var(--app-text-secondary)' }}>
                                {log.substring(10)}
                            </span>
                        </div>
                    ))
                ).reverse()}
            </div>
        </div>
    );
};

export default Logs;
