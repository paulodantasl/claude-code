import type { RfqTemplateInsert, RequirementTemplateInsert } from "./schema.js";

// Three trade templates. Sections are intentionally short; the LLM fleshes
// each body from the project's actual specs at draft time.
export const TRADE_TEMPLATES: RfqTemplateInsert[] = [
  {
    name: "Cast-in-place concrete (Division 03 30 00)",
    trade: "concrete",
    division: "03 30 00",
    description:
      "RFQ template for cast-in-place concrete including footings, slabs-on-grade, and walls.",
    sections: [
      {
        id: "scope",
        title: "1. Scope of Work",
        prompt:
          "Write a concise scope of work for cast-in-place concrete. Pull mix designs, strengths, and any specified curing requirements from the project's spec section 03 30 00 if present. List the elements being bid (footings, slabs-on-grade, walls, etc.) in bullet form.",
        required: true,
      },
      {
        id: "materials",
        title: "2. Materials & Mix Designs",
        prompt:
          "Enumerate required material standards (cement type, aggregate, admixtures, water/cement ratio, slump, air entrainment). Cite the spec clauses that define them.",
        required: true,
      },
      {
        id: "submittals",
        title: "3. Required Submittals",
        prompt:
          "List submittals the vendor must provide with their bid (mix design, manufacturer data sheets for admixtures, ASTM compliance certificates, batch tickets, etc.). Pull required submittals from the spec.",
        required: true,
      },
      {
        id: "schedule",
        title: "4. Schedule & Lead Time",
        prompt:
          "Describe the project schedule constraints and the lead time we expect for mix design approval and first placement. Reference any milestone dates from the project notes.",
        required: false,
      },
      {
        id: "pricing",
        title: "5. Pricing Format",
        prompt:
          "Instruct the vendor on the required pricing format: line items by element (e.g., footings CY, slab CY, wall CY), unit prices, alternates, and exclusions. Be explicit about what must be itemized.",
        required: true,
      },
      {
        id: "exclusions",
        title: "6. Exclusions & Clarifications",
        prompt:
          "Note exclusions the vendor is allowed to claim and clarifications they must make explicit (e.g., reinforcing steel, formwork, finishing, weather protection).",
        required: false,
      },
    ],
  },
  {
    name: "Structural steel (Division 05 12 00)",
    trade: "structural_steel",
    division: "05 12 00",
    description:
      "RFQ template for structural steel framing, including fabrication and erection.",
    sections: [
      {
        id: "scope",
        title: "1. Scope of Work",
        prompt:
          "Describe the structural steel scope: fabrication, delivery, erection, connections. Pull the connection design responsibility (delegated vs. detailed by EOR) from the spec.",
        required: true,
      },
      {
        id: "standards",
        title: "2. Standards & Specifications",
        prompt:
          "List applicable standards (AISC 360, AISC 303, AWS D1.1, ASTM grades). Reference spec clauses.",
        required: true,
      },
      {
        id: "submittals",
        title: "3. Required Submittals",
        prompt:
          "List submittals: shop drawings, erection drawings, mill certs, welder qualifications, paint system data, connection calcs if delegated.",
        required: true,
      },
      {
        id: "schedule",
        title: "4. Schedule & Lead Time",
        prompt:
          "State the required delivery and erection schedule. Note any phasing.",
        required: false,
      },
      {
        id: "pricing",
        title: "5. Pricing Format",
        prompt:
          "Specify pricing format: lump sum vs. tonnage, unit price for added material, premium for after-hours work.",
        required: true,
      },
      {
        id: "exclusions",
        title: "6. Exclusions & Clarifications",
        prompt:
          "Note expected exclusions (decking, embeds, anchor bolts, fireproofing) and any clarifications.",
        required: false,
      },
    ],
  },
  {
    name: "Gypsum drywall (Division 09 21 16)",
    trade: "drywall",
    division: "09 21 16",
    description: "RFQ template for gypsum board assemblies and finishing.",
    sections: [
      {
        id: "scope",
        title: "1. Scope of Work",
        prompt:
          "Describe the drywall scope: framing, hanging, taping/finishing levels, fire-rated assemblies. Pull the required finish level (e.g., Level 4, Level 5) from the spec.",
        required: true,
      },
      {
        id: "assemblies",
        title: "2. Assemblies & Standards",
        prompt:
          "List required assemblies (UL listings for fire-rated walls, STC ratings), board thickness, framing gauge, control joint spacing.",
        required: true,
      },
      {
        id: "submittals",
        title: "3. Required Submittals",
        prompt:
          "List submittals: product data, UL design listings, shop drawings for special conditions, sample finishes.",
        required: true,
      },
      {
        id: "schedule",
        title: "4. Schedule & Lead Time",
        prompt: "Required start and finish dates by floor or area.",
        required: false,
      },
      {
        id: "pricing",
        title: "5. Pricing Format",
        prompt:
          "Unit pricing by assembly type, separate line items for fire-rated and STC-rated assemblies, alternates for finish level.",
        required: true,
      },
      {
        id: "exclusions",
        title: "6. Exclusions & Clarifications",
        prompt:
          "Standard exclusions (acoustic insulation, in-wall blocking, painting) and clarifications.",
        required: false,
      },
    ],
  },
];

// Requirement (compliance checklist) templates. The deriver can also propose
// requirements straight from spec language; these give a fast manual start.
export const REQUIREMENT_TEMPLATES: RequirementTemplateInsert[] = [
  {
    name: "General vendor onboarding (insurance & waivers)",
    packageKind: "compliance",
    trade: null,
    description:
      "Baseline compliance artifacts required from every vendor before mobilization.",
    items: [
      {
        id: "coi",
        label: "Certificate of Insurance (COI)",
        description:
          "Current COI naming the GC and owner as additional insured, with required GL/auto/umbrella/WC limits.",
        artifactKind: "coi",
        severity: "required",
        sourceHint: "Subcontract insurance exhibit",
      },
      {
        id: "w9",
        label: "W-9",
        description: "Signed W-9 for payment setup.",
        artifactKind: "other",
        severity: "required",
        sourceHint: null,
      },
      {
        id: "lien-waiver",
        label: "Conditional lien waiver (first draw)",
        description: "Conditional waiver and release on progress payment.",
        artifactKind: "lien_waiver",
        severity: "required",
        sourceHint: "State statutory form",
      },
      {
        id: "safety-plan",
        label: "Site-specific safety plan",
        description: "Safety plan and EMR documentation.",
        artifactKind: "other",
        severity: "recommended",
        sourceHint: null,
      },
    ],
  },
  {
    name: "Cast-in-place concrete submittals (03 30 00)",
    packageKind: "compliance",
    trade: "concrete",
    description: "Submittal package required for the concrete scope.",
    items: [
      {
        id: "mix-design",
        label: "Concrete mix design",
        description:
          "Mix design for each specified strength, submitted at least 14 days before placement.",
        artifactKind: "submittal",
        severity: "required",
        sourceHint: "03 30 00 - 3.3 Submittals",
      },
      {
        id: "admixture-sds",
        label: "Admixture SDS / product data",
        description: "Manufacturer data and SDS for all admixtures and curing compounds.",
        artifactKind: "sds",
        severity: "required",
        sourceHint: "03 30 00 - 3.3 Submittals",
      },
      {
        id: "cement-cert",
        label: "Cement & aggregate compliance certs",
        description: "ASTM C150 / C33 certificates of compliance.",
        artifactKind: "submittal",
        severity: "required",
        sourceHint: "03 30 00 - 3.3 Submittals",
      },
      {
        id: "curing-warranty",
        label: "Curing compound warranty",
        description: "Manufacturer warranty for the curing compound, if applicable.",
        artifactKind: "warranty",
        severity: "optional",
        sourceHint: null,
      },
    ],
  },
];
