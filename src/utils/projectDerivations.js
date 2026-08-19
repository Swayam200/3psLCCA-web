import { normalizeProjectData } from './projectSchema.js';
import { recyclingChunkData } from './recyclingDerivations.js';
import {
    computeMachineryTotal,
    computeMaterialEmissions,
    computeTrafficReroutingData,
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

export const deriveTrafficAndRoadData = (projectData) => {
    const project = normalizeProjectData(projectData);
    const traffic = project.traffic_data || {};
    const vehicleData = traffic.vehicle_data || traffic.vehicles || {};
    const vehiclesPerDay = traffic.vehicles_per_day || {};
    const roadParams = traffic.road_params || {};
    const alternateRoad = traffic.alternate_road || {};

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
        mode: traffic.mode || traffic.calculation_mode || 'GLOBAL',
        vehicle_data: normalizedVehicles,
        severity_minor: parseNumber(traffic.severity_minor ?? traffic.severity?.severity_minor ?? traffic.severity?.minor),
        severity_major: parseNumber(traffic.severity_major ?? traffic.severity?.severity_major ?? traffic.severity?.major),
        severity_fatal: parseNumber(traffic.severity_fatal ?? traffic.severity?.severity_fatal ?? traffic.severity?.fatal),
        carriage_width_in_m: parseNumber(traffic.carriage_width_in_m ?? roadParams.carriage_width_in_m),
        hourly_capacity: parseNumber(traffic.hourly_capacity ?? roadParams.hourly_capacity),
        alternate_road_carriageway: traffic.alternate_road_carriageway ?? alternateRoad.alternate_road_carriageway ?? '',
        alternate_road_speed: parseNumber(traffic.alternate_road_speed ?? alternateRoad.alternate_road_speed),
        road_roughness_mm_per_km: parseNumber(traffic.road_roughness_mm_per_km ?? roadParams.road_roughness_mm_per_km),
        road_rise_m_per_km: parseNumber(traffic.road_rise_m_per_km ?? roadParams.road_rise_m_per_km),
        road_fall_m_per_km: parseNumber(traffic.road_fall_m_per_km ?? roadParams.road_fall_m_per_km),
        additional_reroute_distance_km: parseNumber(traffic.additional_reroute_distance_km ?? roadParams.additional_reroute_distance_km),
        additional_travel_time_min: parseNumber(traffic.additional_travel_time_min ?? roadParams.additional_travel_time_min),
        crash_rate_accidents_per_million_km: parseNumber(traffic.crash_rate_accidents_per_million_km ?? roadParams.crash_rate_accidents_per_million_km),
        work_zone_multiplier: parseNumber(traffic.work_zone_multiplier ?? roadParams.work_zone_multiplier),
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
