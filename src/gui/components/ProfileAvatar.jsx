/* eslint-disable no-unused-vars */
import React, { useState, useRef } from 'react';

const ProfileAvatar = ({ size = 80, profileName, logoData, onLogoChange, theme }) => {
    const [isHovered, setIsHovered] = useState(false);
    const fileInputRef = useRef(null);

    const handleClick = () => {
        fileInputRef.current?.click();
    };

    const handleFileChange = (event) => {
        const file = event.target.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = (e) => {
            const img = new Image();
            img.onload = () => {
                const canvas = document.createElement('canvas');
                const MAX_WIDTH = 300;
                const MAX_HEIGHT = 300;
                let width = img.width;
                let height = img.height;

                if (width > height) {
                    if (width > MAX_WIDTH) {
                        height = Math.round(height * (MAX_WIDTH / width));
                        width = MAX_WIDTH;
                    }
                } else {
                    if (height > MAX_HEIGHT) {
                        width = Math.round(width * (MAX_HEIGHT / height));
                        height = MAX_HEIGHT;
                    }
                }
                
                canvas.width = width;
                canvas.height = height;
                const ctx = canvas.getContext('2d');
                ctx.drawImage(img, 0, 0, width, height);
                
                // Compress to JPEG with 0.8 quality to keep it under 30KB
                const dataUrl = canvas.toDataURL('image/jpeg', 0.8);
                onLogoChange(dataUrl);
            };
            img.src = e.target.result;
        };
        reader.readAsDataURL(file);
        event.target.value = '';
    };

    // Determine display content
    const getDisplayContent = () => {
        if (logoData && logoData !== 'null' && logoData !== 'undefined') {
            return (
                <img 
                    src={logoData} 
                    alt="Profile Logo" 
                    style={{
                        width: '100%',
                        height: '100%',
                        objectFit: 'cover',
                        borderRadius: '50%'
                    }}
                />
            );
        }
        
        if (profileName) {
            const initials = profileName
                .split(/\s+/)
                .filter(Boolean)
                .map(word => word[0])
                .join('')
                .slice(0, 2)
                .toUpperCase();

            // Calculate a hash from the profileName for dynamic consistent color/gradient
            let hash = 0;
            for (let i = 0; i < profileName.length; i++) {
                hash = profileName.charCodeAt(i) + ((hash << 5) - hash);
            }
            const hue1 = Math.abs(hash) % 360;
            const hue2 = (hue1 + 40) % 360;
            const bgGradient = `linear-gradient(135deg, hsl(${hue1}, 60%, 50%) 0%, hsl(${hue2}, 60%, 40%) 100%)`;
            
            return (
                <div
                    style={{
                        width: '100%',
                        height: '100%',
                        borderRadius: '50%',
                        background: bgGradient,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: '#fff',
                        fontSize: initials.length > 1 ? `${size / 3.5}px` : `${size / 3}px`,
                        fontWeight: 'bold',
                        letterSpacing: initials.length > 1 ? '1px' : 'normal'
                    }}
                >
                    {initials}
                </div>
            );
        }

        // Empty state - show +
        return (
            <div
                style={{
                    width: '100%',
                    height: '100%',
                    borderRadius: '50%',
                    backgroundColor: theme?.border || '#d1d5db',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: theme?.textSecondary || '#6b7280',
                    fontSize: `${size / 2}px`,
                    cursor: 'pointer'
                }}
            >
                +
            </div>
        );
    };

    return (
        <>
            <div
                onClick={handleClick}
                onMouseEnter={() => setIsHovered(true)}
                onMouseLeave={() => setIsHovered(false)}
                style={{
                    width: size,
                    height: size,
                    borderRadius: '50%',
                    cursor: 'pointer',
                    position: 'relative',
                    overflow: 'hidden'
                }}
            >
                {getDisplayContent()}
                
                {/* Hover overlay */}
                {isHovered && profileName && (
                    <div
                        style={{
                            position: 'absolute',
                            top: 0,
                            left: 0,
                            right: 0,
                            bottom: 0,
                            borderRadius: '50%',
                            backgroundColor: 'rgba(0, 0, 0, 0.5)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            color: '#fff',
                            fontSize: '12px',
                            fontWeight: 'bold'
                        }}
                    >
                        CHANGE
                    </div>
                )}
            </div>
            
            {/* Hidden file input for logo upload */}
            <input
                type="file"
                ref={fileInputRef}
                onChange={handleFileChange}
                accept="image/png,image/jpeg,image/jpg"
                style={{ display: 'none' }}
            />
        </>
    );
};

export default ProfileAvatar;
