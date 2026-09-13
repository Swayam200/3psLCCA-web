import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
    plugins: [react()],
    // Tests use isolated storage and mocked services, never a developer's .env.
    envDir: false,
    test: {
        environment: 'jsdom',
        include: ['tests/components/**/*.spec.jsx', 'tests/integration/**/*.spec.js'],
        setupFiles: ['tests/helpers/setup.js'],
        restoreMocks: true,
        unstubGlobals: true,
        coverage: {
            provider: 'v8',
            reporter: ['text', 'html', 'lcov'],
            reportsDirectory: 'coverage/components',
            include: ['src/contexts/ProjectDataContext.jsx', 'src/lib/projectStorageService.js', 'src/gui/components/RenameProjectModal.jsx', 'src/gui/components/NewProjectModal.jsx'],
        },
    },
});
