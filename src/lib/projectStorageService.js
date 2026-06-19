/* eslint-disable no-unused-vars */
import { databases, APPWRITE_CONFIG, ID, Query, account } from './appwrite';
import { normalizeProjectData } from '../utils/projectSchema';

/**
 * Helper to get the current Appwrite user ID if logged in
 */
const getCurrentUserId = async () => {
    try {
        const user = await account.get();
        return user.$id;
    } catch (e) {
        return null;
    }
};

/**
 * Service to abstract storing project data.
 * Implements an Offline-First strategy: always writes to localStorage,
 * and syncs to Appwrite in the background. Handles conflict resolution
 * using a "Last Write Wins" approach via _lastModified timestamps.
 */
export const projectStorageService = {
    async saveProject(projectId, projectData) {
        const isGuest = sessionStorage.getItem('isGuest') === 'true';
        const now = Date.now();
        const normalizedProject = normalizeProjectData({
            ...projectData,
            _lastModified: now,
        });

        // 1. Always Save Locally First
        const storageKey = `project_data_${projectId}`;
        const localWrapper = {
            data: normalizedProject,
            sync_status: isGuest ? 'synced' : 'pending'
        };
        localStorage.setItem(storageKey, JSON.stringify(localWrapper));
        
        // Update recent projects
        let recent = JSON.parse(localStorage.getItem('recentProjects') || '[]');
        const index = recent.findIndex(p => p.id === projectId);
        if (index > -1) {
            recent[index].name = normalizedProject.name || recent[index].name;
            recent[index].date = new Date(now).toLocaleDateString();
        } else {
            recent.push({
                id: projectId,
                name: normalizedProject.name || 'Unnamed Project',
                date: new Date(now).toLocaleDateString()
            });
        }
        localStorage.setItem('recentProjects', JSON.stringify(recent));

        // 2. Try to sync to cloud if logged in
        if (!isGuest) {
            try {
                const userId = await getCurrentUserId();
                if (!userId) throw new Error("Not logged in");

                const cloudData = {
                    name: normalizedProject.name || 'Unnamed Project',
                    data: JSON.stringify(normalizedProject)
                };

                try {
                    await databases.getDocument(
                        APPWRITE_CONFIG.databaseId,
                        APPWRITE_CONFIG.collectionId,
                        projectId
                    );
                    
                    await databases.updateDocument(
                        APPWRITE_CONFIG.databaseId,
                        APPWRITE_CONFIG.collectionId,
                        projectId,
                        cloudData
                    );
                } catch (e) {
                    await databases.createDocument(
                        APPWRITE_CONFIG.databaseId,
                        APPWRITE_CONFIG.collectionId,
                        projectId,
                        { ...cloudData, userId: userId }
                    );
                }
                
                // Cloud save success: update local status
                localWrapper.sync_status = 'synced';
                localStorage.setItem(storageKey, JSON.stringify(localWrapper));

            } catch (err) {
                console.error("Failed to save project to cloud. Preserved locally.", err);
                throw new Error("offline");
            }
        }
    },

    async loadProject(projectId) {
        const isGuest = sessionStorage.getItem('isGuest') === 'true';
        const storageKey = `project_data_${projectId}`;
        const savedStr = localStorage.getItem(storageKey);
        
        // Handle backwards compatibility where local storage might just be raw projectData
        let localData = null;
        if (savedStr) {
            const parsed = JSON.parse(savedStr);
            if (parsed.sync_status && parsed.data) {
                localData = normalizeProjectData(parsed.data);
            } else {
                localData = normalizeProjectData(parsed);
            }
        }

        if (isGuest) {
            return localData;
        } else {
            try {
                const doc = await databases.getDocument(
                    APPWRITE_CONFIG.databaseId,
                    APPWRITE_CONFIG.collectionId,
                    projectId
                );
                const cloudData = normalizeProjectData(JSON.parse(doc.data));
                
                // Conflict resolution: Last Write Wins
                const cloudTime = cloudData._lastModified || 0;
                const localTime = localData?._lastModified || 0;
                
                if (localData && localTime > cloudTime) {
                    // Local is newer (e.g. user was offline) -> queue a sync
                    console.log("Local data is newer than cloud. Using local data.");
                    const wrapper = { data: localData, sync_status: 'pending' };
                    localStorage.setItem(storageKey, JSON.stringify(wrapper));
                    return localData;
                } else {
                    // Cloud is newer or same -> use cloud and update local cache
                    const wrapper = { data: cloudData, sync_status: 'synced' };
                    localStorage.setItem(storageKey, JSON.stringify(wrapper));
                    return cloudData;
                }
            } catch (e) {
                console.error("Failed to load project from cloud. Falling back to local.", e);
                return localData;
            }
        }
    },

    async listProjects() {
        const isGuest = sessionStorage.getItem('isGuest') === 'true';
        
        if (isGuest) {
            return JSON.parse(localStorage.getItem('recentProjects') || '[]');
        } else {
            try {
                const userId = await getCurrentUserId();
                if (!userId) return [];
                
                const response = await databases.listDocuments(
                    APPWRITE_CONFIG.databaseId,
                    APPWRITE_CONFIG.collectionId,
                    [
                        Query.equal('userId', userId),
                        Query.orderDesc('$createdAt')
                    ]
                );
                
                const cloudList = response.documents.map(doc => ({
                    id: doc.$id,
                    name: doc.name,
                    date: new Date(doc.$createdAt).toLocaleDateString(),
                    pinned: false
                }));
                const localList = JSON.parse(localStorage.getItem('recentProjects') || '[]');
                const merged = [...cloudList];
                for (const localProj of localList) {
                    if (!merged.some(p => p.id === localProj.id)) {
                        merged.push(localProj);
                    }
                }
                return merged;
            } catch (e) {
                console.error("Failed to list projects from cloud", e);
                // Fallback to local list if offline
                return JSON.parse(localStorage.getItem('recentProjects') || '[]');
            }
        }
    },

    async deleteProject(projectId) {
        const isGuest = sessionStorage.getItem('isGuest') === 'true';
        
        // Always delete locally
        localStorage.removeItem(`project_data_${projectId}`);
        let recent = JSON.parse(localStorage.getItem('recentProjects') || '[]');
        recent = recent.filter(p => p.id !== projectId);
        localStorage.setItem('recentProjects', JSON.stringify(recent));

        if (!isGuest) {
            try {
                await databases.deleteDocument(
                    APPWRITE_CONFIG.databaseId,
                    APPWRITE_CONFIG.collectionId,
                    projectId
                );
            } catch (e) {
                console.error("Failed to delete project from cloud", e);
            }
        }
    },

    async syncPendingProjects() {
        const isGuest = sessionStorage.getItem('isGuest') === 'true';
        if (isGuest) return;

        try {
            const userId = await getCurrentUserId();
            if (!userId) return;

            let recent = JSON.parse(localStorage.getItem('recentProjects') || '[]');
            
            for (let proj of recent) {
                const storageKey = `project_data_${proj.id}`;
                const savedStr = localStorage.getItem(storageKey);
                if (!savedStr) continue;
                
                const parsed = JSON.parse(savedStr);
                if (parsed.sync_status === 'pending' && parsed.data) {
                    console.log(`Background syncing project ${proj.id}...`);
                    try {
                        const normalizedProject = normalizeProjectData(parsed.data);
                        const cloudData = {
                            name: normalizedProject.name || 'Unnamed Project',
                            data: JSON.stringify(normalizedProject)
                        };

                        try {
                            await databases.getDocument(
                                APPWRITE_CONFIG.databaseId,
                                APPWRITE_CONFIG.collectionId,
                                proj.id
                            );
                            await databases.updateDocument(
                                APPWRITE_CONFIG.databaseId,
                                APPWRITE_CONFIG.collectionId,
                                proj.id,
                                cloudData
                            );
                        } catch (e) {
                            await databases.createDocument(
                                APPWRITE_CONFIG.databaseId,
                                APPWRITE_CONFIG.collectionId,
                                proj.id,
                                { ...cloudData, userId: userId }
                            );
                        }
                        
                        parsed.data = normalizedProject;
                        parsed.sync_status = 'synced';
                        localStorage.setItem(storageKey, JSON.stringify(parsed));
                        console.log(`Successfully synced project ${proj.id}`);
                    } catch (e) {
                        console.error(`Background sync failed for ${proj.id}`, e);
                    }
                }
            }
        } catch (e) {
            console.error("Error in syncPendingProjects", e);
        }
    }
};
