# Power BI Visual Generation Research and Delivery Plan

## Goal

Define a realistic path to a **production-grade AI-assisted Power BI visual generation server** that can:

- generate valid Power BI report visuals and layouts from expressed needs,
- propose strong report presentation/design directions,
- stay aligned with official Microsoft surfaces,
- coexist cleanly with `microsoft/powerbi-modeling-mcp`,
- and avoid overpromising on unsupported or weakly documented visual behaviors.

This document compiles:

- official Microsoft documentation findings,
- GitHub ecosystem research,
- architectural conclusions,
- and a concrete forward plan for implementation.

## Current Repo Baseline

This repository already provides the foundations needed for a serious solution:

- file-first PBIP/PBIR/TMDL project discovery,
- structured report reads,
- structured semantic-model reads,
- safe report writes with `dry_run` and backups,
- local TMDL writes for common model operations,
- binding analysis between visuals and semantic-model objects,
- impact-analysis helpers,
- a smoke test and broad unit-test coverage,
- explicit interop guidance with `microsoft/powerbi-modeling-mcp`,
- a real MCP stdio integration test.

This means the repo no longer needs a raw CRUD layer. It needs a **semantic generation layer** above the current safe mutation APIs.

## Documentation Compilation

### 1. Official Microsoft Documentation Surfaces

#### PBIR / PBIP / Report Metadata

These are the strongest official sources for generating or editing report visuals outside Power BI Desktop:

- Power BI enhanced report format (PBIR):  
  https://learn.microsoft.com/en-us/power-bi/developer/embedded/projects-enhanced-report-format
- Power BI Desktop project report folder:  
  https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-report
- Report definition (Fabric REST article):  
  https://learn.microsoft.com/en-us/rest/api/fabric/articles/item-management/definitions/report-definition
- Official JSON schemas for report definition:  
  https://github.com/microsoft/json-schemas/tree/main/fabric/item/report/definition

What these sources give us:

- PBIR is the official file-first report surface.
- Report metadata is split into pages, visuals, bookmarks, report settings, resources, etc.
- JSON schemas exist and are machine-usable.
- This is the correct surface for **built-in visual containers**, report layout, and visual metadata mutation.

Limits:

- PBIR documentation is schema- and file-structure-heavy.
- It does not provide a complete “all built-in visuals syntax guide.”
- PBIR is still described as preview in current Microsoft docs, so versioning matters.

#### Custom Visual Development

These are the strongest official sources for the custom visual path:

- Develop custom visuals in Power BI:  
  https://learn.microsoft.com/en-us/power-bi/developer/visuals/develop-power-bi-visuals
- Visual project structure:  
  https://learn.microsoft.com/en-us/power-bi/developer/visuals/visual-project-structure
- Capabilities and properties:  
  https://learn.microsoft.com/en-ie/power-bi/developer/visuals/capabilities
- Objects and properties:  
  https://learn.microsoft.com/en-us/power-bi/developer/visuals/objects-properties
- Data view mappings:  
  https://learn.microsoft.com/en-us/power-bi/developer/visuals/dataview-mappings
- Visual API:  
  https://learn.microsoft.com/en-us/power-bi/developer/visuals/visual-api
- Format pane / formatting model:  
  https://learn.microsoft.com/en-us/power-bi/developer/visuals/format-pane-general
- Official custom visual API repo:  
  https://github.com/microsoft/powerbi-visuals-api
- Official visuals tools / `pbiviz`:  
  https://github.com/microsoft/PowerBI-visuals-tools

What these sources give us:

- A custom visual is a separate artifact family.
- The syntax is not PBIR-native; it is package/capability-based.
- `capabilities.json`, `dataRoles`, `dataViewMappings`, objects/properties, and formatting model define how the host interacts with a visual.

Limits:

- This is not a complete syntax grammar for native Power BI visuals.
- It is the right path only when the output is a **custom visual**, not a standard report visual container.

#### Embedded Authoring APIs

Official runtime authoring APIs:

- Report authoring overview:  
  https://learn.microsoft.com/en-us/javascript/api/overview/powerbi/report-authoring-overview
- Create a visual:  
  https://learn.microsoft.com/en-us/javascript/api/overview/powerbi/create-add-visual
- Configure data fields:  
  https://learn.microsoft.com/en-us/javascript/api/overview/powerbi/data-fields
- Format visual properties:  
  https://learn.microsoft.com/en-us/javascript/api/overview/powerbi/visual-properties
- Create, edit, and save an embedded report:  
  https://learn.microsoft.com/en-us/javascript/api/overview/powerbi/create-edit-report-embed-view

What these sources give us:

- A live imperative authoring surface for embedded scenarios.
- Useful for operational automation in a running report session.

Limits:

- These APIs are not a persisted file syntax.
- They are a separate target from PBIR generation.

### 2. GitHub Ecosystem Research

The strongest research repos found:

#### Best corpus / catalog sources

- `DataChant/PowerBI-Visuals-AppSource`  
  https://github.com/DataChant/PowerBI-Visuals-AppSource  
  Best broad source for custom visual GUIDs, packages, metadata, and examples.

- `pbi-tools/pbix-samples`  
  https://github.com/pbi-tools/pbix-samples  
  Best source of extracted real-world Power BI report/project structures.

#### Best declarative visual sources

- `deneb-viz/deneb`  
  https://github.com/deneb-viz/deneb  
  The strongest direct target for AI-generated declarative visuals inside Power BI.

- `PBI-David/Deneb-Showcase`  
  https://github.com/PBI-David/Deneb-Showcase  
  Best example corpus for Deneb/Vega-Lite visual patterns.

- `vega/vega-lite`  
  https://github.com/vega/vega-lite  
  Best upstream grammar for declarative chart generation.

#### Best validation / structural tools

- `pbi-tools/pbi-tools`  
  https://github.com/pbi-tools/pbi-tools  
  Good for PBIP/PBIR extraction and round-trips.

- `NatVanG/fab-inspector`  
  https://github.com/NatVanG/fab-inspector  
  Useful for PBIR-aware validation and metadata testing ideas.

#### Important adjacent but not complete solutions

- `microsoft/powerbi-report-authoring`  
  https://github.com/microsoft/powerbi-report-authoring  
  Useful for embedded runtime authoring, not file-first generation.

- `microsoft/powerbi-modeling-mcp`  
  https://github.com/microsoft/powerbi-modeling-mcp  
  Strong live semantic-model server, but not report/page/visual generation.

### 2b. Additional Custom Visual and Design-System Research

The extra GitHub scan shows that the best prior art for "custom things" is split across custom visual contracts, declarative visualization templates, and report theme/design-system assets.

#### Microsoft Sample Bar Chart

- Repo: https://github.com/microsoft/PowerBI-visuals-sampleBarChart
- Key files:
  - `capabilities.json`
  - `pbiviz.json`
  - `src/barChart.ts`
  - `src/barChartSettingsModel.ts`

Observed pattern:

- `capabilities.json` is the host contract:
  - `dataRoles`
  - `dataViewMappings`
  - `objects`
  - tooltips
  - drilldown
  - formatting support
- `pbiviz.json` is the package identity and runtime contract:
  - visual name
  - display name
  - GUID
  - API version
  - icon/style/capabilities paths
- `visual.ts` turns Power BI data views into a render model, then renders with D3/SVG and Power BI host services.
- The formatting model maps capabilities objects to formatting cards/slices.

Design lesson:

- Custom visual generation is not "write one visual JSON."
- It is a contract-first authoring surface:
  - roles define what fields are allowed,
  - mappings define how those fields arrive,
  - formatting objects define the design controls,
  - TypeScript rendering code defines the actual visual behavior.

Implication for this repo:

- The visual AI layer should treat custom visuals as **capability manifests**, not as native PBIR visuals.
- A future custom visual catalog should parse or store:
  - data roles,
  - mappings,
  - formatting object groups,
  - privileges,
  - certification/governance notes,
  - visual GUID/package identity.

#### Formatting Model Utils

- Repo: https://github.com/microsoft/powerbi-visuals-utils-formattingmodel
- Official docs: https://learn.microsoft.com/en-us/power-bi/developer/visuals/format-pane-general

Observed pattern:

- Formatting settings are modeled as cards, groups, containers, and slices.
- Card and slice names must align with `capabilities.json` object/property names.
- Formatting cards can be hidden dynamically.
- The custom visual exposes formatting through `getFormattingModel`.

Design lesson:

- Formatting is a structured control model, not just arbitrary style JSON.
- A design generator should understand "what can be styled" per visual family before it promises a look.

Implication for this repo:

- Add a future `design_system.py` or `style_catalog.py` layer that can describe:
  - global theme controls,
  - native visual style controls,
  - custom visual formatting controls,
  - unsupported design requests.

#### HTML Content Custom Visual

- Repo: https://github.com/dm-p/powerbi-visuals-html-content
- Site: https://html-content.com/

Observed pattern:

- `capabilities.json` defines a broad `content` role using `GroupingOrMeasure`.
- The visual accepts HTML/Markdown-like content and optional styling inputs.
- The lite package explicitly restricts remote content and HTML surface area.
- The visual is useful for highly custom presentation blocks, SVG/HTML cards, and authored narrative elements.

Design lesson:

- HTML/SVG custom visuals can provide strong presentation flexibility, but governance and sandboxing limits matter.
- They are attractive for custom storytelling blocks, but not a universal safe default.

Implication for this repo:

- Treat HTML/SVG custom visuals as a later optional lane:
  - `html_content_plan_generate`
  - `html_content_eligibility_check`
  - `html_content_payload_validate`
- Do not use this as the default report design lane until custom visual governance is explicit.

#### Deneb and Vega Template Repos

- `deneb-viz/deneb`: https://github.com/deneb-viz/deneb
- `PowerBI-tips/Deneb-Templates`: https://github.com/PowerBI-tips/Deneb-Templates
- `avatorl/Deneb-Vega-Templates`: https://github.com/avatorl/Deneb-Vega-Templates
- Deneb template docs: https://deneb.guide/docs/1.6/templates

Observed pattern:

- Deneb uses Vega/Vega-Lite specs with Deneb-specific template metadata.
- `avatorl/Deneb-Vega-Templates` organizes templates by the Financial Times Visual Vocabulary:
  - deviation
  - correlation
  - ranking
  - distribution
  - change over time
  - magnitude
  - part-to-whole
  - spatial
  - flow
- Advanced examples include chart types such as Sankey.

Design lesson:

- For "AI visual generation," a visual vocabulary is more useful than a flat list of Power BI visual types.
- The planner should first classify analytical intent, then choose the rendering lane:
  - native PBIR for standard dashboard/report components,
  - Deneb for expressive chart grammar,
  - custom visual only when the package and governance context are known.

Implication for this repo:

- Add a future `visual_vocabulary.py` layer with intent families:
  - compare
  - rank
  - trend
  - distribute
  - correlate
  - explain variance
  - show flow
  - show geography
  - monitor status
  - tell narrative
- The existing `visual_plan_generate` should eventually choose from this vocabulary before choosing a concrete `visualType`.

#### Theme Template Repos and Design Systems

- `MattRudy/PowerBI-ThemeTemplates`: https://github.com/MattRudy/PowerBI-ThemeTemplates
- Official custom theme docs: https://learn.microsoft.com/en-us/power-bi/create-reports/report-themes-create-custom

Observed pattern:

- Theme JSON supports global styles and visual-specific `visualStyles`.
- Style presets can create named variations for visual types.
- Matt Rudy's repo separates theme examples per native visual type and validates JSON through automation.
- The repo explicitly exists because per-visual formatting options are difficult to discover from docs alone.

Design lesson:

- Strong Power BI report design should rely on theme-level defaults before visual-level overrides.
- A page design generator should output:
  - page layout,
  - visual choices,
  - theme/style guidance,
  - style preset recommendations,
  - exceptions that truly need per-visual formatting.

Implication for this repo:

- Add a future design-system lane:
  - `theme_design_brief_generate`
  - `theme_style_catalog_list`
  - `theme_recipe_generate`
  - `theme_recipe_apply`
- Use global `visualStyles["*"]` and named presets for consistency.
- Keep direct `visual.json` style mutation for specific exceptions and mined examples.

#### SandDance

- Repo: https://github.com/microsoft/SandDance
- Project site: https://microsoft.github.io/SandDance/

Observed pattern:

- SandDance is a modular visualization system with JavaScript components and a Power BI custom visual.
- It emphasizes exploration, presentation, unit visualizations, animation, and storytelling.
- Microsoft describes it as a way to explore, understand, and present data; the Power BI visual benefits from animated transitions and bookmarks for narrative context.

Design lesson:

- Some report design quality comes from interaction and narrative sequencing, not only static layout.
- Bookmarks, navigation, and visual state transitions should become part of the report design planner later.

Implication for this repo:

- Add bookmark/navigation-aware page recipes later:
  - executive story flow,
  - guided analysis,
  - before/after or scenario walkthrough,
  - drillthrough path suggestions.

#### DataChant AppSource Visual Corpus

- Repo: https://github.com/DataChant/PowerBI-Visuals-AppSource

Observed pattern:

- This is useful as an inventory/corpus of custom visual packages and metadata.
- It is not a generation engine, but it can help build a custom visual catalog.

Design lesson:

- Custom visual support should begin with inventory and eligibility, not generation.

Implication for this repo:

- Add future custom visual tools:
  - `custom_visual_inventory_scan`
  - `custom_visual_capabilities_read`
  - `custom_visual_eligibility_check`
  - `custom_visual_generation_guidance`

### 3. Deneb Research

Deneb should be treated as an **optional generation lane**, not the default replacement for PBIR.

Why it matters:

- It provides a high-level declarative syntax target for chart-heavy requests.
- It is a much better AI authoring surface for bespoke charts than hand-authoring every native visual’s internal JSON shape.

Why it should not be the default:

- It is still a custom visual.
- Governance, certification, and import restrictions matter.
- It is not the right default for report layout, slicers, cards, tables, matrix visuals, or environments that restrict custom visuals.

Conclusion:

- native PBIR remains the baseline,
- Deneb is the optional “advanced chart lane.”

## Research Synthesis

## There is no single visual syntax

The main conclusion is that “generate all possible Power BI visuals syntax” is the wrong abstraction.

There are at least five authoring surfaces:

1. Native PBIR report visuals
2. Custom visuals (`pbiviz`, `capabilities.json`)
3. Deneb / Vega-Lite / Vega declarative visuals
4. Embedded imperative authoring APIs
5. Installed / approved custom visual inventory and governance state

So the real problem is not “one universal syntax generator.”  
It is **a visual generation system that selects the right authoring surface**.

## The repo should own the report-first semantic layer

This repository is already the correct home for:

- PBIR report/page/visual generation,
- report-first design/layout semantics,
- local PBIP/TMDL file mutation,
- report↔model binding and impact analysis.

It should not try to duplicate:

- live Desktop/Fabric semantic-model orchestration,
- Microsoft’s broad modeling server scope,
- arbitrary custom visual packaging/import workflows on day one.

## “Design expertise” is a separate layer from syntax generation

If we want the server to “propose nice report designs” based on presentation needs, we need a dedicated **design intelligence layer**, not just a better JSON generator.

That layer needs to reason about:

- audience: executive, analyst, operations, customer
- intent: compare, monitor, diagnose, explain, persuade
- page archetype: dashboard, detail page, overview, comparison, operational cockpit
- narrative flow: hero KPI → trend → breakdown → exceptions → details
- visual hierarchy: emphasis, whitespace, layout, grouping, redundancy
- Power BI presentation constraints: interactions, slicers, page size, theme consistency, readability

This is very similar to what good web page design MCP servers do:

- they don’t just emit HTML,
- they choose composition, hierarchy, style, and defaults.

The same principle should apply here.

## Recommended Real Solution Architecture

Build one new layer above the current mutation surface:

- `mcp/visual_ai/catalog.py`
- `mcp/visual_ai/planner.py`
- `mcp/visual_ai/compiler.py`
- `mcp/visual_ai/design_expert.py`
- later: `mcp/visual_ai/examples.py`
- later: `mcp/visual_ai/custom_guidance.py`

### `catalog.py`

Read-only catalog of supported visual families and their requirements:

- `visualType`
- syntax family (`native-pbir`, `deneb`, `custom-visual`, `embedded-runtime`)
- required roles
- optional roles
- queryState templates
- formatting surfaces
- constraints
- example references

### `planner.py`

Intent → structured plan:

Input:
- “show monthly margin trend by manager”
- “give me an executive overview page”
- “I want a clean consulting margin dashboard”

Output:
- recommended page archetype
- recommended visual set
- required model fields
- whether model work is needed
- confidence
- generation path (`native-pbir` vs `deneb`)

### `compiler.py`

Plan → existing safe write primitives:

- create containers
- bind fields
- apply layout
- apply style templates
- attach provenance

It should compile only through the current safe write layer, not bypass it.

### `design_expert.py`

This is the missing “nice report design” layer.

It should provide:

- presentation intent classification
- page recipe selection
- layout heuristics
- section hierarchy
- theme/style recommendations
- audience-specific defaults
- “why this design” explanation

Example outputs:

- “Executive KPI page”
- “Operational trend-and-exception page”
- “Consulting margin analysis page”
- “Project portfolio review page”

### `examples.py`

Only after catalog + planner exist:

- mine PBIR examples
- mine Deneb examples
- find nearest-neighbor layouts/styles
- suggest reusable fragments

### `custom_guidance.py`

Read-only guidance:

- what custom visuals are already installed or allowed
- when to prefer Deneb
- what is unsupported

## Practical Support Tiers

### Tier 1: Native PBIR skeletons

Safe default:

- `visualType`
- `position`
- placeholder bindings

### Tier 2: Native role-aware visuals

For standard supported visuals:

- full `queryState`
- sort/filter wiring
- core formatting

### Tier 3: Deneb lane

For chart-heavy bespoke visuals:

- generate Vega-Lite first
- Vega only when lower-level control is necessary

### Tier 4: Installed custom visuals

Only when:

- the package is known
- the organization allows it
- the server has a catalog entry for it

### Tier 5: Runtime embedded authoring

Only for live embedded scenarios, not the file-first default.

## Recommended Delivery Plan

### Phase A: Visual catalog + planner foundation

Ship these MCP tools:

- `visual_catalog_list`
- `visual_requirements_check`
- `visual_plan_generate`
- `visual_plan_explain`

Support only these native families first:

- `card`
- `lineChart`
- `clusteredBarChart`
- `clusteredColumnChart`
- `tableEx`
- `slicer`
- `textbox`

### Phase B: Design expertise layer

Ship:

- `report_design_brief_generate`
- `report_page_recipe_list`
- `report_page_recipe_generate`

These should propose:

- page purpose
- visual hierarchy
- section arrangement
- recommended visual families
- recommended layout zones

### Phase C: Compiler

Ship:

- `visual_plan_apply`
- `page_recipe_apply`

Default all apply tools to `dry_run=True`.

### Phase D: Example mining

Build:

- local PBIR example mining
- Deneb example mining
- theme/style preset mining
- custom visual capability manifest mining
- nearest-neighbor suggestion tools

New tools to add:

- `visual_examples_list`
- `visual_template_recommend`
- `theme_style_examples_list`
- `custom_visual_capabilities_read`

### Phase E: Boundary-aware model handoff

If the visual plan needs missing measures/relationships:

- generate machine-readable `ModelRequirements`
- if local PBIP/TMDL is enough, optionally compile to local model writes
- if live Fabric/Desktop work is needed, explicitly hand off to `microsoft/powerbi-modeling-mcp`

### Phase F: Custom visual guidance and optional Deneb compiler

Ship:

- `deneb_spec_generate`
- `deneb_spec_validate`
- `custom_visual_inventory`
- `custom_visual_eligibility_check`

### Phase G: Design-system and visual-vocabulary intelligence

Ship:

- `visual_vocabulary_classify`
- `report_design_system_generate`
- `theme_recipe_generate`
- `page_storyboard_generate`

This phase should encode the strongest lesson from the extra GitHub research:

- classify analytical/presentation intent before choosing a Power BI visual type,
- prefer theme-level and preset-level consistency before per-visual overrides,
- treat custom visuals as explicit capability/governance choices,
- use bookmarks/navigation as a storytelling layer, not just a report artifact.

## Recommended Immediate Next Milestone

If we want a real solution quickly, the best next build is:

1. `visual_catalog_list`
2. `visual_plan_generate`
3. `visual_requirements_check`
4. `report_design_brief_generate`

With only:

- native built-in visuals
- no automatic model mutation
- no arbitrary custom visual generation
- Deneb only as an explicitly selected optional lane
- theme/design-system advice as read-only output first

That is enough to prove:

- the server can reason about visuals, not just mutate files,
- the server can propose strong presentation design,
- the server can choose a generation path intelligently,
- and the server can stay within safe, documented boundaries.

The immediate next implementation after local PBIR example mining should be:

1. `visual_vocabulary_classify`
2. `theme_style_examples_list`
3. `custom_visual_capabilities_read`
4. `report_design_system_generate`

## Recommended Positioning

The strongest positioning for this repo is:

- **This repo**: report/UI file-first generation, local PBIP/TMDL assistance, visual planning, design expertise, report↔model impact reasoning
- **Microsoft modeling MCP**: live semantic-model operations in Desktop/Fabric
- **Deneb**: optional declarative advanced-chart lane

This gives us a realistic, differentiated solution instead of chasing an impossible “universal visual syntax generator.”

## Final Recommendation

Build a **visual planning and design intelligence layer** above the current safe PBIR/TMDL infrastructure.

Do **not** promise support for every visual as one syntax.

Do this instead:

- native PBIR first
- design expertise as a first-class layer
- Deneb as optional advanced chart lane
- custom visuals later and selectively
- Microsoft modeling MCP for live semantic-model work

That is the most credible path to a real solution for Power BI visual generation and report presentation quality.
