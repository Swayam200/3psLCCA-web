import { parseNumber } from '../carbon_emission/carbonUtils.js'

const VEHICLES = [
  ['small_cars', 'Small cars'],
  ['big_cars', 'Big cars'],
  ['two_wheelers', 'Two wheelers'],
  ['o_buses', 'Ordinary buses'],
  ['d_buses', 'Deluxe buses'],
  ['lcv', 'Light commercial vehicles'],
  ['hcv', 'Heavy commercial vehicles'],
  ['mcv', 'Multi-axle commercial vehicles'],
]

const CONSTRUCTION = [
  ['foundation_data', 'Foundation'],
  ['substructure_data', 'Sub-Structure'],
  ['superstructure_data', 'Super Structure'],
  ['miscellaneous_data', 'Miscellaneous'],
]

const activeRows = (sections) => (Array.isArray(sections) ? sections : [])
  .flatMap((section) => (section?.rows || []).map((row) => ({ section, row })))
  .filter(({ row }) => row?.state?.in_trash !== true)

const value = (input, fallback = '—') => (
  input === undefined || input === null || input === '' ? fallback : input
)

const money = (input) => parseNumber(input).toLocaleString('en-IN', {
  maximumFractionDigits: 2,
})

export const buildReportModel = (project = {}, calculation = {}) => {
  const general = project.general_info || {}
  const bridge = project.bridge_data || {}
  const financial = project.financial_data || {}
  const maintenance = project.maintenance_repair_data || project.maintenance_data || {}
  const demolition = project.demolition_data || {}
  const traffic = project.traffic_and_road_data || project.traffic_data || {}
  const carbon = project.carbon_emission_data || {}
  const social = carbon.social_cost_data || {}
  const material = carbon.material_emissions_data || {}
  const transport = carbon.transport_emissions_data || {}
  const machinery = carbon.machinery_emissions_data || {}
  const recycling = project.recycling_data || {}
  const currency = general.project_currency || project.currency || 'INR'
  const trafficMode = String(traffic.mode || traffic.calculation_mode || 'GLOBAL').toUpperCase()

  const constructionRows = CONSTRUCTION.flatMap(([key, category]) => (
    activeRows(project[key]).map(({ section, row }) => ({
      category,
      component: section?.name || '—',
      material: row?.workName || row?.values?.material_name || 'Unnamed material',
      quantity: parseNumber(row?.qty ?? row?.values?.quantity),
      unit: row?.unit || row?.values?.unit || '—',
      rate: parseNumber(row?.rate ?? row?.values?.rate),
      source: row?.source || row?.values?.rate_source || '—',
      total: parseNumber(row?.qty ?? row?.values?.quantity)
        * parseNumber(row?.rate ?? row?.values?.rate),
    }))
  ))

  const materialRows = (material.rows || []).map((row) => ({
    category: row.category || '—',
    component: row.sectionName || '—',
    material: row.name || row.material || 'Unnamed material',
    quantity: parseNumber(row.quantity ?? row.qty),
    unit: row.unit || '—',
    conversionFactor: parseNumber(row.conversion_factor ?? row.cf, 1),
    emissionFactor: parseNumber(row.emission_factor ?? row.carbon_emission ?? row.ef),
    emissionUnit: row.emission_unit || row.carbon_unit || row.ef_unit || '—',
    total: parseNumber(row.total_kgCO2e ?? row.total),
    included: row.calculated_included ?? row.included ?? true,
    reason: row.reason || '—',
  }))

  const transportRows = (transport.entries || []).map((entry) => ({
    vehicle: entry.vehicle_name || '—',
    origin: entry['from-to'] || entry.origin || '—',
    distance: parseNumber(entry.distance_km),
    trips: parseNumber(entry.trips),
    emissions: parseNumber(entry.emission_kgCO2e),
  }))

  const machineryRows = machinery.mode === 'lumpsum'
    ? [
        {
          equipment: 'Electricity',
          source: 'Grid electricity',
          consumption: parseNumber(machinery.lumpsum?.elec_consumption_per_day),
          days: parseNumber(machinery.lumpsum?.elec_days),
          factor: parseNumber(machinery.lumpsum?.elec_ef),
          emissions: parseNumber(machinery.lumpsum?.elec_consumption_per_day)
            * parseNumber(machinery.lumpsum?.elec_days)
            * parseNumber(machinery.lumpsum?.elec_ef),
        },
        {
          equipment: 'Fuel',
          source: 'Fuel',
          consumption: parseNumber(machinery.lumpsum?.fuel_consumption_per_day),
          days: parseNumber(machinery.lumpsum?.fuel_days),
          factor: parseNumber(machinery.lumpsum?.fuel_ef),
          emissions: parseNumber(machinery.lumpsum?.fuel_consumption_per_day)
            * parseNumber(machinery.lumpsum?.fuel_days)
            * parseNumber(machinery.lumpsum?.fuel_ef),
        },
      ]
    : (machinery.detailed?.rows || []).map((row) => ({
        equipment: row.name || '—',
        source: row.source || '—',
        consumption: parseNumber(row.rate) * parseNumber(row.hrs) * parseNumber(row.days),
        days: parseNumber(row.days),
        factor: parseNumber(row.ef),
        emissions: parseNumber(row.rate) * parseNumber(row.hrs)
          * parseNumber(row.days) * parseNumber(row.ef),
      }))

  return {
    project: {
      name: general.project_name || bridge.bridge_name || project.name || 'Unnamed Project',
      code: general.project_code || '—',
      description: general.project_description || general.remarks || 'No description provided.',
      country: general.project_country || bridge.project_country || project.country || '—',
      currency,
      unitSystem: general.unit_system || project.unitSystem || '—',
      agency: general.agency_name || bridge.user_agency || '—',
      evaluator: general.contact_person || general.evaluated_by || '—',
      reviewer: general.reviewed_by || '—',
    },
    bridgeRows: [
      ['Bridge name', value(bridge.bridge_name)],
      ['User agency', value(bridge.user_agency)],
      ['Location', value(bridge.location)],
      ['Country', value(bridge.project_country || general.project_country)],
      ['Bridge type', value(bridge.bridge_type)],
      ['Total span', `${value(bridge.span, 0)} m`],
      ['Carriageway width', `${value(bridge.carriageway_width, 0)} m`],
      ['Number of lanes', value(bridge.num_lanes, 0)],
      ['Traffic direction', value(bridge.vehicle_path_direction)],
      ['Footpath', value(bridge.footpath)],
      ['Design life', `${value(bridge.design_life, 0)} years`],
      ['Analysis period', `${value(bridge.analysis_period, 0)} years`],
      ['Year of construction', value(bridge.year_of_construction)],
      ['Construction duration', `${value(bridge.duration_construction_months, 0)} months`],
      ['Working days per month', value(bridge.working_days_per_month, 0)],
      ['Calendar days per month', value(bridge.days_per_month, 0)],
    ],
    financialRows: [
      ['Discount rate', `${value(financial.discount_rate, 0)} %`, value(financial.discount_rate_source)],
      ['Inflation rate', `${value(financial.inflation_rate, 0)} %`, value(financial.inflation_rate_source)],
      ['Interest rate', `${value(financial.interest_rate, 0)} %`, value(financial.interest_rate_source)],
      ['Investment ratio', value(financial.investment_ratio, 0), value(financial.investment_ratio_source)],
    ],
    constructionRows,
    constructionTotal: constructionRows.reduce((sum, row) => sum + row.total, 0),
    maintenanceRows: [
      ['Routine inspection', `${value(maintenance.routine_inspection_cost, 0)} %`, `${value(maintenance.routine_inspection_freq, 0)} years`, '—'],
      ['Periodic maintenance', `${value(maintenance.periodic_maintenance_cost, 0)} %`, `${value(maintenance.periodic_maintenance_freq, 0)} years`, '—'],
      ['Major inspection', `${value(maintenance.major_inspection_cost, 0)} %`, `${value(maintenance.major_inspection_freq, 0)} years`, '—'],
      ['Major repair', `${value(maintenance.major_repair_cost, 0)} %`, `${value(maintenance.major_repair_freq, 0)} years`, `${value(maintenance.major_repair_duration, 0)} months`],
      ['Bearing and expansion-joint replacement', `${value(maintenance.bearing_exp_joint_cost, 0)} %`, `${value(maintenance.bearing_exp_joint_freq, 0)} years`, `${value(maintenance.bearing_exp_joint_duration, 0)} days`],
      ['Demolition and disposal', `${value(demolition.demolition_cost_pct ?? demolition.demolition_cost, 0)} %`, 'End of life', `${value(demolition.demolition_duration, 0)} months`],
    ],
    trafficMode,
    globalTrafficRows: [
      ['Road-user cost per day', `${currency} ${money(traffic.road_user_cost_per_day)}`],
      ['Reference/source', value(traffic.source || traffic.global_entry?.source)],
      ['Remarks', value(traffic.remarks)],
    ],
    vehicleRows: VEHICLES.map(([key, label]) => {
      const row = traffic.vehicle_data?.[key] || traffic.vehicles?.[key] || {}
      return [
        label,
        parseNumber(row.vehicles_per_day),
        parseNumber(row.accident_percentage),
        row.pwr === undefined ? '—' : parseNumber(row.pwr),
      ]
    }),
    roadRows: [
      ['Alternate carriageway', value(traffic.alternate_road_carriageway)],
      ['Carriageway width', `${value(traffic.carriage_width_in_m, 0)} m`],
      ['Hourly capacity', `${value(traffic.hourly_capacity, 0)} PCU/hour`],
      ['Road roughness', `${value(traffic.road_roughness_mm_per_km, 0)} mm/km`],
      ['Road rise', `${value(traffic.road_rise_m_per_km, 0)} m/km`],
      ['Road fall', `${value(traffic.road_fall_m_per_km, 0)} m/km`],
      ['Additional reroute distance', `${value(traffic.additional_reroute_distance_km, 0)} km`],
      ['Additional travel time', `${value(traffic.additional_travel_time_min, 0)} min`],
      ['Crash rate', value(traffic.crash_rate_accidents_per_million_km, 0)],
      ['Work-zone multiplier', value(traffic.work_zone_multiplier, 0)],
      ['Force free-flow off-peak', traffic.force_free_flow_off_peak ? 'Yes' : 'No'],
    ],
    peakRows: Object.entries(traffic.peak_hour_distribution || traffic.peak_distribution || {})
      .map(([hour, fraction]) => [hour.replaceAll('_', ' '), parseNumber(fraction)]),
    socialCarbonRows: [
      ['Source/mode', value(social.source || social.mode)],
      ['Applied SCC', `${currency} ${value(social.result?.cost_of_carbon_local ?? social.cost_of_carbon_local, 0)} /kgCO2e`],
      ['Reference', value(social.custom?.source || social.source_reference)],
      ['Comments', value(social.custom?.comments || social.comments)],
    ],
    materialIncluded: materialRows.filter((row) => row.included),
    materialExcluded: materialRows.filter((row) => !row.included),
    transportRows,
    transportTotal: parseNumber(transport.total_kgCO2e),
    machineryRows,
    machineryTotal: parseNumber(machinery.total_kgCO2e),
    diversionRows: [
      ['Mode', value(carbon.diversion_emissions_data?.mode)],
      ['Reroute distance', `${value(carbon.diversion_emissions_data?.reroute_km, 0)} km`],
      ['Total diversion emissions', `${value(carbon.diversion_emissions_data?.total_kgCO2e_per_day, 0)} kgCO2e/day`],
    ],
    recyclingIncluded: (recycling.included || []).map((row) => [
      row.material || row.materialName || '—',
      value(row.recoveryPct ?? row.recyclability_percentage, 0),
      value(row.scrapRate ?? row.scrap_rate, 0),
      value(row.recoveredValue, 0),
    ]),
    recyclingExcluded: (recycling.excluded || []).map((row) => [
      row.material || row.materialName || '—',
      value(row.reason || row.exclusionReason),
    ]),
    recyclingTotal: parseNumber(recycling.total_recovered_value),
    calculation: {
      source: calculation.source || 'unknown',
      coreVersion: calculation.coreVersion || calculation.core_version || 'unknown',
      pyodideVersion: calculation.pyodideVersion || calculation.pyodide_version || 'unknown',
      calculatedAt: calculation.calculated_at || 'unknown',
    },
  }
}
