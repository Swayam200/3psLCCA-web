// Loaded only into the isolated demo test server. Invalid-key/provider-error
// tests remain deterministic and never send requests to a real AI provider.
globalThis.fetch = async () => {
    throw new Error('External provider requests are disabled in demo tests.');
};
