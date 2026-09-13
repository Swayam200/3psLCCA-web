import 'react';
import { Modal, Button } from 'react-bootstrap';
import Logo3psLCCA from '../../assets/logo-3psLCCA.svg';

const HelpModal = ({ show, onHide, title, message }) => {
    return (
        <Modal 
            show={show} 
            onHide={onHide} 
            centered 
            contentClassName="help-info-modal"
            backdrop="static"
        >
            <style>{`
                .help-info-modal {
                    background-color: #1a1d21;
                    border: 1px solid #343a40;
                    color: #ffffff;
                    border-radius: 8px;
                    overflow: hidden;
                    box-shadow: 0 10px 25px rgba(0,0,0,0.5);
                    width: 400px;
                    margin: auto;
                }
                .help-info-modal .modal-header {
                    border-bottom: 1px solid #2d3238;
                    padding: 10px 16px;
                    display: flex;
                    align-items: center;
                    background-color: #1a1d21;
                }
                .help-info-modal .modal-title {
                    font-size: 14px;
                    font-weight: 500;
                    display: flex;
                    align-items: center;
                    color: #e9ecef;
                }
                .help-info-modal .modal-body {
                    padding: 24px;
                    background-color: #1a1d21;
                }
                .help-info-modal .modal-footer {
                    border-top: none;
                    padding: 0 16px 16px 16px;
                    background-color: #1a1d21;
                    display: flex;
                    justify-content: flex-end;
                }
                .help-info-modal .btn-ok {
                    background-color: #3b82f6;
                    border: none;
                    color: white;
                    padding: 6px 24px;
                    border-radius: 4px;
                    font-size: 14px;
                    font-weight: 500;
                    transition: background-color 0.2s;
                }
                .help-info-modal .btn-ok:hover {
                    background-color: #2563eb;
                }
                .help-info-modal .close-btn {
                    background: none;
                    border: none;
                    color: #adb5bd;
                    font-size: 20px;
                    line-height: 1;
                    cursor: pointer;
                    margin-left: auto;
                    padding: 0;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                }
                .help-info-modal .close-btn:hover {
                    color: #ffffff;
                }
                .message-text {
                    font-size: 14px;
                    line-height: 1.5;
                    color: #e9ecef;
                    font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
                }
            `}</style>
            <div className="modal-header">
                <div className="modal-title">
                    <img src={Logo3psLCCA} alt="Logo" width="20" height="20" className="me-2" />
                    {title}
                </div>
                <button className="close-btn" onClick={onHide}>&times;</button>
            </div>
            <Modal.Body>
                <div className="message-text">
                    {message}
                </div>
            </Modal.Body>
            <div className="modal-footer">
                <Button className="btn-ok" onClick={onHide}>
                    OK
                </Button>
            </div>
        </Modal>
    );
};

export default HelpModal;
