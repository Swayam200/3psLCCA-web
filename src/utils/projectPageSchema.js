const VEHICLE_KEYS = [
    'small_cars',
    'big_cars',
    'two_wheelers',
    'o_buses',
    'd_buses',
    'lcv',
    'hcv',
    'mcv',
];

const TRAFFIC_VEHICLE_DEFAULTS = {
    hcv: { pwr: 7.22 },
    mcv: { pwr: 8 },
};

const WPI_COST_KEYS = [
    'petrol',
    'diesel',
    'engine_oil',
    'other_oil',
    'grease',
    'property_damage',
    'tyre_cost',
    'spare_parts',
    'fixed_depreciation',
    'commodity_holding_cost',
    'passenger_cost',
    'crew_cost',
    'fatal',
    'major',
    'minor',
    'vot_cost',
];

const asObject = (value) => (
    value && typeof value === 'object' && !Array.isArray(value) ? value : {}
);

const asArray = (value) => (Array.isArray(value) ? value : []);

const clone = (value) => {
    if (value === undefined) return undefined;
    return JSON.parse(JSON.stringify(value));
};

const numberValue = (value) => {
    if (value === '' || value === null || value === undefined) return null;
    const parsed = Number(String(value).replace(/,/g, '').replace('%', '').trim());
    return Number.isFinite(parsed) ? parsed : null;
};

const normalizeObject = (value) => ({ ...asObject(value) });
const valueOrDefault = (value, fallback) => (
    value === '' || value === null || value === undefined ? fallback : value
);

export const normalizeGeneralInfo = (value, project = {}) => {
    const data = normalizeObject(value);
    return {
        ...data,
        project_name: data.project_name || project.name || '',
        project_country: data.project_country || project.country || '',
        project_currency: data.project_currency || project.currency || '',
        unit_system: data.unit_system || project.unitSystem || '',
    };
};

export const normalizeBridgeData = (value, project = {}) => {
    const data = normalizeObject(value);
    const generalInfo = asObject(project.general_info);
    const legacyLocation = [
        data.location_address,
        data.location_from,
        data.location_via,
        data.location_to,
    ].filter(Boolean).join(', ');

    return {
        ...data,
        bridge_name: data.bridge_name ?? '',
        user_agency: data.user_agency ?? '',
        project_country: data.project_country
            || data.location_country
            || generalInfo.project_country
            || project.country
            || 'INDIA',
        location: data.location || legacyLocation,
        bridge_type: data.bridge_type ?? '',
        span: valueOrDefault(data.span, 0),
        carriageway_width: valueOrDefault(data.carriageway_width, 0),
        num_lanes: valueOrDefault(data.num_lanes, 0),
        vehicle_path_direction: valueOrDefault(data.vehicle_path_direction, 'One Way'),
        footpath: valueOrDefault(
            data.footpath === 'No' ? 'No footpath' : data.footpath,
            'No footpath',
        ),
        design_life: valueOrDefault(data.design_life, 0),
        analysis_period: valueOrDefault(
            data.analysis_period,
            valueOrDefault(data.service_life, 0),
        ),
        year_of_construction: valueOrDefault(
            data.year_of_construction,
            new Date().getFullYear(),
        ),
        duration_construction_months: valueOrDefault(data.duration_construction_months, 0),
        working_days_per_month: valueOrDefault(data.working_days_per_month, 22),
        days_per_month: valueOrDefault(data.days_per_month, 30),
    };
};

export const normalizeFinancialData = (value) => normalizeObject(value);

export const normalizeConstructionSections = (value, sectionKey = 'section') => (
    asArray(value).map((section, sectionIndex) => {
        const sectionData = asObject(section);
        return {
            ...sectionData,
            id: sectionData.id || `${sectionKey}-${sectionIndex + 1}`,
            name: sectionData.name || `Section ${sectionIndex + 1}`,
            rows: asArray(sectionData.rows).map((row, rowIndex) => {
                const rowData = asObject(row);
                return {
                    ...rowData,
                    id: rowData.id || `${sectionKey}-${sectionIndex + 1}-row-${rowIndex + 1}`,
                };
            }),
        };
    })
);

export const normalizeTrafficData = (value) => {
    const data = normalizeObject(value);
    const vehicles = asObject(data.vehicles || data.vehicle_data);
    const normalizedVehicles = VEHICLE_KEYS.reduce((acc, key) => {
        const row = asObject(vehicles[key]);
        const vehiclesPerDay = numberValue(row.vehicles_per_day ?? row.adt ?? row.ADT) || 0;
        const defaultPwr = TRAFFIC_VEHICLE_DEFAULTS[key]?.pwr;
        const shouldRepairLegacyPwr = defaultPwr !== undefined
            && vehiclesPerDay === 0
            && (row.pwr === '' || row.pwr === null || row.pwr === undefined || Number(row.pwr) === 0);
        acc[key] = {
            vehicles_per_day: 0,
            accident_percentage: 0,
            pwr: defaultPwr || 0,
            ...row,
            ...(shouldRepairLegacyPwr ? { pwr: defaultPwr } : {}),
        };
        return acc;
    }, {});
    const alternateRoad = normalizeObject(data.alternate_road);
    const severity = normalizeObject(data.severity);
    const roadParams = normalizeObject(data.road_params);
    const profileYear = String(data.wpi?.selected_profile_year || '')
        || data.wpi_year
        || String(data.wpi_profile || '').match(/\d{4}/)?.[0]
        || '2019';

    const rawWpiData = data.wpi?.data_snapshot?.selected
        || data.wpi_data
        || data.wpi?.data_snapshot
        || data.wpi?.WPI;

    return {
        ...data,
        calculation_mode: data.calculation_mode || data.mode || 'INDIA',
        vehicles: normalizedVehicles,
        force_free_flow: data.force_free_flow ?? data.force_free_flow_off_peak ?? true,
        alternate_road: {
            alternate_road_carriageway: '',
            carriage_width_in_m: 0,
            hourly_capacity: 0,
            ...alternateRoad,
        },
        severity: {
            severity_minor: 0,
            severity_major: 0,
            severity_fatal: 0,
            ...severity,
        },
        road_params: {
            road_roughness_mm_per_km: 2000,
            road_rise_m_per_km: 0,
            road_fall_m_per_km: 0,
            additional_reroute_distance_km: 0,
            additional_travel_time_min: 0,
            crash_rate_accidents_per_million_km: 0,
            work_zone_multiplier: 1,
            ...roadParams,
        },
        num_peak_hours: numberValue(data.num_peak_hours) ?? 0,
        peak_distribution: normalizeObject(data.peak_distribution || data.peak_hour_distribution),
        wpi_profile: data.wpi?.selected_profile_name || data.wpi_profile || '2019',
        wpi_year: profileYear,
        wpi_data: normalizeObject(rawWpiData),
        wpi: data.wpi || (
            data.wpi_profile || data.wpi_data
                ? {
                    selected_profile_name: data.wpi_profile || '',
                    selected_profile_year: profileYear,
                    data_snapshot: normalizeObject(data.wpi_data),
                }
                : null
        ),
    };
};

export const normalizeTransportData = (value, project = {}) => {
    const data = normalizeObject(value);
    const legacyEntries = project?.carbon_emission_data?.transport_emissions_data?.raw_ui_entries
        || project?.carbon_emission_data?.transportation_emissions_data?.raw_ui_entries
        || [];
    const vehicles = asArray(data.vehicles).length > 0 ? data.vehicles : legacyEntries;
    return {
        ...data,
        vehicles: asArray(vehicles).map((entry, index) => {
            const entryData = normalizeObject(entry);
            const vehicle = normalizeObject(entryData.vehicle);
            const route = normalizeObject(entryData.route);
            return {
                ...entryData,
                id: entryData.id || `transport-${index + 1}`,
                vehicle: {
                    name: vehicle.name || vehicle.vehicle_class || '',
                    vehicle_class: vehicle.vehicle_class || vehicle.name || '',
                    capacity: numberValue(vehicle.capacity) ?? 0,
                    gross_weight: numberValue(vehicle.gross_weight) ?? 0,
                    empty_weight: numberValue(vehicle.empty_weight) ?? 0,
                    emission_factor: numberValue(vehicle.emission_factor) ?? 0,
                    is_custom: vehicle.is_custom ?? true,
                },
                route: {
                    origin: route.origin || entryData.origin || '',
                    destination: route.destination || 'Site',
                    distance_km: numberValue(route.distance_km) ?? 0,
                },
                materials: asArray(entryData.materials || entryData.selectedMaterials)
                    .map((item) => {
                        const material = normalizeObject(item);
                        return {
                            uuid: material.uuid || material.id,
                            kg_factor: numberValue(material.kg_factor ?? material.kgFactor) ?? 0,
                            material_name: material.material_name || material.name || '',
                        };
                    })
                    .filter((item) => item.uuid),
                summary: normalizeObject(entryData.summary),
                meta: normalizeObject(entryData.meta),
                state: normalizeObject(entryData.state),
            };
        }),
    };
};

export const normalizeCarbonEmissionData = (value, project = {}) => {
    const data = normalizeObject(value);
    const projectData = project || {};

    // 1. Material Emissions (material_emissions_data)
    const STRUCTURE_CHUNKS = [
        ['foundation_data', 'Foundation'],
        ['substructure_data', 'Sub Structure'],
        ['superstructure_data', 'Super Structure'],
        ['miscellaneous_data', 'Miscellaneous']
    ];
    let allMats = [];
    STRUCTURE_CHUNKS.forEach(([chunkId, category]) => {
        const sections = asArray(projectData[chunkId]);
        sections.forEach(section => {
            const compName = section.name || '';
            const items = asArray(section.rows);
            items.filter(item => !asObject(item.state).in_trash).forEach(item => {
                allMats.push({
                    id: `${chunkId}-${item.id}`,
                    raw_id: item.id,
                    name: item.workName || 'Unnamed Material',
                    category: category,
                    component: compName,
                    quantity: numberValue(item.qty) || 0,
                    unit: item.unit || '',
                    cf: numberValue(item.conversionFactor) ?? 1.0,
                    ef: item.carbonEmission ? (numberValue(item.carbonEmission.factor) || 0) : 0,
                    chunkId: chunkId
                });
            });
        });
    });

    const materialData = normalizeObject(data.material_emissions_data);
    const excludedIdsList = asArray(materialData.excluded_ids || materialData.excluded);
    const excludedSet = new Set(excludedIdsList);

    const matRows = allMats.map(m => ({
        id: m.id,
        name: m.name,
        category: m.category,
        component: m.component,
        quantity: m.quantity,
        unit: m.unit,
        conversion_factor: m.cf,
        emission_factor: m.ef,
        total_kgCO2e: m.quantity * m.cf * m.ef,
        included: !excludedSet.has(m.id),
    }));
    const includedRows = matRows.filter(row => row.included);
    const calculatedCategoryTotals = includedRows.reduce((acc, row) => {
        acc[row.category] = (acc[row.category] || 0) + row.total_kgCO2e;
        return acc;
    }, {
        Foundation: 0,
        'Sub Structure': 0,
        'Super Structure': 0,
        Miscellaneous: 0,
    });
    const materialTotal = includedRows.reduce((sum, row) => sum + row.total_kgCO2e, 0);

    const nextMaterialData = {
        ...materialData,
        excluded_ids: Array.from(excludedSet),
        rows: matRows,
        category_totals: calculatedCategoryTotals,
        total_kgCO2e: materialTotal,
    };

    // 2. Transportation Emissions (transport_emissions_data / transportation_emissions_data)
    const transportData = normalizeObject(data.transport_emissions_data || data.transportation_emissions_data);
    const rawEntries = asArray(transportData.raw_ui_entries || transportData.deliveries);

    // Create lookup by raw_id and prefixed_id
    const matsLookup = {};
    allMats.forEach(m => {
        matsLookup[m.raw_id] = m;
        matsLookup[m.id] = m;
    });

    const updatedEntries = rawEntries.map(entry => {
        const vehicle = asObject(entry.vehicle);
        const route = asObject(entry.route);
        const entryMats = asArray(entry.selectedMaterials || entry.materials);

        const updatedEntryMats = entryMats.map(em => {
            const currentItem = matsLookup[em.id];
            if (currentItem) {
                return {
                    ...em,
                    name: currentItem.name || em.name,
                    quantity: currentItem.quantity,
                    unit: currentItem.unit || em.unit,
                    kgFactor: currentItem.cf,
                };
            }
            return em;
        });

        const cap = numberValue(vehicle.capacity) || 0;
        const gross = numberValue(vehicle.gross_weight) || 0;
        const empty = numberValue(vehicle.empty_weight) || 0;
        const dist = numberValue(route.distance_km) || 0;
        const ef = numberValue(vehicle.emission_factor) || 0;

        const totalWeightT = updatedEntryMats.reduce((sum, m) => sum + ((numberValue(m.quantity) || 0) * (numberValue(m.kgFactor) || 1) / 1000), 0);
        const trips = cap > 0 ? Math.ceil(totalWeightT / cap) : 0;
        const emission = (gross + empty) * trips * dist * ef;

        return {
            ...entry,
            vehicle,
            route,
            selectedMaterials: updatedEntryMats,
            emission_kgCO2e: emission,
            materials: updatedEntryMats,
            vehicle_name: vehicle.name,
            origin: route.origin,
            distance_km: route.distance_km,
        };
    });

    const transportTotal = updatedEntries.length > 0
        ? updatedEntries.reduce((sum, entry) => sum + (entry.emission_kgCO2e || 0), 0)
        : (numberValue(transportData.total_kgCO2e) || 0);

    const nextTransportData = {
        ...transportData,
        raw_ui_entries: updatedEntries,
        entries: updatedEntries.map(entry => ({
            vehicle_name: entry.vehicle?.name,
            origin: entry.route?.origin,
            distance_km: entry.route?.distance_km,
            emission_kgCO2e: entry.emission_kgCO2e,
            materials: entry.selectedMaterials
        })),
        total_kgCO2e: transportTotal,
        active_vehicle_count: updatedEntries.length,
    };

    // 3. Machinery Emissions (machinery_emissions_data)
    const machData = normalizeObject(data.machinery_emissions_data);
    const machMode = machData.mode || 'detailed';
    const detailedEntries = asArray(machData.detailed_entries || machData.entries);
    const ls = asObject(machData.lump_sum);

    let machineryTotal = 0;
    if (machMode === 'detailed' && detailedEntries.length > 0) {
        machineryTotal = detailedEntries.reduce((sum, e) => {
            const r = numberValue(e.rate) || 0;
            const h = numberValue(e.hours) || 0;
            const d = numberValue(e.days) || 0;
            const ef = numberValue(e.ef || e.emission_factor) || 0;
            return sum + (r * h * d * ef);
        }, 0);
    } else if (machMode === 'lump_sum' && (ls.elec_kwh_per_day || ls.fuel_litres_per_day)) {
        const elec_kwh = numberValue(ls.elec_kwh_per_day) || 0;
        const elec_days = numberValue(ls.elec_days) || 0;
        const elec_ef = numberValue(ls.elec_ef !== undefined ? ls.elec_ef : 0.71) ?? 0.71;
        const fuel_litres = numberValue(ls.fuel_litres_per_day) || 0;
        const fuel_days = numberValue(ls.fuel_days) || 0;
        const fuel_ef = numberValue(ls.fuel_ef !== undefined ? ls.fuel_ef : 2.69) ?? 2.69;
        machineryTotal = (elec_kwh * elec_days * elec_ef) + (fuel_litres * fuel_days * fuel_ef);
    } else {
        machineryTotal = numberValue(machData.total_kgCO2e) || 0;
    }

    const nextMachData = {
        ...machData,
        total_kgCO2e: machineryTotal,
    };

    // 4. Traffic Diversion Emissions (diversion_emissions_data / diversion_emissions)
    const defaultFactors = {
        small_cars: 0.1030,
        big_cars: 0.2690,
        two_wheelers: 0.0351,
        o_buses: 0.4548,
        d_buses: 0.6064,
        lcv: 0.3070,
        hcv: 0.5928,
        mcv: 0.7375
    };

    const diversionData = normalizeObject(data.diversion_emissions_data || data.diversion_emissions);
    const divMode = diversionData.mode || 'direct';
    const rerouteKm = numberValue(diversionData.reroute_km) || 0;
    const divFactors = {
        ...defaultFactors,
        ...asObject(diversionData.factors)
    };
    const directValue = numberValue(diversionData.direct_value) || 0;

    const trafficData = asObject(projectData.traffic_data);
    let totalPerDay = 0;
    if (divMode === 'calculate') {
        const getVehicleAdt = (td, key) => {
            const vehicles = asObject(td.vehicles || td.vehicle_data);
            const row = asObject(vehicles[key]);
            const vpdLegacy = asObject(td.vehicles_per_day);
            return numberValue(
                row.vehicles_per_day ?? 
                row.adt ?? 
                row.ADT ?? 
                vpdLegacy[key]
            ) || 0;
        };

        const hasAdt = Object.keys(defaultFactors).some(key => getVehicleAdt(trafficData, key) > 0);
        if (hasAdt && rerouteKm > 0) {
            totalPerDay = Object.keys(defaultFactors).reduce((sum, key) => {
                const adt = getVehicleAdt(trafficData, key);
                const factor = numberValue(divFactors[key]) || 0;
                return sum + (adt * rerouteKm * factor);
            }, 0);
        } else {
            totalPerDay = numberValue(diversionData.total_kgCO2e_per_day ?? diversionData.total_calculated_emissions) || 0;
        }
    } else {
        totalPerDay = directValue || numberValue(diversionData.total_kgCO2e_per_day ?? diversionData.total_direct_emissions) || 0;
    }

    const desktopMode = divMode === 'calculate' ? 'Calculate by Vehicle' : 'Enter Directly';

    const nextDiversionData = {
        ...diversionData,
        mode: divMode,
        calculation_mode: desktopMode,
        reroute_km: rerouteKm,
        factors: divFactors,
        direct_value: directValue,
        total_kgCO2e_per_day: totalPerDay,
        total_calculated_emissions: divMode === 'calculate' ? totalPerDay : 0,
        total_direct_emissions: divMode === 'direct' ? totalPerDay : 0,
    };

    // 5. Social Cost of Carbon (social_cost_data)
    const socialData = normalizeObject(data.social_cost_data);
    const sccMode = socialData.mode || socialData.source || 'NITI Aayog';
    const inrRate = numberValue(socialData.inr_rate !== undefined ? socialData.inr_rate : 1.0) ?? 1.0;
    const usdRate = numberValue(socialData.usd_rate !== undefined ? socialData.usd_rate : 83.0) ?? 83.0;
    const ssp = socialData.ssp || 'SSP2 (Middle of the Road)';
    const rcp = socialData.rcp || 'RCP 4.5 (Intermediate)';
    const customScc = numberValue(socialData.custom_scc !== undefined ? socialData.custom_scc : socialData.custom?.entered_value !== undefined ? socialData.custom.entered_value : 0.05) ?? 0.05;

    // The Social Cost page resolves Ricke-mode values itself from the
    // per-country dataset (an async fetch a sync normalizer cannot do) and
    // stores the result. When those params are present, echo the stored cost
    // verbatim — recomputing from the legacy stub below would corrupt the
    // precise value and break normalize-idempotence (the carbon-freeze
    // invariant). The stub survives only for legacy rows without params.
    const hasRickeParams = socialData.ricke && typeof socialData.ricke === 'object';

    let sccVal;
    if (sccMode === 'NITI Aayog') {
        sccVal = 6.3936 * inrRate;
    } else if (sccMode === 'K. Ricke et al. (Country-Level)' && hasRickeParams) {
        sccVal = numberValue(
            socialData.calculated_scc_local !== undefined
                ? socialData.calculated_scc_local
                : socialData.result?.cost_of_carbon_local
        ) ?? 0;
    } else if (sccMode === 'K. Ricke et al. (Country-Level)') {
        const RICKE_SCC_TABLE = {
            "SSP1 (Sustainability)|RCP 2.6 (Low Warming)": 0.085,
            "SSP1 (Sustainability)|RCP 4.5 (Intermediate)": 0.095,
            "SSP2 (Middle of the Road)|RCP 4.5 (Intermediate)": 0.110,
            "SSP2 (Middle of the Road)|RCP 6.0 (High)": 0.135,
            "SSP3 (Regional Rivalry)|RCP 8.5 (Extreme)": 0.185,
            "SSP5 (Fossil-fueled Development)|RCP 8.5 (Extreme)": 0.210,
        };
        const key = `${ssp}|${rcp}`;
        const baseUsd = RICKE_SCC_TABLE[key] !== undefined ? RICKE_SCC_TABLE[key] : 0.1;
        sccVal = baseUsd * usdRate;
    } else {
        sccVal = customScc;
    }

    const nextSocialData = {
        ...socialData,
        mode: sccMode,
        inr_rate: inrRate,
        usd_rate: usdRate,
        ssp,
        rcp,
        custom_scc: customScc,
        calculated_scc_local: sccVal,
        cost_of_carbon_local: sccVal,
        result: {
            ...asObject(socialData.result),
            cost_of_carbon_local: sccVal,
        }
    };

    return {
        ...data,
        material_emissions_data: nextMaterialData,
        transport_emissions_data: nextTransportData,
        transportation_emissions_data: nextTransportData,
        machinery_emissions_data: nextMachData,
        diversion_emissions_data: nextDiversionData,
        diversion_emissions: nextDiversionData,
        social_cost_data: nextSocialData,
    };
};

export const normalizeMaintenanceData = (value) => normalizeObject(value);

export const normalizeDemolitionData = (value) => {
    const data = normalizeObject(value);
    return {
        ...data,
        demolition_cost_pct: data.demolition_cost_pct ?? numberValue(data.demolition_cost) ?? 0,
        demolition_carbon_cost_pct: data.demolition_carbon_cost_pct ?? numberValue(data.demolition_carbon_cost) ?? 0,
    };
};

export const normalizeRecyclingData = (value) => {
    const data = normalizeObject(value);
    const included = asArray(data.included);
    const totalRecoveredValue = included.reduce((sum, item) => {
        return sum + (numberValue(asObject(item).recoveredValue) || 0);
    }, 0);
    return {
        ...data,
        included,
        excluded: asArray(data.excluded),
        total_recovered_value: totalRecoveredValue,
    };
};

export const normalizeOutputsData = (value) => normalizeObject(value);

const SECTION_NORMALIZERS = {
    general_info: normalizeGeneralInfo,
    bridge_data: normalizeBridgeData,
    financial_data: normalizeFinancialData,
    traffic_data: normalizeTrafficData,
    transport_data: normalizeTransportData,
    foundation_data: (value) => normalizeConstructionSections(value, 'foundation'),
    substructure_data: (value) => normalizeConstructionSections(value, 'substructure'),
    superstructure_data: (value) => normalizeConstructionSections(value, 'superstructure'),
    miscellaneous_data: (value) => normalizeConstructionSections(value, 'miscellaneous'),
    carbon_emission_data: normalizeCarbonEmissionData,
    maintenance_repair_data: normalizeMaintenanceData,
    demolition_data: normalizeDemolitionData,
    recycling_data: normalizeRecyclingData,
    outputs_data: normalizeOutputsData,
};

export const normalizeProjectSection = (sectionKey, value, project = {}) => {
    const normalizer = SECTION_NORMALIZERS[sectionKey];
    return normalizer ? normalizer(clone(value), project) : clone(value);
};

const required = (data, keys) => keys.filter((key) => (
    data[key] === '' || data[key] === null || data[key] === undefined
));

export const validateGeneralInfoData = (value) => {
    const missing = required(asObject(value), ['project_name']);
    return missing.map(() => 'Project Name is required.');
};

export const validateBridgeData = (value) => {
    const data = asObject(value);
    const errors = required(data, [
        'design_life',
        'analysis_period',
        'year_of_construction',
        'duration_construction_months',
    ]).map((key) => `${key.replaceAll('_', ' ')} is required.`);

    for (const key of ['design_life', 'analysis_period', 'duration_construction_months']) {
        const number = numberValue(data[key]);
        if (number !== null && number <= 0) errors.push(`${key.replaceAll('_', ' ')} must be greater than zero.`);
    }

    const daysPerMonth = numberValue(data.days_per_month);
    if (daysPerMonth !== null && (daysPerMonth < 29 || daysPerMonth > 31)) {
        errors.push('days per month must be between 29 and 31.');
    }
    return errors;
};

export const getBridgeWarnings = (value) => {
    const data = asObject(value);
    const warnings = [];
    const workingDays = numberValue(data.working_days_per_month);
    const daysPerMonth = numberValue(data.days_per_month);
    const yearOfConstruction = numberValue(data.year_of_construction);

    if (
        workingDays !== null
        && daysPerMonth !== null
        && workingDays > 0
        && daysPerMonth > 0
        && workingDays > daysPerMonth
    ) {
        warnings.push('working days per month cannot exceed days per month.');
    }
    if (yearOfConstruction !== null && yearOfConstruction < new Date().getFullYear()) {
        warnings.push('year of construction is in the past; confirm this is intentional.');
    }
    return warnings;
};

export const validateFinancialData = (value) => {
    const data = asObject(value);
    const errors = required(data, [
        'discount_rate',
        'inflation_rate',
        'interest_rate',
        'investment_ratio',
    ]).map((key) => `${key.replaceAll('_', ' ')} is required.`);

    for (const key of ['discount_rate', 'inflation_rate', 'interest_rate']) {
        const number = numberValue(data[key]);
        if (number !== null && number < 0) errors.push(`${key.replaceAll('_', ' ')} cannot be negative.`);
    }
    const investmentRatio = numberValue(data.investment_ratio);
    if (investmentRatio !== null && (investmentRatio < 0 || investmentRatio > 1)) {
        errors.push('investment ratio must be between 0 and 1.');
    }
    return errors;
};

export const validateTrafficData = (value) => {
    const data = normalizeTrafficData(value);
    const errors = [];
    if (!['INDIA', 'GLOBAL'].includes(data.calculation_mode)) {
        errors.push('Calculation mode must be INDIA or GLOBAL.');
        return errors;
    }
    if (data.calculation_mode === 'GLOBAL') {
        if (numberValue(data.road_user_cost_per_day) === null) {
            errors.push('Road user cost per day is required in GLOBAL mode.');
        }
        return errors;
    }

    const totalAdt = VEHICLE_KEYS.reduce((sum, key) => {
        return sum + (numberValue(data.vehicles[key]?.vehicles_per_day) || 0);
    }, 0);
    if (totalAdt > 0) {
        const accidentTotal = VEHICLE_KEYS.reduce((sum, key) => {
            return sum + (numberValue(data.vehicles[key]?.accident_percentage) || 0);
        }, 0);
        if (Math.abs(accidentTotal - 100) > 0.1) {
            errors.push('Vehicle accident percentages must sum to 100.');
        }
        for (const key of ['hcv', 'mcv']) {
            const row = data.vehicles[key];
            if ((numberValue(row.vehicles_per_day) || 0) > 0 && (numberValue(row.pwr) || 0) <= 0) {
                errors.push(`Passenger Weight Ratio (PWR) for ${key.toUpperCase()} must be greater than zero when that vehicle type has traffic.`);
            }
        }
    }

    const severityTotal = ['severity_minor', 'severity_major', 'severity_fatal'].reduce((sum, key) => {
        return sum + (numberValue(data.severity[key]) || 0);
    }, 0);
    if (severityTotal > 0 && Math.abs(severityTotal - 100) > 0.001) {
        errors.push('Accident severity percentages must sum to 100.');
    }
    if (!data.alternate_road.alternate_road_carriageway) {
        errors.push('Alternate road carriageway is required in INDIA mode.');
    }
    if ((numberValue(data.alternate_road.carriage_width_in_m) || 0) <= 0) {
        errors.push('Alternate road carriage width must be greater than zero.');
    }
    if ((numberValue(data.alternate_road.hourly_capacity) || 0) <= 0) {
        errors.push('Alternate road hourly capacity must be greater than zero.');
    }
    if ((numberValue(data.road_params.road_roughness_mm_per_km) || 0) < 2000) {
        errors.push('Road roughness must be at least 2000 mm/km.');
    }
    const workZoneMultiplier = numberValue(data.road_params.work_zone_multiplier);
    if (workZoneMultiplier === null || workZoneMultiplier < 0 || workZoneMultiplier > 1) {
        errors.push('Work zone multiplier must be between 0 and 1.');
    }
    const activePeaks = Object.entries(data.peak_distribution)
        .filter(([key]) => key.startsWith('peak_hour_'))
        .slice(0, data.num_peak_hours)
        .map(([, value]) => numberValue(value) || 0);
    if (totalAdt > 0 && activePeaks.some((value) => value <= 0)) {
        errors.push('Each configured peak hour traffic proportion must be greater than zero.');
    }
    if (activePeaks.reduce((sum, value) => sum + value, 0) > 1 + 1e-6) {
        errors.push('Peak hour traffic proportions must not exceed 100%.');
    }
    if (!data.wpi_profile || Object.keys(data.wpi_data).length === 0) {
        errors.push('A WPI profile is required in INDIA mode.');
    } else {
        const zeroWpiCell = VEHICLE_KEYS.some((vehicle) => (
            WPI_COST_KEYS.some((key) => (numberValue(data.wpi_data?.[vehicle]?.[key]) || 0) <= 0)
        ));
        if (zeroWpiCell) errors.push('WPI adjustment factor values must be greater than zero.');
    }
    return errors;
};

const validateLifecyclePercentages = (value, requiredKeys, positiveKeys) => {
    const data = asObject(value);
    const errors = required(data, requiredKeys).map((key) => `${key.replaceAll('_', ' ')} is required.`);
    for (const key of requiredKeys) {
        const number = numberValue(data[key]);
        if (number !== null && number < 0) errors.push(`${key.replaceAll('_', ' ')} cannot be negative.`);
    }
    for (const key of positiveKeys) {
        const number = numberValue(data[key]);
        if (number !== null && number <= 0) errors.push(`${key.replaceAll('_', ' ')} must be greater than zero.`);
    }
    return errors;
};

export const validateMaintenanceData = (value) => validateLifecyclePercentages(
    value,
    [
        'routine_inspection_cost',
        'routine_inspection_freq',
        'periodic_maintenance_cost',
        'periodic_maintenance_carbon_cost',
        'periodic_maintenance_freq',
        'major_inspection_cost',
        'major_inspection_freq',
        'major_repair_cost',
        'major_repair_carbon_cost',
        'major_repair_freq',
        'major_repair_duration',
        'bearing_exp_joint_cost',
        'bearing_exp_joint_freq',
        'bearing_exp_joint_duration',
    ],
    [
        'routine_inspection_freq',
        'periodic_maintenance_freq',
        'major_inspection_freq',
        'major_repair_freq',
        'major_repair_duration',
        'bearing_exp_joint_freq',
        'bearing_exp_joint_duration',
    ],
);

export const validateDemolitionData = (value) => validateLifecyclePercentages(
    value,
    ['demolition_cost', 'demolition_carbon_cost', 'demolition_duration'],
    ['demolition_duration'],
);
