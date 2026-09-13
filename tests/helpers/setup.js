import { afterEach, beforeEach, vi } from 'vitest';
import { cleanup } from '@testing-library/react';
import { createStorage } from './storage.js';

beforeEach(() => {
    vi.stubGlobal('localStorage', createStorage());
    vi.stubGlobal('sessionStorage', createStorage());
});
afterEach(() => {
    cleanup();
    vi.useRealTimers();
});
