/* eslint-disable no-unused-vars */
import React, { useState, useEffect } from 'react';
import { Form, Button, Container, Row, Col, Modal, Alert, Spinner } from 'react-bootstrap';
import { BsStars, BsGoogle } from 'react-icons/bs';
import Logo3psLCCA from '../../assets/logo-3psLCCA.svg';

const Loginpage = ({ onLogin, onGuestLogin, onGoogleLogin }) => {
    const [isSignup, setIsSignup] = useState(false);
    const [name, setName] = useState('');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [rememberMe, setRememberMe] = useState(false);
    const [validated, setValidated] = useState(false);
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);

    // Guest Prompt State
    const [showGuestPrompt, setShowGuestPrompt] = useState(false);
    const [guestNameInput, setGuestNameInput] = useState('');

    // Typewriter effect state
    const [welcomeText, setWelcomeText] = useState('');
    const fullText = "welcome to 3psLCCA app";

    useEffect(() => {
        let index = 0;
        let timer;
        setWelcomeText('');

        // Start typing after a delay of 1.8 seconds (matching logo entrance completion)
        const delayTimeout = setTimeout(() => {
            timer = setInterval(() => {
                if (index < fullText.length) {
                    const nextChar = fullText.charAt(index);
                    setWelcomeText((prev) => prev + nextChar);
                    index++;
                } else {
                    clearInterval(timer);
                }
            }, 80);
        }, 1800);

        return () => {
            clearTimeout(delayTimeout);
            if (timer) clearInterval(timer);
        };
    }, []);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setValidated(true);
        setError('');
        
        if (!email || !password || (isSignup && !name)) return;

        setLoading(true);
        try {
            if (onLogin) {
                await onLogin({ 
                    email, 
                    password, 
                    name: isSignup ? name : undefined, 
                    action: isSignup ? 'signup' : 'login' 
                });
            }
        } catch (err) {
            setError(err.message || 'An error occurred during authentication.');
        } finally {
            setLoading(false);
        }
    };

    const handleGuestSubmit = (e) => {
        e.preventDefault();
        const name = guestNameInput.trim() || 'Guest';
        setShowGuestPrompt(false);
        if (onGuestLogin) onGuestLogin(name);
    };

    return (
        <Container fluid className="p-0 m-0 min-vh-100 d-flex flex-column">
            <style>{`

                @keyframes logo-fly-in {
                    0% {
                        opacity: 0;
                        transform: translateX(-100vw) rotate(-540deg) scale(0.3);
                        filter: blur(8px);
                    }
                    60% {
                        transform: translateX(8%) rotate(25deg) scale(1.1);
                        filter: blur(0);
                    }
                    80% {
                        transform: translateX(-3%) rotate(-10deg) scale(0.95);
                    }
                    100% {
                        opacity: 1;
                        transform: translateX(0) rotate(0deg) scale(1);
                    }
                }

                @keyframes logo-float {
                    0%, 100% {
                        transform: translateY(0);
                    }
                    50% {
                        transform: translateY(-8px);
                    }
                }

                @keyframes logo-periodic-rotate {
                    0%, 75% {
                        transform: rotate(0deg);
                    }
                    85%, 100% {
                        transform: rotate(360deg);
                    }
                }

                @keyframes caret-blink {
                    0%, 100% { opacity: 1; }
                    50% { opacity: 0; }
                }

                .premium-logo-container {
                    position: relative;
                    animation: logo-fly-in 1.8s cubic-bezier(0.25, 1, 0.5, 1) forwards;
                }

                .premium-logo-floater {
                    animation: logo-float 4s ease-in-out infinite;
                    animation-delay: 1.8s;
                }

                .premium-logo-rotator {
                    animation: logo-periodic-rotate 10s cubic-bezier(0.68, -0.6, 0.32, 1.6) infinite;
                    animation-delay: 1.8s;
                    transition: all 0.5s cubic-bezier(0.34, 1.56, 0.64, 1);
                    cursor: pointer;
                }

                .premium-logo-rotator:hover {
                    transform: scale(1.15) rotate(15deg);
                    filter: drop-shadow(0 15px 30px rgba(0,0,0,0.25)) drop-shadow(0 0 15px var(--app-primary-accent)) !important;
                }

                .logo-bg-glow {
                    position: absolute;
                    border-radius: 50%;
                    background: radial-gradient(circle, rgba(115, 165, 175, 0.15) 0%, rgba(115, 165, 175, 0) 70%);
                    z-index: -1;
                    animation: logo-float 4s ease-in-out infinite alternate;
                    animation-delay: 1.8s;
                }

                .typewriter-cursor {
                    animation: caret-blink 0.8s infinite;
                    color: var(--app-primary-accent);
                    margin-left: 4px;
                    font-weight: 200;
                }
            `}</style>
            <Row className="g-0 m-0 w-100 flex-grow-1" style={{ backgroundColor: 'var(--app-bg-main)', transition: 'background-color 0.3s ease' }}>

                {/* Left Side: Minimal Background */}
                <Col md={6} className="d-flex flex-column p-3 p-md-4 pb-5 pb-md-4">

                    {/* Top Logo */}
                    <div className="d-flex align-items-center mb-4" style={{ fontWeight: 'bold', fontSize: '1.2rem', color: 'var(--app-text-primary)' }}>
                        <img src={Logo3psLCCA} alt="3psLCCA Logo" width="24" height="24" className="me-2" style={{ objectFit: 'contain' }} /> 3psLCCA
                    </div>

                    {/* Middle Text */}
                    <div className="d-flex flex-column justify-content-center align-items-center text-center flex-grow-1" style={{ paddingBottom: '5vh' }}>
                        <div className="premium-logo-container mb-4 d-flex justify-content-center align-items-center">
                            <div className="logo-bg-glow" style={{ width: 'clamp(110px, 18vw, 160px)', height: 'clamp(110px, 18vw, 160px)' }}></div>
                            <div className="premium-logo-floater">
                                <img
                                    src={Logo3psLCCA}
                                    alt="3psLCCA Logo"
                                    className="premium-logo-rotator"
                                    style={{ width: 'clamp(90px, 15vw, 130px)', height: 'clamp(90px, 15vw, 130px)', filter: 'drop-shadow(0 8px 16px rgba(0,0,0,0.15))' }}
                                />
                            </div>
                        </div>
                        <h1 className="fw-bold mb-2" style={{ fontSize: 'clamp(1.8rem, 4vw, 2.8rem)', letterSpacing: '-0.5px', color: 'var(--app-text-primary)', transition: 'color 0.3s ease', minHeight: 'clamp(2.4rem, 5vw, 3.6rem)' }}>
                            {welcomeText}
                            <span className="typewriter-cursor">|</span>
                        </h1>
                        <p className="px-3 mb-0" style={{ fontSize: '1.1rem', lineHeight: '1.6', maxWidth: '90%', color: 'var(--app-text-secondary)', transition: 'color 0.3s ease' }}>
                            Your comprehensive platform for Life Cycle Cost Analysis.<br />
                            Plan efficiently, track expenses, and gain actionable insights for all your projects.
                        </p>
                    </div>
                </Col>

                {/* Right Side: Form Container */}
                <Col md={6} className="d-flex flex-column justify-content-center p-3 p-md-4 border-start" style={{ backgroundColor: 'var(--app-bg-card)', borderColor: 'var(--app-border-light)', transition: 'background-color 0.3s ease, border-color 0.3s ease' }}>
                    <div className="w-100 mx-auto p-3 p-md-4 rounded shadow border" style={{ maxWidth: '520px', backgroundColor: 'var(--app-bg-card)', borderColor: 'var(--app-border-light)', transition: 'background-color 0.3s ease, border-color 0.3s ease' }}>

                        <div className="mb-3 text-center">
                            <h1 className="fw-bold mb-1" style={{ color: 'var(--app-text-primary)', fontSize: '2rem', transition: 'color 0.3s ease' }}>{isSignup ? 'Signup' : 'Login'}</h1>
                            <p className="mb-0" style={{ fontSize: '0.85rem', lineHeight: '1.3', color: 'var(--app-text-secondary)', transition: 'color 0.3s ease' }}>
                                {isSignup ? 'Create a new account to manage your projects.' : 'Welcome! Login to manage your projects, resources, and access comprehensive analysis tools.'}
                            </p>
                        </div>

                        <div className="mx-auto" style={{ maxWidth: '380px' }}>
                            {error && <Alert variant="danger" className="py-2" style={{ fontSize: '0.85rem' }}>{error}</Alert>}
                            <Form onSubmit={handleSubmit} noValidate>
                                {isSignup && (
                                    <Form.Group className="mb-2">
                                        <Form.Label className="fw-bold mb-1" style={{ fontSize: '0.75rem', color: 'var(--app-text-secondary)', transition: 'color 0.3s ease' }}>NAME</Form.Label>
                                        <Form.Control
                                            type="text"
                                            value={name}
                                            onChange={(e) => setName(e.target.value)}
                                            style={{ fontSize: '0.85rem', padding: '0.35rem 0.6rem', borderRadius: '4px', backgroundColor: 'var(--app-input-bg)', color: 'var(--app-input-text)', borderColor: 'var(--app-input-border)', transition: 'all 0.3s ease' }}
                                            isInvalid={validated && !name}
                                        />
                                        <Form.Control.Feedback type="invalid" style={{ fontSize: '0.7rem' }}>
                                            Name is required for signup.
                                        </Form.Control.Feedback>
                                    </Form.Group>
                                )}
                                <Form.Group className="mb-2">
                                    <Form.Label className="fw-bold mb-1" style={{ fontSize: '0.75rem', color: 'var(--app-text-secondary)', transition: 'color 0.3s ease' }}>EMAIL</Form.Label>
                                    <Form.Control
                                        type="email"
                                        value={email}
                                        onChange={(e) => setEmail(e.target.value)}
                                        style={{ fontSize: '0.85rem', padding: '0.35rem 0.6rem', borderRadius: '4px', backgroundColor: 'var(--app-input-bg)', color: 'var(--app-input-text)', borderColor: 'var(--app-input-border)', transition: 'all 0.3s ease' }}
                                        isInvalid={validated && !email}
                                    />
                                    <Form.Control.Feedback type="invalid" style={{ fontSize: '0.7rem' }}>
                                        Email is required.
                                    </Form.Control.Feedback>
                                </Form.Group>

                                <Form.Group className="mb-2">
                                    <Form.Label className="fw-bold mb-1" style={{ fontSize: '0.75rem', color: 'var(--app-text-secondary)', transition: 'color 0.3s ease' }}>PASSWORD</Form.Label>
                                    <Form.Control
                                        type="password"
                                        value={password}
                                        onChange={(e) => setPassword(e.target.value)}
                                        style={{ fontSize: '0.85rem', padding: '0.35rem 0.6rem', borderRadius: '4px', backgroundColor: 'var(--app-input-bg)', color: 'var(--app-input-text)', borderColor: 'var(--app-input-border)', transition: 'all 0.3s ease' }}
                                        isInvalid={validated && !password}
                                    />
                                    <Form.Control.Feedback type="invalid" style={{ fontSize: '0.7rem' }}>
                                        Password is required.
                                    </Form.Control.Feedback>
                                </Form.Group>

                                <Form.Group className="mb-3">
                                    <Form.Check
                                        type="checkbox"
                                        label="Remember me"
                                        checked={rememberMe}
                                        onChange={(e) => setRememberMe(e.target.checked)}
                                        style={{ fontSize: '0.8rem', color: 'var(--app-text-secondary)', transition: 'color 0.3s ease' }}
                                        className="d-flex align-items-center gap-2 m-0"
                                    />
                                </Form.Group>

                                <Button
                                    type="submit"
                                    disabled={loading}
                                    className="w-100 py-2 fw-bold mb-3 border-0 d-flex justify-content-center align-items-center"
                                    style={{ backgroundColor: 'var(--app-primary-accent)', color: 'var(--app-bg-main)', fontSize: '0.9rem', letterSpacing: '0.5px', borderRadius: '4px' }}
                                >
                                    {loading ? <Spinner animation="border" size="sm" /> : (isSignup ? 'SIGNUP' : 'LOGIN')}
                                </Button>
                                
                                <div className="d-flex align-items-center mb-3">
                                    <hr className="flex-grow-1" style={{ borderColor: 'var(--app-border-light)' }} />
                                    <span className="px-2 text-muted" style={{ fontSize: '0.8rem' }}>OR</span>
                                    <hr className="flex-grow-1" style={{ borderColor: 'var(--app-border-light)' }} />
                                </div>
                                
                                <Button
                                    variant="light"
                                    onClick={onGoogleLogin}
                                    className="w-100 py-2 fw-bold mb-3 d-flex justify-content-center align-items-center gap-2"
                                    style={{ backgroundColor: '#ffffff', color: '#757575', border: '1px solid #ddd', fontSize: '0.9rem', borderRadius: '4px', boxShadow: '0 1px 3px rgba(0,0,0,0.08)' }}
                                >
                                    <BsGoogle style={{ color: '#DB4437', fontSize: '1.1rem' }} />
                                    Continue with Google
                                </Button>
                            </Form>

                            <div className="d-flex justify-content-between align-items-center mt-2" style={{ fontSize: '0.8rem' }}>
                                <span style={{ color: 'var(--app-text-secondary)', transition: 'color 0.3s ease' }}>
                                    {isSignup ? 'Already have an account? ' : 'New User? '}
                                    <span 
                                        onClick={() => { setIsSignup(!isSignup); setError(''); setValidated(false); }}
                                        style={{ color: 'var(--app-primary-accent)', fontWeight: 'bold', cursor: 'pointer', textDecoration: 'none', transition: 'color 0.3s ease' }}
                                    >
                                        {isSignup ? 'Login' : 'Signup'}
                                    </span>
                                </span>
                                {!isSignup && (
                                    <span style={{ color: 'var(--app-text-secondary)', cursor: 'pointer', fontStyle: 'italic', transition: 'color 0.3s ease' }}>
                                        Forgot your password?
                                    </span>
                                )}
                            </div>
                        </div>

                        {/* Guest Login Option */}
                        <div className="mt-3 pt-2 border-top text-center mx-auto" style={{ maxWidth: '380px', borderColor: 'var(--app-border-light) !important' }}>
                            <Button
                                variant="light"
                                className="w-100 py-1 d-flex justify-content-center align-items-center m-0"
                                style={{ color: 'var(--app-text-primary)', border: '1px solid var(--app-border-mid)', borderRadius: '4px', fontSize: '0.85rem', backgroundColor: 'var(--app-bg-alt)', transition: 'all 0.3s ease' }}
                                onClick={() => setShowGuestPrompt(true)}
                            >
                                Continue as Guest
                            </Button>
                        </div>
                    </div>
                </Col>
            </Row>

            {/* Guest Name Prompt Modal */}
            <Modal show={showGuestPrompt} onHide={() => setShowGuestPrompt(false)} centered backdrop="static">
                <div style={{ backgroundColor: 'var(--app-bg-card)', color: 'var(--app-text-primary)', borderRadius: '6px' }}>
                    <Modal.Header closeButton style={{ borderBottom: '1px solid var(--app-border-light)' }} className="px-4 pt-4">
                        <Modal.Title style={{ fontSize: '1.2rem', fontWeight: 'bold' }}>Welcome</Modal.Title>
                    </Modal.Header>
                    <Modal.Body className="px-4 pb-4">
                        <Form onSubmit={handleGuestSubmit}>
                            <Form.Group className="mb-3">
                                <Form.Label className="fw-bold" style={{ fontSize: '0.85rem', color: 'var(--app-text-secondary)' }}>Please enter your name:</Form.Label>
                                <Form.Control
                                    type="text"
                                    value={guestNameInput}
                                    placeholder="e.g. John Doe"
                                    onChange={(e) => setGuestNameInput(e.target.value)}
                                    style={{ backgroundColor: 'var(--app-input-bg)', color: 'var(--app-input-text)', borderColor: 'var(--app-input-border)' }}
                                    autoFocus
                                />
                            </Form.Group>
                            <div className="d-flex justify-content-end gap-2">
                                <Button variant="secondary" onClick={() => setShowGuestPrompt(false)} style={{ backgroundColor: 'transparent', color: 'var(--app-text-secondary)', border: '1px solid var(--app-border-light)' }}>Cancel</Button>
                                <Button type="submit" style={{ backgroundColor: 'var(--app-primary-accent)', color: 'var(--app-bg-main)', border: 'none', fontWeight: 'bold' }}>Continue</Button>
                            </div>
                        </Form>
                    </Modal.Body>
                </div>
            </Modal>
        </Container>
    );
};

export default Loginpage;