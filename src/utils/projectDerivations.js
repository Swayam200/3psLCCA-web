import { normalizeProjectData } from './projectSchema.js';
import {
    pickTrafficField, TRAFFIC_ALTERNATE_ROAD_KEYS, TRAFFIC_SEVERITY_KEYS, TRAFFIC_ROAD_PARAM_KEYS,
} from './projectPageSchema.js';
import { recyclingChunkData } from './recyclingDerivations.js';
import {
    computeMachineryTotal,
    computeMaterialEmissions,
    computeTrafficReroutingData,
    resolveTrafficMode,
    computeTransportEmissions,
    normalizeMachineryData,
    parseNumber,
} from '../gui/components/carbon_emission/carbonUtils.js';

const VEHICLE_TYPES = [
    'small_cars',
    'big_cars',
    'two_wheelers',
    'o_buses',
    'd_buses',
    'lcv',
    'hcv',
    'mcv',
];

export const getSectionsTotal = (sections) => {
    if (!Array.isArray(sections)) return 0;
    return sections.reduce((sum, section) => {
        const rows = Array.isArray(section?.rows) ? section.rows : [];
        return sum + rows.reduce((rowSum, row) => {
            if (row?.state?.in_trash) return rowSum;
            return rowSum + parseNumber(row?.rate) * parseNumber(row?.qty);
        }, 0);
    }, 0);
};

export const getRecyclingTotal = (recyclingData) => {
    const included = Array.isArray(recyclingData?.included) ? recyclingData.included : [];
    return included.reduce((sum, item) => sum + parseNumber(item?.recoveredValue), 0);
};

export const getMaterialCarbonRows = (projectData) => {
    const project = normalizeProjectData(projectData);
    return computeMaterialEmissions(project).rows;
};

export const deriveConstructionWorkData = (projectData) => {
    const project = normalizeProjectData(projectData);
    const totals = {
        Foundation: { total: getSectionsTotal(project.foundation_data), rows: project.foundation_data },
        'Sub Structure': { total: getSectionsTotal(project.substructure_data), rows: project.substructure_data },
        'Super Structure': { total: getSectionsTotal(project.superstructure_data), rows: project.superstructure_data },
        Miscellaneous: { total: getSectionsTotal(project.miscellaneous_data), rows: project.miscellaneous_data },
    };
    const grandTotal = Object.values(totals).reduce((sum, section) => sum + section.total, 0);

    return {
        ...(project.construction_work_data || {}),
        ...totals,
        'Super-Structure': totals['Super Structure'],
        grand_total: grandTotal,
    };
};

export const deriveCarbonEmissionData = (projectData) => {
    const project = normalizeProjectData(projectData);
    const carbonData = project.carbon_emission_data || {};
    const material = computeMaterialEmissions(project);
    const stripRaw = (row) => {
        const next = { ...row };
        delete next.raw;
        return next;
    };
    const transportComputed = computeTransportEmissions(project);
    const machineryComputed = normalizeMachineryData(carbonData.machinery_emissions_data || {});
    const trafficRerouting = computeTrafficReroutingData(project);
    const existingMaterial = carbonData.material_emissions_data || {};
    const transport = carbonData.transport_emissions_data || carbonData.transportation_emissions_data || {};
    const machinery = carbonData.machinery_emissions_data || {};
    const social = carbonData.social_cost_data || {};
    const socialCostLocal = parseNumber(
        social.result?.cost_of_carbon_local ??
        social.cost_of_carbon_local ??
        social.calculated_scc_local
    );

    return {
        ...carbonData,
        material_emissions_data: {
            ...existingMaterial,
            rows: material.rows.map(stripRaw),
            included_items: material.includedRows.map(stripRaw),
            excluded_items: material.excludedRows.map(stripRaw),
            category_totals: material.cat_totals,
            cat_totals: material.cat_totals,
            total_kgCO2e: material.total_kgCO2e,
            included_count: material.included_count,
            total_count: material.total_count,
            excluded_ids: material.excluded_ids,
        },
        transport_emissions_data: {
            ...transport,
            ...transportComputed,
            total_kgCO2e: transportComputed.total_kgCO2e,
        },
        transportation_emissions_data: {
            ...transport,
            ...transportComputed,
            total_kgCO2e: transportComputed.total_kgCO2e,
        },
        machinery_emissions_data: {
            ...machinery,
            ...machineryComputed,
            total_kgCO2e: computeMachineryTotal(machineryComputed),
        },
        diversion_emissions_data: {
            ...(carbonData.diversion_emissions_data || carbonData.diversion_emissions || {}),
            ...trafficRerouting,
        },
        diversion_emissions: {
            ...(carbonData.diversion_emissions || carbonData.diversion_emissions_data || {}),
            ...trafficRerouting,
        },
        social_cost_data: {
            ...social,
            calculated_scc_local: socialCostLocal,
            cost_of_carbon_local: socialCostLocal,
            result: {
                ...(social.result || {}),
                cost_of_carbon_local: socialCostLocal,
            },
        },
    };
};

export const deriveDemolitionData = (projectData) => {
    const project = normalizeProjectData(projectData);
    const demolition = project.demolition_data || {};
    return {
        ...demolition,
        demolition_cost_pct: parseNumber(demolition.demolition_cost_pct ?? demolition.demolition_cost),
        demolition_carbon_cost_pct: parseNumber(demolition.demolition_carbon_cost_pct ?? demolition.demolition_carbon_cost),
    };
};

export const deriveRecyclingData = (projectData) => {
    const project = normalizeProjectData(projectData);
    // Desktop parity: the recovered (salvage) value is DERIVED from the
    // construction material rows at calculation time — the recycling chunk
    // only stores the computed summary (desktop recycling/main.py). The
    // legacy saved `included` list is used only when the project has no
    // material rows at all (hand-entered data from older web versions).
    const computed = recyclingChunkData(
        project,
        project.general_info?.project_currency || project.currency || '',
    );
    const legacyTotal = getRecyclingTotal(project.recycling_data);
    return {
        ...(project.recycling_data || {}),
        ...computed,
        total_recovered_value: computed.total_count > 0
            ? computed.total_recovered_value
            : legacyTotal,
    };
};

/**
 * Desktop-shaped (flat) view of the traffic data for consumers that read
 * the desktop chunk contract (report, LaTeX runtime): the web form's
 * sub-objects are copied onto the flat keys they mirror, and web-only names
 * get their desktop aliases. Flat keys that already hold a real value are
 * left untouched, so desktop-imported projects are unchanged.
 */
export const flattenTrafficData = (trafficData = {}) => {
    const traffic = { ...(trafficData || {}) };
    const groups = [
        [traffic.alternate_road, TRAFFIC_ALTERNATE_ROAD_KEYS],
        [traffic.severity, TRAFFIC_SEVERITY_KEYS],
        [traffic.road_params, TRAFFIC_ROAD_PARAM_KEYS],
    ];
    groups.forEach(([group, keys]) => {
        if (!group || typeof group !== 'object') return;
        keys.forEach((key) => {
            const value = pickTrafficField(group[key], traffic[key]);
            if (value !== undefined) traffic[key] = value;
        });
    });
    const filled = (value) => value && typeof value === 'object' && Object.keys(value).length > 0;
    if (!filled(traffic.vehicle_data) && filled(traffic.vehicles)) traffic.vehicle_data = traffic.vehicles;
    if (!filled(traffic.peak_hour_distribution) && filled(traffic.peak_distribution)) traffic.peak_hour_distribution = traffic.peak_distribution;
    if (traffic.mode === undefined && traffic.calculation_mode !== undefined) traffic.mode = traffic.calculation_mode;
    if (traffic.force_free_flow_off_peak === undefined && traffic.force_free_flow !== undefined) traffic.force_free_flow_off_peak = traffic.force_free_flow;
    return traffic;
};

export const deriveTrafficAndRoadData = (projectData) => {
    const project = normalizeProjectData(projectData);
    const traffic = project.traffic_data || {};
    const vehicleData = traffic.vehicle_data || traffic.vehicles || {};
    const vehiclesPerDay = traffic.vehicles_per_day || {};
    const roadParams = traffic.road_params || {};
    const alternateRoad = traffic.alternate_road || {};
    const severity = traffic.severity || {};

    // Per-vehicle rerouting emission factors live on the Traffic Rerouting
    // Emissions page data (desktop diversion_emissions chunk); the engine
    // multiplies them by vehicles/day × reroute km. Resolve them here so
    // every vehicle row carries the value the adapter reads first.
    const reroutingFactors = computeTrafficReroutingData(project).emission_factors || {};

    const normalizedVehicles = VEHICLE_TYPES.reduce((acc, key) => {
        const row = vehicleData[key] || {};
        const emissionFactor = parseNumber(
            row.carbon_emissions_kgCO2e_per_km ?? row.emission_factor ?? row.ef ?? reroutingFactors[key],
        );
        acc[key] = {
            vehicles_per_day: parseNumber(row.vehicles_per_day ?? row.adt ?? row.ADT ?? vehiclesPerDay[key]),
            accident_percentage: parseNumber(row.accident_percentage),
            pwr: row.pwr === '' || row.pwr === undefined ? undefined : parseNumber(row.pwr),
            adt: parseNumber(row.adt ?? row.ADT ?? vehiclesPerDay[key]),
            traffic_growth: parseNumber(row.traffic_growth ?? row.growth_rate ?? traffic.traffic_growth),
            velocity: parseNumber(row.velocity ?? row.speed),
            VOC: parseNumber(row.VOC ?? row.voc),
            occupancy: parseNumber(row.occupancy),
            carbon_emissions_kgCO2e_per_km: emissionFactor,
            emission_factor: emissionFactor,
        };
        return acc;
    }, {});

    const wpiSnapshot = traffic.wpi || (
        traffic.wpi_profile || traffic.wpi_data
            ? {
                selected_profile_name: traffic.wpi_profile || '',
                selected_profile_year: traffic.wpi_year || '',
                data_snapshot: traffic.wpi_data || {},
            }
            : null
    );

    return {
        ...traffic,
        mode: resolveTrafficMode(projectData),
        vehicle_data: normalizedVehicles,
        // The traffic form stores these in sub-objects (alternate_road,
        // severity, road_params); desktop files use the flat keys. The
        // normalized sub-object already reconciles the two (pickTrafficField),
        // so it is the source of truth here; the flat key is the fallback.
        severity_minor: parseNumber(pickTrafficField(severity.severity_minor ?? severity.minor, traffic.severity_minor)),
        severity_major: parseNumber(pickTrafficField(severity.severity_major ?? severity.major, traffic.severity_major)),
        severity_fatal: parseNumber(pickTrafficField(severity.severity_fatal ?? severity.fatal, traffic.severity_fatal)),
        carriage_width_in_m: parseNumber(pickTrafficField(alternateRoad.carriage_width_in_m, traffic.carriage_width_in_m ?? roadParams.carriage_width_in_m)),
        hourly_capacity: parseNumber(pickTrafficField(alternateRoad.hourly_capacity, traffic.hourly_capacity ?? roadParams.hourly_capacity)),
        alternate_road_carriageway: pickTrafficField(alternateRoad.alternate_road_carriageway, traffic.alternate_road_carriageway) ?? '',
        alternate_road_speed: parseNumber(traffic.alternate_road_speed ?? alternateRoad.alternate_road_speed),
        road_roughness_mm_per_km: parseNumber(pickTrafficField(roadParams.road_roughness_mm_per_km, traffic.road_roughness_mm_per_km)),
        road_rise_m_per_km: parseNumber(pickTrafficField(roadParams.road_rise_m_per_km, traffic.road_rise_m_per_km)),
        road_fall_m_per_km: parseNumber(pickTrafficField(roadParams.road_fall_m_per_km, traffic.road_fall_m_per_km)),
        additional_reroute_distance_km: parseNumber(pickTrafficField(roadParams.additional_reroute_distance_km, traffic.additional_reroute_distance_km)),
        additional_travel_time_min: parseNumber(pickTrafficField(roadParams.additional_travel_time_min, traffic.additional_travel_time_min)),
        crash_rate_accidents_per_million_km: parseNumber(pickTrafficField(roadParams.crash_rate_accidents_per_million_km, traffic.crash_rate_accidents_per_million_km)),
        work_zone_multiplier: parseNumber(pickTrafficField(roadParams.work_zone_multiplier, traffic.work_zone_multiplier)),
        force_free_flow_off_peak: Boolean(traffic.force_free_flow_off_peak ?? traffic.force_free_flow),
        road_user_cost_per_day: parseNumber(traffic.road_user_cost_per_day),
        peak_hour_distribution: traffic.peak_hour_distribution || traffic.peak_distribution || {},
        wpi: wpiSnapshot,
    };
};

export const buildCalculationProjectInputs = (projectData) => {
    const project = normalizeProjectData(projectData);
    return {
        ...project,
        bridge_data: project.bridge_data || {},
        financial_data: project.financial_data || {},
        traffic_data: project.traffic_data || {},
        traffic_and_road_data: deriveTrafficAndRoadData(project),
        construction_work_data: deriveConstructionWorkData(project),
        carbon_emission_data: deriveCarbonEmissionData(project),
        maintenance_data: project.maintenance_repair_data || {},
        maintenance_repair_data: project.maintenance_repair_data || {},
        demolition_data: deriveDemolitionData(project),
        recycling_data: deriveRecyclingData(project),
    };
};
