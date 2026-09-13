import { beforeEach, describe, expect, it, vi } from 'vitest';

const cloud = vi.hoisted(() => ({
    account: { get: vi.fn() },
    databases: { getDocument: vi.fn(), updateDocument: vi.fn(), createDocument: vi.fn(), listDocuments: vi.fn(), deleteDocument: vi.fn() },
}));
vi.mock('../../src/lib/appwrite', () => ({
    ...cloud,
    APPWRITE_CONFIG: { databaseId: 'test-db', collectionId: 'test-projects' },
    Query: { equal: vi.fn(), orderDesc: vi.fn() },
}));
import { projectStorageService as storage } from '../../src/lib/projectStorageService.js';

const project = (name = 'Bridge', time = 100) => ({ name, general_info: { project_name: name }, _lastModified: time });
const local = () => JSON.parse(localStorage.getItem('project_data_p'));
const putLocal = (data, status = 'pending') => {
    localStorage.setItem('project_data_p', JSON.stringify({ data, sync_status: status }));
    localStorage.setItem('recentProjects', JSON.stringify([{ id: 'p', name: data.name }]));
};
beforeEach(() => {
    vi.resetAllMocks();
    vi.spyOn(console, 'error').mockImplementation(() => {});
    vi.spyOn(console, 'log').mockImplementation(() => {});
    cloud.account.get.mockResolvedValue({ $id: 'test-user' });
    cloud.databases.getDocument.mockResolvedValue({ data: JSON.stringify(project()) });
    cloud.databases.updateDocument.mockResolvedValue({});
    cloud.databases.createDocument.mockResolvedValue({});
    cloud.databases.deleteDocument.mockResolvedValue({});
});

describe('guest persistence', () => {
    beforeEach(() => sessionStorage.setItem('isGuest', 'true'));
    it('saves, renames, lists and reloads without contacting Appwrite', async () => {
        await storage.saveProject('p', project());
        await storage.saveProject('p', project('Renamed'));
        expect((await storage.loadProject('p')).name).toBe('Renamed');
        expect(await storage.listProjects()).toEqual([expect.objectContaining({ id: 'p', name: 'Renamed' })]);
        expect(local().sync_status).toBe('synced');
        expect(cloud.account.get).not.toHaveBeenCalled();
        expect(cloud.databases.getDocument).not.toHaveBeenCalled();
    });
    it('loads old unwrapped local projects', async () => {
        localStorage.setItem('project_data_p', JSON.stringify(project('Legacy')));
        expect((await storage.loadProject('p')).general_info.project_name).toBe('Legacy');
    });
    it('returns null for a missing project and removes deleted projects from recents', async () => {
        expect(await storage.loadProject('missing')).toBeNull();
        await storage.saveProject('p', project());
        await storage.deleteProject('p');
        expect(local()).toBeNull();
        expect(await storage.listProjects()).toEqual([]);
        await storage.syncPendingProjects();
        expect(cloud.account.get).not.toHaveBeenCalled();
    });
});

describe('cloud persistence', () => {
    it('writes locally before an asynchronous cloud save completes', async () => {
        let finish;
        cloud.databases.updateDocument.mockImplementation(() => new Promise(resolve => { finish = resolve; }));
        const saving = storage.saveProject('p', project());
        expect(local().data.name).toBe('Bridge');
        expect(local().sync_status).toBe('pending');
        await vi.waitFor(() => expect(finish).toBeTypeOf('function'));
        finish({});
        await saving;
        expect(local().sync_status).toBe('synced');
    });
    it('preserves local data and the offline error contract when authentication fails', async () => {
        cloud.account.get.mockRejectedValue(new Error('Not authenticated'));
        await expect(storage.saveProject('p', project())).rejects.toThrow('offline');
        expect(local().data.name).toBe('Bridge');
        expect(local().sync_status).toBe('pending');
    });
    it('creates a missing document with its owner', async () => {
        cloud.databases.getDocument.mockRejectedValue(Object.assign(new Error('Missing'), { code: 404 }));
        await storage.saveProject('p', project());
        expect(cloud.databases.createDocument).toHaveBeenCalledWith('test-db', 'test-projects', 'p', expect.objectContaining({ userId: 'test-user', name: 'Bridge' }));
    });
    it.each([
        [200, 100, 'Local', 'pending'],
        [100, 200, 'Cloud', 'synced'],
        [100, 100, 'Cloud', 'synced'],
    ])('resolves local=%i and cloud=%i timestamps to %s', async (localTime, cloudTime, expected, status) => {
        putLocal(project('Local', localTime));
        cloud.databases.getDocument.mockResolvedValue({ data: JSON.stringify(project('Cloud', cloudTime)) });
        expect((await storage.loadProject('p')).name).toBe(expected);
        expect(local().sync_status).toBe(status);
    });
    it('uses the local copy when the cloud cannot be reached', async () => {
        putLocal(project('Offline'));
        cloud.databases.getDocument.mockRejectedValue(new Error('Network unavailable'));
        expect((await storage.loadProject('p')).name).toBe('Offline');
    });
    it('retries pending saves without changing their edit timestamp', async () => {
        putLocal(project('Pending', 123));
        await storage.syncPendingProjects();
        expect(cloud.databases.updateDocument).toHaveBeenCalled();
        expect(local().sync_status).toBe('synced');
        expect(local().data._lastModified).toBe(123);
    });
    it('leaves a failed retry pending for the next sync', async () => {
        putLocal(project());
        cloud.databases.getDocument.mockRejectedValue(new Error('Offline'));
        cloud.databases.createDocument.mockRejectedValue(new Error('Offline'));
        await storage.syncPendingProjects();
        expect(local().sync_status).toBe('pending');
    });
    it('merges local-only projects into the cloud list without duplicating IDs', async () => {
        putLocal(project('Local'));
        cloud.databases.listDocuments.mockResolvedValue({ documents: [{ $id: 'cloud', name: 'Cloud', $createdAt: '2026-01-01' }, { $id: 'p', name: 'Cloud P', $createdAt: '2026-01-01' }] });
        const projects = await storage.listProjects();
        expect(projects.map(p => p.id)).toEqual(['cloud', 'p']);
        expect(projects[1].name).toBe('Cloud P');
    });
});
