import test from 'node:test';
import assert from 'node:assert/strict';
import JSZip from 'jszip';
import { export3psFile } from '../../src/utils/projectExport.js';
import { import3psFile } from '../../src/utils/projectImport.js';
import { normalizeProjectData } from '../../src/utils/projectSchema.js';

test('a web archive round-trips identity, zero values, material IDs and trash state', async () => {
    const original = normalizeProjectData({
        id: 'archive-test',
        general_info: { project_name: 'Archive Bridge', project_currency: 'INR' },
        financial_data: { discount_rate: 0 },
        foundation_data: [{ id: 'foundation', name: 'Foundation', rows: [{ id: 'material-1', workName: 'Steel', qty: 0, rate: 10, unit: 'kg', state: { in_trash: true }, carbonEmission: { factor: 2 } }] }],
    });
    const before = structuredClone(original);
    const restored = await import3psFile(await (await export3psFile(original)).arrayBuffer());
    assert.equal(restored.general_info.project_name, 'Archive Bridge');
    assert.equal(Number(restored.financial_data.discount_rate), 0);
    const row = restored.foundation_data[0].rows[0];
    assert.equal(row.id, 'material-1');
    assert.equal(Number(row.qty), 0);
    assert.equal(row.state.in_trash, true);
    assert.deepEqual(original, before, 'export must not mutate project state');
});

test('invalid archive data reports the existing error and retains its cause', async () => {
    await assert.rejects(import3psFile(new Uint8Array([1, 2, 3]).buffer), error => {
        assert.equal(error.message, 'Corrupted or invalid .3ps zip archive.');
        assert.ok(error.cause instanceof Error);
        return true;
    });
});

test('a malformed known chunk identifies the failing section', async (t) => {
    t.mock.method(console, 'error', () => {});
    const zip = new JSZip();
    zip.file('chunks/financial_data.json', '{invalid');
    await assert.rejects(import3psFile(await zip.generateAsync({ type: 'arraybuffer' })), error => {
        assert.match(error.message, /Parsing failure in chunk "financial_data"/);
        assert.ok(error.cause instanceof Error);
        return true;
    });
});
