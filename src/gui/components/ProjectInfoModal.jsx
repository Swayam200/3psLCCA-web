import 'react';
import { Modal, Button } from 'react-bootstrap';
import { FaInfoCircle, FaCalendarAlt, FaGlobe, FaCoins, FaRulerCombined } from 'react-icons/fa';
import Logo3psLCCA from '../../assets/logo-3psLCCA.svg';

const ProjectInfoModal = ({ show, onHide, projectData }) => {
    if (!projectData) return null;

    const gi = projectData.general_info || {};
    const details = [
        { label: 'Project Name', value: projectData.name || gi.project_name || 'N/A', icon: FaInfoCircle },
        { label: 'Created At', value: projectData.createdAt || 'N/A', icon: FaCalendarAlt },
        { label: 'Country', value: projectData.country || gi.project_country || 'N/A', icon: FaGlobe },
        { label: 'Currency', value: projectData.currency || gi.project_currency || 'N/A', icon: FaCoins },
        { label: 'Unit System', value: projectData.unitSystem || gi.unit_system || 'N/A', icon: FaRulerCombined },
    ];

    return (
        <Modal 
            show={show} 
            onHide={onHide} 
            centered 
            contentClassName="project-info-modal"
            backdrop="static"
        >
            <style>{`
                .project-info-modal {
                    background-color: #1a1d21;
                    border: 1px solid #343a40;
                    color: #ffffff;
                    border-radius: 8px;
                    overflow: hidden;
                    box-shadow: 0 10px 25px rgba(0,0,0,0.5);
                    width: 450px;
                    margin: auto;
                }
                .project-info-modal .modal-header {
                    border-bottom: 1px solid #2d3238;
                    padding: 10px 16px;
                    display: flex;
                    align-items: center;
                    background-color: #1a1d21;
                }
                .project-info-modal .modal-title {
                    font-size: 14px;
                    font-weight: 600;
                    display: flex;
                    align-items: center;
                    color: #e9ecef;
                }
                .project-info-modal .modal-body {
                    padding: 20px 24px;
                    background-color: #1a1d21;
                }
                .project-info-modal .modal-footer {
                    border-top: 1px solid #2d3238;
                    padding: 12px 16px;
                    background-color: #1a1d21;
                    display: flex;
                    justify-content: flex-end;
                }
                .project-info-modal .btn-ok {
                    background-color: #9adc32;
                    border: none;
                    color: #000;
                    padding: 6px 24px;
                    border-radius: 4px;
                    font-size: 14px;
                    font-weight: 600;
                    transition: opacity 0.2s;
                }
                .project-info-modal .btn-ok:hover {
                    opacity: 0.9;
                }
                .project-info-modal .close-btn {
                    background: none;
                    border: none;
                    color: #adb5bd;
                    font-size: 20px;
                    line-height: 1;
                    cursor: pointer;
                    margin-left: auto;
                    display: flex;
                    align-items: center;
                }
                .project-info-modal .close-btn:hover {
                    color: #ffffff;
                }
                .info-item {
                    display: flex;
                    align-items: center;
                    padding: 12px 0;
                    border-bottom: 1px solid #2d3238;
                }
                .info-item:last-child {
                    border-bottom: none;
                }
                .info-icon-box {
                    width: 32px;
                    height: 32px;
                    background-color: rgba(154, 220, 50, 0.1);
                    border-radius: 6px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    margin-right: 16px;
                    color: #9adc32;
                }
                .info-content {
                    flex-grow: 1;
                }
                .info-label {
                    font-size: 11px;
                    color: #adb5bd;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                    margin-bottom: 2px;
                }
                .info-value {
                    font-size: 14px;
                    color: #ffffff;
                    font-weight: 500;
                }
            `}</style>
            <div className="modal-header">
                <div className="modal-title">
                    <img src={Logo3psLCCA} alt="Logo" width="20" height="20" className="me-2" />
                    Project Details
                </div>
                <button className="close-btn" onClick={onHide}>&times;</button>
            </div>
            <Modal.Body>
                {details.map((detail, idx) => (
                    <div key={idx} className="info-item">
                        <div className="info-icon-box">
                            <detail.icon size={16} />
                        </div>
                        <div className="info-content">
                            <div className="info-label">{detail.label}</div>
                            <div className="info-value">{detail.value}</div>
                        </div>
                    </div>
                ))}
            </Modal.Body>
            <div className="modal-footer">
                <Button className="btn-ok" onClick={onHide}>
                    Close
                </Button>
            </div>
        </Modal>
    );
};

export default ProjectInfoModal;
