import { useMemo, useState } from 'react';
import { Button, Form, Modal, Table } from 'react-bootstrap';
import { useProjectData } from '../../../contexts/ProjectDataContext';
import {
    computeTransportEmissions,
    computeTransportEntry,
    computeTrips,
    defaultKgFactorForRow,
    formatNumber,
    getStructureMaterials,
    parseNumber,
    STRUCTURE_CHUNKS,
} from './carbonUtils';

const blankVehicle = {
    name: '',
    vehicle_class: '',
    capacity: 0,
    gross_weight: 0,
    empty_weight: 0,
    emission_factor: 0,
    is_custom: true,
};

const DeliveryModal = ({ show, onHide, onSave, initialData }) => {
    const { projectData } = useProjectData();
    const allMaterials = useMemo(() => getStructureMaterials(projectData), [projectData]);
    const assigned = useMemo(() => {
        const currentId = initialData?.id;
        return new Set((projectData.transport_data?.vehicles || [])
            .filter((entry) => entry.id !== currentId && entry.state?.in_trash !== true)
            .flatMap((entry) => entry.materials || [])
            .map((item) => item.uuid));
    }, [initialData?.id, projectData.transport_data?.vehicles]);

    const [origin, setOrigin] = useState(initialData?.route?.origin || '');
    const [distance, setDistance] = useState(initialData?.route?.distance_km || 0);
    const [vehicle, setVehicle] = useState({ ...blankVehicle, ...(initialData?.vehicle || {}) });
    const [selected, setSelected] = useState(() => {
        const map = new Map();
        (initialData?.materials || []).forEach((item) => map.set(item.uuid, parseNumber(item.kg_factor)));
        return map;
    });
    const [search, setSearch] = useState('');
    const [hideAssigned, setHideAssigned] = useState(false);
    const [poolMaterials, setPoolMaterials] = useState(initialData?.summary?.pool_materials ?? true);

    const materialRows = allMaterials.map((material) => {
        const kgFactor = selected.get(material.id) ?? material.kg_factor ?? defaultKgFactorForRow(material.raw);
        return {
            ...material,
            kg_factor: kgFactor,
            qty_kg: material.quantity * kgFactor,
            assigned: assigned.has(material.id),
        };
    }).filter((material) => {
        const term = search.trim().toLowerCase();
        const matches = !term || [material.name, material.category, material.unit]
            .some((value) => String(value || '').toLowerCase().includes(term));
        return matches && (!hideAssigned || !material.assigned);
    });

    const selectedRows = materialRows.filter((material) => selected.has(material.id));
    const trips = computeTrips(selectedRows.map((row) => ({
        material_name: row.name,
        qty_kg: row.qty_kg,
    })), parseNumber(vehicle.capacity) * 1000, poolMaterials);
    const emission = trips * parseNumber(distance) * parseNumber(vehicle.emission_factor) *
        (parseNumber(vehicle.gross_weight) + parseNumber(vehicle.empty_weight));

    const setVehicleField = (field, value) => {
        setVehicle((prev) => {
            const next = { ...prev, [field]: value };
            if (field === 'name') next.vehicle_class = value;
            if (field === 'capacity' || field === 'gross_weight') {
                next.empty_weight = Math.max(0, parseNumber(next.gross_weight) - parseNumber(next.capacity));
            }
            return next;
        });
    };

    const toggleMaterial = (material) => {
        if (material.assigned) return;
        setSelected((prev) => {
            const next = new Map(prev);
            if (next.has(material.id)) next.delete(material.id);
            else next.set(material.id, material.kg_factor || 0);
            return next;
        });
    };

    const updateKgFactor = (materialId, value) => {
        setSelected((prev) => {
            const next = new Map(prev);
            if (next.has(materialId)) next.set(materialId, parseNumber(value));
            return next;
        });
    };

    const selectAllVisible = () => {
        const enabled = materialRows.filter((material) => !material.assigned && material.quantity > 0 && material.kg_factor > 0);
        const allSelected = enabled.every((material) => selected.has(material.id));
        setSelected((prev) => {
            const next = new Map(prev);
            enabled.forEach((material) => {
                if (allSelected) next.delete(material.id);
                else next.set(material.id, material.kg_factor);
            });
            return next;
        });
    };

    const handleSave = () => {
        if (parseNumber(distance) <= 0) return window.alert('One-way distance must be greater than 0 km.');
        if (parseNumber(vehicle.capacity) <= 0) return window.alert('Payload capacity must be greater than 0 t.');
        if (parseNumber(vehicle.gross_weight) <= 0) return window.alert('Gross weight (loaded) must be greater than 0 t.');
        if (parseNumber(vehicle.gross_weight) < parseNumber(vehicle.capacity)) return window.alert('Gross weight (loaded) must be >= payload capacity.');
        if (parseNumber(vehicle.emission_factor) <= 0) return window.alert('Emission factor must be greater than 0 kgCO2e / t-km.');
        const materials = Array.from(selected.entries())
            .filter(([, kgFactor]) => kgFactor > 0)
            .map(([uuid, kgFactor]) => ({
                uuid,
                kg_factor: kgFactor,
                material_name: allMaterials.find((item) => item.id === uuid)?.name || '',
            }));
        if (materials.length === 0) return window.alert('Select at least one material with a valid kg/unit factor.');
        const totalCargoKg = materials.reduce((sum, item) => {
            const material = allMaterials.find((row) => row.id === item.uuid);
            return sum + (material?.quantity || 0) * item.kg_factor;
        }, 0);
        if (totalCargoKg <= 0) return window.alert('At least one selected material must have non-zero quantity.');
        onSave({
            id: initialData?.id || crypto.randomUUID(),
            vehicle: {
                ...vehicle,
                capacity: parseNumber(vehicle.capacity),
                gross_weight: parseNumber(vehicle.gross_weight),
                empty_weight: Math.max(0, parseNumber(vehicle.gross_weight) - parseNumber(vehicle.capacity)),
                emission_factor: parseNumber(vehicle.emission_factor),
                vehicle_class: vehicle.vehicle_class || vehicle.name,
                is_custom: true,
            },
            route: {
                origin,
                destination: 'Site',
                distance_km: parseNumber(distance),
            },
            materials,
            summary: {
                pool_materials: poolMaterials,
                trips,
                total_cargo_kg: totalCargoKg,
                total_cargo_t: totalCargoKg / 1000,
                distance_km: parseNumber(distance),
                emission_factor: parseNumber(vehicle.emission_factor),
                total_emissions_kgco2e: emission,
            },
            meta: {
                created_at: initialData?.meta?.created_at || new Date().toISOString(),
                updated_at: new Date().toISOString(),
            },
            state: initialData?.state || {},
        });
        return null;
    };

    return (
        <Modal show={show} onHide={onHide} size="xl" centered contentClassName="bg-dark text-light carbon-delivery-modal">
            <Modal.Header closeButton closeVariant="white">
                <Modal.Title>{initialData ? 'Edit Delivery' : 'Add Delivery'}</Modal.Title>
            </Modal.Header>
            <Modal.Body style={{ maxHeight: '72vh', overflowY: 'auto' }}>
                <style>{`
                    .carbon-delivery-modal .form-control,
                    .carbon-delivery-modal .form-select {
                        background: var(--app-bg-alt);
                        color: var(--app-text-primary);
                        border-color: var(--app-border-mid);
                    }
                    .carbon-delivery-modal .form-label {
                        font-size: 0.72rem;
                        font-weight: 700;
                        color: var(--app-text-secondary);
                    }
                `}</style>
                <div className="carbon-section-title mt-0">Delivery Configuration</div>
                <div className="row g-3 mb-3">
                    <div className="col-md-3">
                        <Form.Label>FROM - TO</Form.Label>
                        <Form.Control size="sm" value={origin} onChange={(event) => setOrigin(event.target.value)} />
                    </div>
                    <div className="col-md-3">
                        <Form.Label>ONE-WAY DISTANCE (km) *</Form.Label>
                        <Form.Control size="sm" type="number" value={distance} onChange={(event) => setDistance(event.target.value)} />
                    </div>
                    <div className="col-md-3">
                        <Form.Label>VEHICLE TYPE</Form.Label>
                        <Form.Control size="sm" value={vehicle.name} onChange={(event) => setVehicleField('name', event.target.value)} />
                    </div>
                    <div className="col-md-3">
                        <Form.Label>PAYLOAD CAPACITY (t) *</Form.Label>
                        <Form.Control size="sm" type="number" value={vehicle.capacity} onChange={(event) => setVehicleField('capacity', event.target.value)} />
                    </div>
                    <div className="col-md-3">
                        <Form.Label>GROSS WEIGHT - LOADED (t) *</Form.Label>
                        <Form.Control size="sm" type="number" value={vehicle.gross_weight} onChange={(event) => setVehicleField('gross_weight', event.target.value)} />
                    </div>
                    <div className="col-md-3">
                        <Form.Label>EMPTY WEIGHT (t)</Form.Label>
                        <Form.Control size="sm" type="number" value={vehicle.empty_weight} onChange={(event) => setVehicleField('empty_weight', event.target.value)} />
                    </div>
                    <div className="col-md-3">
                        <Form.Label>EMISSION FACTOR *</Form.Label>
                        <Form.Control size="sm" type="number" value={vehicle.emission_factor} onChange={(event) => setVehicleField('emission_factor', event.target.value)} />
                    </div>
                </div>

                <div className="carbon-section-title mt-4">Material Picker</div>
                <div className="d-flex align-items-center gap-2 mb-2">
                    <Form.Control size="sm" placeholder="Search materials..." value={search} onChange={(event) => setSearch(event.target.value)} />
                    <Form.Check type="checkbox" label="Pool same materials" checked={poolMaterials} onChange={(event) => setPoolMaterials(event.target.checked)} />
                    <Form.Check type="checkbox" label="Hide assigned" checked={hideAssigned} onChange={(event) => setHideAssigned(event.target.checked)} />
                    <Button size="sm" variant="outline-light" onClick={selectAllVisible}>Select with Quantity</Button>
                </div>

                <Table size="sm" variant="dark" bordered hover responsive className="carbon-desktop-table">
                    <thead>
                        <tr>
                            <th style={{ width: 42 }} />
                            <th>Material</th>
                            <th>Category</th>
                            <th>Unit</th>
                            <th className="text-end">kg / unit</th>
                            <th className="text-end">Quantity (kg)</th>
                        </tr>
                    </thead>
                    <tbody>
                        {materialRows.map((material) => {
                            const checked = selected.has(material.id);
                            const canSelect = !material.assigned && material.kg_factor > 0;
                            return (
                                <tr key={material.id} className={material.assigned ? 'opacity-50' : ''}>
                                    <td className="text-center">
                                        <Form.Check
                                            checked={checked}
                                            disabled={!canSelect}
                                            onChange={() => toggleMaterial(material)}
                                        />
                                    </td>
                                    <td>{material.name}</td>
                                    <td>{material.category}</td>
                                    <td>{material.unit || '-'}</td>
                                    <td className="text-end">
                                        <input
                                            type="number"
                                            className="form-control form-control-sm text-end"
                                            value={material.kg_factor || ''}
                                            disabled={material.assigned}
                                            onChange={(event) => updateKgFactor(material.id, event.target.value)}
                                            onFocus={() => {
                                                if (!checked && !material.assigned) toggleMaterial(material);
                                            }}
                                        />
                                    </td>
                                    <td className="text-end">{material.qty_kg > 0 ? formatNumber(material.qty_kg, 0) : '-'}</td>
                                </tr>
                            );
                        })}
                    </tbody>
                </Table>
            </Modal.Body>
            <Modal.Footer className="justify-content-between">
                <div className="d-flex gap-3">
                    <span>Trips: <strong>{trips || '-'}</strong></span>
                    <span>Total Emission: <strong>{emission > 0 ? formatNumber(emission) : '-'}</strong> kgCO2e</span>
                </div>
                <div className="d-flex gap-2">
                    <Button variant="secondary" onClick={onHide}>Cancel</Button>
                    <Button variant="primary" onClick={handleSave}>Save Delivery</Button>
                </div>
            </Modal.Footer>
        </Modal>
    );
};

const TransportationEmissions = () => {
    const { projectData, updateProjectData } = useProjectData();
    const [editingEntry, setEditingEntry] = useState(null);
    const transportData = projectData.transport_data || { vehicles: [] };
    // Display-only derivation — persisted transport_emissions_data is
    // maintained by normalizeCarbonEmissionData / deriveCarbonEmissionData.
    // (A write-back effect here fought the normalizer's shape and looped
    // React; see MaterialEmissions for the same fix.)
    const computed = useMemo(() => computeTransportEmissions(projectData), [projectData]);

    const saveEntry = (entry) => {
        const vehicles = transportData.vehicles || [];
        const exists = vehicles.some((item) => item.id === entry.id);
        const nextVehicles = exists
            ? vehicles.map((item) => (item.id === entry.id ? entry : item))
            : [...vehicles, entry];
        updateProjectData('transport_data', { ...transportData, vehicles: nextVehicles });
        setEditingEntry(null);
    };

    const trashEntry = (entryId) => {
        if (!window.confirm('Remove this delivery entry? Materials will be available for reassignment.')) return;
        const nextVehicles = (transportData.vehicles || []).map((entry) => (
            entry.id === entryId
                ? { ...entry, state: { ...(entry.state || {}), in_trash: true }, meta: { ...(entry.meta || {}), updated_at: new Date().toISOString() } }
                : entry
        ));
        updateProjectData('transport_data', { ...transportData, vehicles: nextVehicles });
    };

    const activeVehicles = (transportData.vehicles || []).filter((entry) => entry.state?.in_trash !== true);

    return (
        <div className="transportation-emissions carbon-desktop-page">
            <div className="carbon-summary-strip mb-3 d-flex justify-content-between align-items-center">
                <div className="d-flex gap-4">
                    <span>Total Transport Emissions: <strong>{formatNumber(computed.total_kgCO2e)}</strong> kgCO2e</span>
                    <span>Vehicles: <strong>{computed.active_vehicle_count}</strong></span>
                </div>
                <Button size="sm" variant="outline-light" onClick={() => setEditingEntry({})}>+ Add Delivery</Button>
            </div>

            <div className="d-flex gap-4 flex-wrap mb-3 small text-secondary">
                {STRUCTURE_CHUNKS.map(([, label]) => (
                    <span key={label}>{label}: <strong>{formatNumber(computed.cat_totals[label] || 0)}</strong></span>
                ))}
            </div>

            <div className="carbon-section-title">Transportation Deliveries</div>

            {activeVehicles.length === 0 ? (
                <div className="text-center py-5" style={{ border: '1px dashed var(--app-border-mid)', background: 'var(--app-bg-card)' }}>
                    <div className="text-secondary mb-3">No active transportation deliveries configured</div>
                    <Button size="sm" onClick={() => setEditingEntry({})}>Configure First Delivery</Button>
                </div>
            ) : (
                activeVehicles.map((entry) => {
                    const calc = computeTransportEntry(entry, projectData);
                    return (
                        <div key={entry.id} className="mb-3" style={{ border: '1px solid var(--app-border-mid)', background: 'var(--app-bg-card)', borderRadius: 4 }}>
                            <div className="d-flex justify-content-between align-items-center p-2" style={{ background: 'var(--app-bg-alt)' }}>
                                <strong>{entry.vehicle?.name || 'Delivery'} - {entry.route?.origin || ''} | {formatNumber(entry.route?.distance_km, 2)} km | {formatNumber(calc.emission_kgCO2e)} kgCO2e</strong>
                                <div className="d-flex gap-2">
                                    <Button size="sm" variant="outline-light" onClick={() => setEditingEntry(entry)}><i className="bi bi-pencil" /></Button>
                                    <Button size="sm" variant="outline-danger" onClick={() => trashEntry(entry.id)}><i className="bi bi-trash" /></Button>
                                </div>
                            </div>
                            <div className="p-2 small d-flex gap-4 flex-wrap">
                                <span>Capacity: {formatNumber(entry.vehicle?.capacity, 2)} t</span>
                                <span>Gross Wt: {formatNumber(entry.vehicle?.gross_weight, 2)} t</span>
                                <span>Empty Wt: {formatNumber(entry.vehicle?.empty_weight, 2)} t</span>
                                <span>EF: {formatNumber(entry.vehicle?.emission_factor, 4)} kgCO2e/t-km</span>
                                <span>Trips: {calc.trips}</span>
                            </div>
                            <Table size="sm" variant="dark" bordered responsive className="mb-0 carbon-desktop-table">
                                <thead>
                                    <tr>
                                        <th>Material</th>
                                        <th>Category</th>
                                        <th className="text-end">kg Factor</th>
                                        <th className="text-end">Quantity (kg)</th>
                                        <th className="text-end">Trips</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {calc.materials.map((material) => (
                                        <tr key={material.uuid}>
                                            <td>{material.name}</td>
                                            <td>{material.category || '-'}</td>
                                            <td className="text-end">{formatNumber(material.kg_factor)}</td>
                                            <td className="text-end">{formatNumber(material.qty_kg, 0)}</td>
                                            <td className="text-end">{material.trips}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </Table>
                        </div>
                    );
                })
            )}

            {editingEntry !== null && (
                <DeliveryModal
                    show={editingEntry !== null}
                    initialData={editingEntry.id ? editingEntry : null}
                    onHide={() => setEditingEntry(null)}
                    onSave={saveEntry}
                />
            )}
        </div>
    );
};

export default TransportationEmissions;
