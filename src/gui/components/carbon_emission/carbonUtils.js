export const STRUCTURE_CHUNKS = [
    ['foundation_data', 'Foundation'],
    ['substructure_data', 'Sub-Structure'],
    ['superstructure_data', 'Super-Structure'],
    ['miscellaneous_data', 'Misc'],
];

export const VEHICLE_TYPES = [
    { key: 'small_cars', label: 'Small Car', defaultEf: 0.1030 },
    { key: 'big_cars', label: 'Big Car', defaultEf: 0.2690 },
    { key: 'two_wheelers', label: 'Two Wheeler', defaultEf: 0.0351 },
    { key: 'o_buses', label: 'Ordinary Buses', defaultEf: 0.4548 },
    { key: 'd_buses', label: 'Deluxe Buses', defaultEf: 0.6064 },
    { key: 'lcv', label: 'LCV', defaultEf: 0.3070 },
    { key: 'hcv', label: 'HCV', defaultEf: 0.5928 },
    { key: 'mcv', label: 'MCV', defaultEf: 0.7375 },
];

export const ENERGY_SOURCES = [
    { label: 'Diesel', unit: 'l/hr', ef: 2.69 },
    { label: 'Electricity (Grid)', unit: 'kW', ef: 0.71 },
    { label: 'Electricity (Solar/Renewable)', unit: 'kW', ef: 0.0 },
    { label: 'Other', unit: 'units/hr', ef: 0.0 },
];

export const DEFAULT_MACHINERY_DATA = [
    { name: 'Backhoe loader (JCB)', source: 'Diesel', rate: 5.0, ef: 2.69 },
    { name: 'Bar bending machine', source: 'Electricity (Grid)', rate: 3.0, ef: 0.71 },
    { name: 'Bar cutting machine', source: 'Electricity (Grid)', rate: 4.0, ef: 0.71 },
    { name: 'Bitumen boiler', source: 'Diesel', rate: 1.0, ef: 2.69 },
    { name: 'Bitumen sprayer', source: 'Diesel', rate: 5.0, ef: 2.69 },
    { name: 'Concrete pump', source: 'Diesel', rate: 12.0, ef: 2.69 },
    { name: 'Crane (crawler)', source: 'Diesel', rate: 12.0, ef: 2.69 },
    { name: 'Crane (mobile)', source: 'Diesel', rate: 8.0, ef: 2.69 },
    { name: 'Dewatering pump', source: 'Diesel', rate: 2.0, ef: 2.69 },
    { name: 'DG set', source: 'Diesel', rate: 4.0, ef: 2.69 },
    { name: 'Grouting mixer', source: 'Electricity (Grid)', rate: 1.0, ef: 0.71 },
    { name: 'Grouting pump', source: 'Electricity (Grid)', rate: 5.0, ef: 0.71 },
    { name: 'Hydraulic excavator', source: 'Diesel', rate: 14.0, ef: 2.69 },
    { name: 'Hydraulic stressing jack', source: 'Electricity (Grid)', rate: 3.0, ef: 0.71 },
    { name: 'Needle Vibrator', source: 'Electricity (Grid)', rate: 1.0, ef: 0.71 },
    { name: 'Paver finisher', source: 'Diesel', rate: 7.0, ef: 2.69 },
    { name: 'Road roller', source: 'Diesel', rate: 4.0, ef: 2.69 },
    { name: 'Rotary piling rig/Hydraulic piling rig', source: 'Diesel', rate: 15.0, ef: 2.69 },
    { name: 'Site office (If Grid electricity is used)', source: 'Electricity (Grid)', rate: 4.0, ef: 0.71 },
    { name: 'Welding machine', source: 'Electricity (Grid)', rate: 4.0, ef: 0.71 },
];

const MASS_UNITS = new Set(['kg', 'kilogram', 'kilograms', 't', 'tonne', 'tonnes', 'mt']);

export const parseNumber = (value, fallback = 0) => {
    if (value === null || value === undefined || value === '') return fallback;
    const parsed = Number(String(value).replace(/,/g, '').replace('%', '').trim());
    return Number.isFinite(parsed) ? parsed : fallback;
};

export const formatNumber = (value, digits = 3) => (
    parseNumber(value).toLocaleString(undefined, {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
    })
);

export const getProjectCountryIso3 = (projectData) => {
    const raw = String(
        projectData?.general_info?.project_country ||
        projectData?.bridge_data?.project_country ||
        projectData?.country ||
        ''
    ).trim().toUpperCase();
    const map = {
        INDIA: 'IND',
        IND: 'IND',
        WORLD: 'WLD',
        GLOBAL: 'WLD',
        WLD: 'WLD',
        USA: 'USA',
        'UNITED STATES': 'USA',
        'UNITED STATES OF AMERICA': 'USA',
    };
    return map[raw] || (raw.length === 3 ? raw : 'WLD');
};

export const carbonUnitDenominator = (carbonEmission = {}) => {
    const raw = carbonEmission.perUnit || carbonEmission.unit || carbonEmission.carbon_unit || '';
    if (!raw) return '';
    const normalized = String(raw).split('—')[0].trim();
    if (normalized.includes('/')) return normalized.split('/').pop().trim();
    return normalized;
};

export const isMassUnit = (unit = '') => MASS_UNITS.has(String(unit).split('—')[0].trim().toLowerCase());

export const defaultKgFactorForRow = (row = {}) => {
    const unit = String(row.unit || row.values?.unit || '').split('—')[0].trim().toLowerCase();
    const saved = parseNumber(row.transport_kg_factor ?? row.values?.transport_kg_factor, null);
    if (saved !== null && saved > 0) return saved;
    if (unit === 'kg' || unit === 'kilogram' || unit === 'kilograms') return 1;
    if (unit === 't' || unit === 'tonne' || unit === 'tonnes' || unit === 'mt') return 1000;
    const conversionFactor = parseNumber(row.conversionFactor ?? row.values?.conversion_factor, 0);
    const denom = carbonUnitDenominator(row.carbonEmission || row.values || {});
    if (conversionFactor > 0 && String(denom).toLowerCase() === 'kg') return conversionFactor;
    return 0;
};

export const getStructureMaterials = (projectData = {}, carbonData = projectData.carbon_emission_data || {}) => {
    const excludedIds = new Set(carbonData.material_emissions_data?.excluded_ids || []);
    return STRUCTURE_CHUNKS.flatMap(([chunkId, category]) => {
        const sections = Array.isArray(projectData[chunkId]) ? projectData[chunkId] : [];
        return sections.flatMap((section, sectionIndex) => {
            const rows = Array.isArray(section?.rows) ? section.rows : [];
            return rows.map((row, rowIndex) => {
                const state = row?.state || {};
                const id = row?.id || `${chunkId}-${sectionIndex}-${rowIndex}`;
                const materialId = `${chunkId}-${id}`;
                const emission = row?.carbonEmission || {};
                const values = row?.values || {};
                const quantity = parseNumber(row?.qty ?? values.quantity);
                const conversionFactor = parseNumber(row?.conversionFactor ?? values.conversion_factor, 1) || 1;
                const emissionFactor = parseNumber(emission.factor ?? values.carbon_emission);
                const explicitInclude = state.included_in_carbon_emission;
                const included = explicitInclude === undefined
                    ? !excludedIds.has(materialId)
                    : explicitInclude === true;
                return {
                    id: materialId,
                    rowId: id,
                    chunkId,
                    category,
                    sectionName: section?.name || '',
                    name: row?.workName || values.material_name || 'Unnamed Material',
                    quantity,
                    unit: row?.unit || values.unit || '',
                    conversion_factor: conversionFactor,
                    emission_factor: emissionFactor,
                    emission_unit: emission.perUnit || values.carbon_unit || '',
                    carbon_source: emission.source || values.carbon_emission_src || '',
                    included,
                    in_trash: state.in_trash === true,
                    carbon_conversion_confirmed: state.carbon_conversion_confirmed === true,
                    kg_factor: defaultKgFactorForRow(row),
                    raw: row,
                };
            }).filter((row) => !row.in_trash);
        });
    });
};

const materialReason = (row) => {
    if (!row.emission_factor) return 'Incomplete Data';
    if (row.conversion_factor <= 0) return 'Incomplete Data';
    if (!row.included) return 'Manually Excluded';
    return '';
};

export const computeMaterialEmissions = (projectData = {}) => {
    const carbonData = projectData.carbon_emission_data || {};
    const rows = getStructureMaterials(projectData, carbonData).map((row) => {
        const total = row.quantity * row.conversion_factor * row.emission_factor;
        const reason = materialReason(row);
        return {
            ...row,
            total_kgCO2e: total,
            reason,
            calculated_included: row.included && reason === '',
        };
    });
    const includedRows = rows.filter((row) => row.calculated_included);
    const cat_totals = STRUCTURE_CHUNKS.reduce((acc, [, label]) => ({ ...acc, [label]: 0 }), {});
    includedRows.forEach((row) => {
        cat_totals[row.category] = (cat_totals[row.category] || 0) + row.total_kgCO2e;
    });
    return {
        rows,
        includedRows,
        excludedRows: rows.filter((row) => !row.calculated_included),
        total_kgCO2e: includedRows.reduce((sum, row) => sum + row.total_kgCO2e, 0),
        included_count: includedRows.length,
        total_count: rows.length,
        cat_totals,
        excluded_ids: rows.filter((row) => !row.included).map((row) => row.id),
    };
};

export const normalizeTransportEntry = (entry = {}) => {
    const vehicle = entry.vehicle || {};
    const route = entry.route || {};
    const selectedMaterials = entry.selectedMaterials || entry.materials || [];
    const capacity = parseNumber(vehicle.capacity);
    const gross = parseNumber(vehicle.gross_weight);
    const empty = parseNumber(vehicle.empty_weight, Math.max(0, gross - capacity));
    const distance = parseNumber(route.distance_km);
    const emissionFactor = parseNumber(vehicle.emission_factor);
    return {
        id: entry.id || crypto.randomUUID(),
        vehicle: {
            name: vehicle.name || vehicle.vehicle_class || '',
            vehicle_class: vehicle.vehicle_class || vehicle.name || '',
            capacity,
            gross_weight: gross,
            empty_weight: empty,
            emission_factor: emissionFactor,
            is_custom: vehicle.is_custom ?? true,
        },
        route: {
            origin: route.origin || entry.origin || '',
            destination: route.destination || 'Site',
            distance_km: distance,
        },
        materials: selectedMaterials.map((item) => ({
            uuid: item.uuid || item.id,
            kg_factor: parseNumber(item.kg_factor ?? item.kgFactor, 0),
            material_name: item.material_name || item.name || '',
        })).filter((item) => item.uuid),
        summary: entry.summary || {},
        meta: entry.meta || {},
        state: entry.state || {},
    };
};

export const computeTrips = (selectedRows, capacityKg, poolMaterials = true) => {
    if (capacityKg <= 0) return 0;
    const buckets = poolMaterials
        ? Object.values(selectedRows.reduce((acc, row) => {
            acc[row.material_name] = (acc[row.material_name] || 0) + row.qty_kg;
            return acc;
        }, {}))
        : selectedRows.map((row) => row.qty_kg);
    return buckets.reduce((sum, kg) => sum + (kg > 0 ? Math.ceil(kg / capacityKg) : 0), 0);
};

export const computeTransportEntry = (entry = {}, projectData = {}) => {
    const normalized = normalizeTransportEntry(entry);
    const materials = getStructureMaterials(projectData);
    const materialById = new Map(materials.map((item) => [item.id, item]));
    const capKg = normalized.vehicle.capacity * 1000;
    const selectedRows = normalized.materials.map((material) => {
        const source = materialById.get(material.uuid);
        const kgFactor = parseNumber(material.kg_factor, source?.kg_factor || 0);
        const qtyKg = (source?.quantity || 0) * kgFactor;
        return {
            uuid: material.uuid,
            name: source?.name || material.material_name || 'Unknown',
            material_name: source?.name || material.material_name || 'Unknown',
            category: source?.category || '',
            unit: source?.unit || '',
            qty: source?.quantity || 0,
            kg_factor: kgFactor,
            qty_kg: qtyKg,
            status: source ? 'ok' : 'removed',
            trips: capKg > 0 && qtyKg > 0 ? Math.ceil(qtyKg / capKg) : 0,
        };
    });
    const trips = computeTrips(selectedRows, capKg, normalized.summary?.pool_materials ?? true);
    const emission = trips * normalized.route.distance_km * normalized.vehicle.emission_factor *
        (normalized.vehicle.gross_weight + normalized.vehicle.empty_weight);
    const totalKg = selectedRows.reduce((sum, row) => sum + row.qty_kg, 0);
    const materialsWithEmissions = selectedRows.map((row) => ({
        ...row,
        emission_kgCO2e: totalKg > 0 ? emission * (row.qty_kg / totalKg) : 0,
    }));
    return {
        entry: normalized,
        materials: materialsWithEmissions,
        trips,
        emission_kgCO2e: emission,
    };
};

export const computeTransportEmissions = (projectData = {}) => {
    const legacy = projectData.carbon_emission_data?.transport_emissions_data?.raw_ui_entries || [];
    const vehicles = (projectData.transport_data?.vehicles || legacy || []).map(normalizeTransportEntry);
    const active = vehicles.filter((entry) => entry.state?.in_trash !== true);
    const computed = active.map((entry) => computeTransportEntry(entry, projectData));
    const cat_totals = STRUCTURE_CHUNKS.reduce((acc, [, label]) => ({ ...acc, [label]: 0 }), {});
    computed.forEach((item) => {
        item.materials.forEach((material) => {
            if (material.status !== 'ok') return;
            cat_totals[material.category] = (cat_totals[material.category] || 0) + material.emission_kgCO2e;
        });
    });
    return {
        vehicles,
        entries: computed.map((item) => ({
            vehicle_name: item.entry.vehicle.name,
            'from-to': item.entry.route.origin,
            distance_km: item.entry.route.distance_km,
            emission_kgCO2e: item.emission_kgCO2e,
            trips: item.trips,
            materials: item.materials,
        })),
        cat_totals,
        total_kgCO2e: computed.reduce((sum, item) => sum + item.emission_kgCO2e, 0),
        active_vehicle_count: active.length,
    };
};

export const computeMachineryDetailedTotal = (rows = []) => rows.reduce((sum, row) => (
    sum + parseNumber(row.rate) * parseNumber(row.hrs ?? row.hours) * parseNumber(row.days) * parseNumber(row.ef)
), 0);

export const computeMachineryLumpsumTotal = (lumpsum = {}) => (
    parseNumber(lumpsum.elec_consumption_per_day ?? lumpsum.elec_kwh_per_day) *
    parseNumber(lumpsum.elec_days) *
    parseNumber(lumpsum.elec_ef) +
    parseNumber(lumpsum.fuel_consumption_per_day ?? lumpsum.fuel_litres_per_day) *
    parseNumber(lumpsum.fuel_days) *
    parseNumber(lumpsum.fuel_ef)
);

export const normalizeMachineryData = (data = {}) => {
    const mode = data.mode === 'lump_sum' ? 'lumpsum' : (data.mode || 'detailed');
    const detailedRows = data.detailed?.rows || data.detailed_entries || [];
    const lumpsum = data.lumpsum || data.lump_sum || {};
    return {
        ...data,
        mode,
        detailed: {
            rows: detailedRows.map((row) => ({
                name: row.name || '',
                source: row.source || 'Diesel',
                rate: parseNumber(row.rate),
                hrs: parseNumber(row.hrs ?? row.hours),
                days: parseNumber(row.days),
                ef: parseNumber(row.ef),
            })),
        },
        lumpsum: {
            elec_consumption_per_day: parseNumber(lumpsum.elec_consumption_per_day ?? lumpsum.elec_kwh_per_day),
            elec_days: parseNumber(lumpsum.elec_days),
            elec_ef: parseNumber(lumpsum.elec_ef),
            fuel_consumption_per_day: parseNumber(lumpsum.fuel_consumption_per_day ?? lumpsum.fuel_litres_per_day),
            fuel_days: parseNumber(lumpsum.fuel_days),
            fuel_ef: parseNumber(lumpsum.fuel_ef),
        },
        remarks: data.remarks || '',
    };
};

export const computeMachineryTotal = (data = {}) => {
    const normalized = normalizeMachineryData(data);
    return normalized.mode === 'lumpsum'
        ? computeMachineryLumpsumTotal(normalized.lumpsum)
        : computeMachineryDetailedTotal(normalized.detailed.rows);
};

/**
 * Resolve the traffic calculation mode the way desktop does
 * (traffic_emissions.py _load_traffic_context): an explicitly stored mode
 * wins; an EMPTY mode falls back to INDIA when bridge_data says the project
 * is in India — deliberately bridge_data only, not general_info, so web and
 * desktop can never disagree on the same project file.
 */
export const resolveTrafficMode = (projectData = {}) => {
    const traffic = projectData.traffic_and_road_data || projectData.traffic_data || {};
    const explicit = String(traffic.mode ?? traffic.calculation_mode ?? '').trim().toUpperCase();
    if (explicit) return explicit;
    const country = String(projectData.bridge_data?.project_country ?? '').trim().toUpperCase();
    return country === 'INDIA' ? 'INDIA' : 'GLOBAL';
};

export const computeTrafficReroutingData = (projectData = {}) => {
    const traffic = projectData.traffic_data || {};
    const carbon = projectData.carbon_emission_data || {};
    const saved = carbon.diversion_emissions_data || carbon.diversion_emissions || {};
    const calculationMode = resolveTrafficMode(projectData);
    const mode = calculationMode === 'INDIA' ? 'Calculate by Vehicle' : 'Enter Directly';
    const factors = saved.emission_factors || saved.factors ||
        VEHICLE_TYPES.reduce((acc, vehicle) => ({ ...acc, [vehicle.key]: vehicle.defaultEf }), {});
    const vehicles = traffic.vehicles || traffic.vehicle_data || {};
    // Same precedence as deriveTrafficAndRoadData: the flat field is the
    // desktop-shaped source of truth; road_params is a web-side sub-object
    // that imports initialize with zeros and must not shadow it.
    const rerouteDistance = parseNumber(
        traffic.additional_reroute_distance_km ??
        traffic.road_params?.additional_reroute_distance_km ??
        saved.reroute_km
    );
    const totalCalculated = VEHICLE_TYPES.reduce((sum, vehicle) => {
        const row = vehicles[vehicle.key] || {};
        const vehiclesPerDay = parseNumber(row.vehicles_per_day ?? row.adt ?? row.ADT);
        return sum + vehiclesPerDay * rerouteDistance * parseNumber(factors[vehicle.key]);
    }, 0);
    const direct = saved.direct_entry?.total_direct_emissions ??
        saved.total_direct_emissions ??
        saved.direct_value ??
        0;
    return {
        mode,
        webMode: mode === 'Calculate by Vehicle' ? 'calculate' : 'direct',
        emission_factors: factors,
        reroute_km: rerouteDistance,
        total_calculated_emissions: totalCalculated,
        direct_entry: {
            total_direct_emissions: parseNumber(direct),
            source: saved.direct_entry?.source || saved.source || '',
            comments: saved.direct_entry?.comments || saved.comments || '',
        },
        remarks: saved.remarks || '',
        total_kgCO2e_per_day: mode === 'Calculate by Vehicle' ? totalCalculated : parseNumber(direct),
    };
};
