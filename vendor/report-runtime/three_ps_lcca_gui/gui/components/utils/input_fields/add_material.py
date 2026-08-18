FIELD_DEFINITIONS = {
    # ── Basic Info ──────────────────────────────────────────────────────────
    "material_name": {
        "label": "Material Name",
        "explanation": "Name of the material or work item as it appears in your project schedule.",
        "required": True,
    },
    "quantity": {
        "label": "Quantity",
        "explanation": "Total quantity of this material required on site, expressed in your project unit (Unit A).",
        "required": True,
    },
    "unit": {
        "label": "Unit",
        "explanation": "The site/project unit for quantity. Example: m3, kg, m, nos.",
        "required": True,
    },
    "rate": {
        "label": "Rate (Cost)",
        "explanation": "Unit cost of this material in your project currency.",
        "required": False,
    },
    "rate_source": {
        "label": "Rate Source",
        "explanation": "Reference for the rate used. Example: DSR 2023, Market Rate, Quoted Rate.",
        "required": False,
    },
    # ── Carbon Emission ─────────────────────────────────────────────────────
    "carbon_emission": {
        "label": "Emission Factor",
        "explanation": (
            "Carbon emission factor from a standard reference (e.g. IFC, IPCC, ICE Database), "
            "expressed in kgCO₂e per Unit B. Example: 0.159 kgCO₂e/kg for ready-mix concrete."
        ),
        "required": False,
    },
    "carbon_unit": {
        "label": "Carbon Unit",
        "explanation": (
            "Unit in which the emission factor is expressed, taken from the standard reference. "
            "Format: kgCO₂e/<unit> - e.g. kgCO₂e/kg, kgCO₂e/m3."
        ),
        "required": False,
    },
    "carbon_emission_src": {
        "label": "Emission Factor Source",
        "explanation": "Reference database or standard used for the emission factor. Example: ICE v3.0, IPCC AR6, ecoinvent.",
        "required": False,
    },
    "conversion_factor": {
        "label": "Conversion Factor",
        "explanation": (
            "Converts your site unit (Unit A) to the standard reference unit (Unit B). "
            "Example: quantity in m³ but emission factor is per kg - enter density, e.g. 2400 for concrete. "
            "Formula: Carbon = Quantity × Conversion Factor × Emission Factor."
        ),
        "required": False,
    },
    # ── Recyclability ───────────────────────────────────────────────────────
    "scrap_rate": {
        "label": "Scrap Rate (per unit)",
        "explanation": (
            "Salvage value received per unit of material after demolition, "
            "expressed in the project's base currency per unit (e.g., per kg, per ton, per m³). "
            "This represents the resale price of the recovered material. "
            "Example: If new steel costs 100 per kg and recovered scrap steel "
            "can be sold for 50 per kg, enter 50."
        ),
        "required": False,
    },
    "post_demolition_recovery_percentage": {
        "label": "Post-Demolition Recovery (%)",
        "explanation": (
            "Percentage of the original installed material quantity that remains "
            "recoverable after demolition. "
            "Example: If 100 kg of steel was initially used and 90 kg can be "
            "recovered, enter 90."
        ),
        "required": False,
    },
    # ── Categorization ──────────────────────────────────────────────────────
    "grade": {
        "label": "Grade",
        "explanation": "Material grade or specification. Example: M25 for concrete, Fe500 for rebar.",
        "required": False,
    },
    "type": {
        "label": "Type",
        "explanation": "Material category. Example: Concrete, Steel, Masonry, Timber.",
        "required": False,
    },
}


