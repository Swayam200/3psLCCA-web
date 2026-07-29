import { Client, Account, Databases, ID, Query } from 'appwrite';

const endpoint = import.meta.env.VITE_APPWRITE_ENDPOINT;
const projectId = import.meta.env.VITE_APPWRITE_PROJECT_ID;

// Builds without Appwrite env (e.g. a fresh checkout with no .env) must still
// boot: skip client configuration so the app runs in guest/offline mode
// instead of throwing at module load and blanking the whole page.
export const isAppwriteConfigured = Boolean(endpoint && projectId);

const client = new Client();

if (isAppwriteConfigured) {
    client
        .setEndpoint(endpoint)
        .setProject(projectId);
}

export const account = new Account(client);
export const databases = new Databases(client);

export const APPWRITE_CONFIG = {
    databaseId: import.meta.env.VITE_APPWRITE_DATABASE_ID,
    collectionId: import.meta.env.VITE_APPWRITE_COLLECTION_ID,
};

export { ID, Query };
