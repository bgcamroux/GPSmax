# GPSmax - Architecture Review and Migration Plan

## 1. Project Summary

### What `GPSmax` *is*
`GPSmax` is a personal consumer GPS tool for managing tracks, waypoints, and routes, and integrating them with other projects such as photography and travel. Specifically, this project was born out of a desire for

- something to quickly copy track files off of my GPS receiver onto my PC;
- the ability to split tracks based on activity;
- quick and reliable pruning of tracks; and
- a central repository for my GPS data files and their derivatives.

I have found packages such as QMapShack, while exceptionally powerful and useful, to be a bit too cumbersome for these purposes. Thus, `GPSmax` was devised as a Unix-inspired filesystem-managed data "pipeline" that would meet these goals and more! Specifically, `GPSmax` will

- preserve *all* data produced by (consumer) GPS receivers (tracks, waypoints, sensors, metadata);
- enforce clear separation between raw data, working data, and derived products;
- deliver auditable, reproducible, and reversible products;
- support long-term analysis, visualization, and geotagging workflows;
- operate at the command-line level (no GUI) and remain tool-agnostic.

This project was initially conceived and built with Garmin devices in mind, but this can easily be expanded to any device that produces GPX data files. Presently, `GPSmax` is a *personal* project for my own use. If others find it useful down the road, I will be most happy to publish it.

### Design philosophy
1. Immutable raw data -- derived data may be regenerated
2. Filesystem-first -- no mandatory database
3. Explicit manifests over implicit discovery

### What `GPSmax` is *not*
There are a great number of geographic tools out there that work with GPS data. We can safely say that `GPSmax` is *not*

- a geographic information system (GIS),
- a mapping tool,
- `gpsprune`.

### User workflow
The typical user workflow might look something like this:
1. **Ingest**: copy data to PC
2. **Normalize**: clean up GPX files, normalize timestamps and file naming, and make them human-readable
3. **Analyze**: compute basic summary information about a track
4. **View**: show the selected track with a speed-based heatmap
5. **Prune**: clean up point clusters while maintaining integrity for geotagging or other future work
6. **Export**: save for future use

The user is expected to make decisions at many points in the workflow. Normalization, pruning, and export are the primary decision points, where users must provide part of the normalized file name; identify sections of a track to be pruned; and make decisions on final export. Commands are designed to be repeatable and idempotent and may be re-run safely as the user refines their decisions.

## 2. Current inventory
This section describes the *current state* of the project, including any persistent GPSmax artifacts and their on-disk organization, as implemented **today** (January 22, 2026).

### Current directory layout
```
GPSmax
├── CHANGELOG.md
├── LICENSE
├── pyproject.toml
├── README.md
├── configs
│   └── config.example.toml
├── docs
│   ├── GPS_Data_Workflow.md
│   ├── GPS_Normalization_Workflow.md
│   ├── GPS_SQLite_README.md
│   ├── NORMALIZATION.md
│   ├── PROJECT_PLANNING.md
│   └── ROADMAP.md
├── src
│   └── gpsmax
│       ├── __init__.py
│       ├── config.py
│       ├── errors.py
│       ├── analyze
│       ├── devices
│       ├── formats
│       ├── ingest
│       ├── normalize
│       ├── sql
│       ├── util
│       └── visualize
└── tests
    ├── conftest.py
    └── data
```

### User entry points
`GPSmax` functionality is currently accessed through four directly-executed Python modules under the package tree. Entry points are based on the module path, running as individual scripts rather than as a conslidated command line interface (CLI). As such, each script manages its own configuration loading, logging setup, filesystem path resolution, and error handling/exit codes.

#### I. Ingestion
- `src/gpsmax/ingest/garmin_ingest.py`
- Purpose: Garmin-specific device-oriented ingestion; copy GPX data from the device to the local filesystem repository.

#### II. Normalization
- `src/gpsmax/normalize/gps_normalize.py`
- Purpose: normalize GPX data and metadata into a consistent, human-usable form (eg. timestamps, file naming, formatting) suitable for subsequent analysis and downstream workflows.

#### III. Manifest & import indexing
- `src/gpsmax/sql/gps_import_manifest.py`
- Purpose: import ingestion manifest into a SQLite or other SQL database.

#### IV. Analysis
- `src/gpsmax/analyze/gpx_analyze.py`
- Purpose: compute summary statistics & metrics for a GPX track (eg. point/segment counts, distance, duration, speed).

### Persistent artifacts and on-disk layout
Each user entry point has some form of output, and some of that output is persistent and stored on-disk. By default (that is, unless otherwise specified in the config file) all run-time data are stored in `~/GPS`. The working directory structure currently looks like the following:

```
GPS
├── _db           # [Optional] track database and schema (may be located elsewhere if using Postgres)
├── _raw          # GPX files copied directly from device, treated as immutable by system; manifests and hashes
├── _work         # GPX files being normalized (may rename this from `_work` to `_norm`)
├── index         # logging from `garmin_ingest.py` (may rename to `logs` or place under `_raw/`)
├── maps          # [Optional] maps produced from tracks (this probably belongs to a different workflow)
└── tracks        # finalized and curated GPX outputs ("derived" files)
```

#### I. Ingestion
Ingestion is the process of finding the GPS device, connecting to it, and copying data from it. GPX files copied directly from the GPS device are to be stored in `~/GPS/_raw`.
- Data copied from the GPS device are currently saved in `~/GPS/_raw/<GPX_year>/<ingest_date>/<device_id>`. (This will change.)
- All GPX files under the `_raw` path are treated as immutible by the system.
- Ingestion calculates a SHA-256 hash for each file copied and appends these to `checksums.sha256`.
- An ingestion manifest is written, describing exactly what was imported and where it was saved. Manifests are always output in JSON format by default; optional CSV output is also supported.
- Ingestion manifests and hashes are currently written under the `_raw` tree, under the `<device_id>` subfolder. (This will change.)

#### II. Normalization
Normalization is the process of re-writing GPX files in a more human-friendly format than what comes raw from the device. We also clean up timestamps and provide a standardized, meaningful file name.
- GPX files are read from the `_raw/` tree and written to the `_work/` tree.
- Files from `_raw` are duplicated and re-written, *never* altered themselves.
- Normalization manifests are produced and stored alongside the normalized files under the `_work/` tree. JSON format.
- Sidecar files are produced as well, stored alongside the normalized files, detailing any actions or transformations that were applied to a given GPX file. User notes and other metadata are also stored in this file. JSON format.

#### III. Manifest & import indexing
If a SQLite (or other SQL) database is used, this process will read and insert data from the ingestion manifests.
- The database file is presently located under the `~/GPS` directory. (This will be moved.)
- Currently this process is invoked by the user. (This may change.)

#### IV. Analysis
Analysis reads normalized GPX files and presently outputs only to `stdout`. There are currently no persistent artifacts for this process.


## 3. What works well
Despite being in an exploratory and evolving state, the current GPSmax architecture demonstrates several strong qualities that provide a solid foundation for future refinement.

### Clear separation of data lifecycles
The project already enforces a meaningful separation between:
- raw data (`_raw/`), treated as immutable;
- intermediate, mutable working data (`_work/`);
- finalized, curated outputs (`tracks/`).

This separation directly supports reproducibility, reversibility, and auditability, and aligns well with the stated design philosophy.

### Preservation of original data
All GPX files copied from devices are preserved in their original form, with no in-place modification. This ensures that:
- original device data can always be recovered;
- downstream transformations are non-destructive; and
- errors in later stages do not corrupt source data.

### Deterministic ingestion with verification
The ingestion process:
- computes cryptographic hashes (SHA-256) for imported files; and
- records detailed ingestion manifests describing what was imported and where it was stored.

These practices provide a strong basis for integrity checking, deduplication, and long-term traceability.

### Explicit, human-readable artifacts
Ingestion and normalization both produce human-readable JSON manifests. Normalization also produces
- human-readable GPX files with standardized timestamps and naming, and
- sidecar JSON metadata describing transformations and user-supplied notes.

This approach favors transparency and inspectability over opaque internal state, which is well-suited to a filesystem-first design.

### Human-in-the-loop workflow
The system explicitly expects user decisions at key points (normalization, pruning, export). This avoids premature automation and respects the subjective and contextual nature of GPS data curation, particularly for photography and travel use cases.

### Modular functional domains
Functionality is already grouped into coherent domains (ingest, normalize, analyze, visualize, devices, formats), which:
- makes the codebase easier to navigate; and
- provides a natural basis for later architectural consolidation.

### Minimal mandatory infrastructure
The core workflow does not require a database. Optional SQLite usage is clearly separated, preserving the ability to run the system using only the filesystem and standard tools.

## 4. Pain points and limitations
As evidenced from the above, there are some parts of this project that are not working as nicely as would be desired. As a result of exploratory development, the current architecture exhibits several sources of growth resistance.

### I. Fragmented user entry points
There are currently four separate Python script-like subpackages that are used as entry points for the user. Each entry point manages its own
- configuration loading,
- logging setup,
- error handling and exit codes, and
- filesystem path resolution.

Consistency across commands then relies on convention rather than enforcement. This also results in duplicated code that could better be centralized into one single entry point. This fragmentation results in a higher cognitive load as managing and reasoning about system-wide behaviours is more difficult.

### II. Blurred boundaries: procedural vs data logic
There is no clear separation of logic domains as different entry-point modules appear to combine
- procedural logic / command orchestration (argument parsing, filesystem navigation, user interaction) and
- data logic (data transformations, analysis, metadata handling).

This makes reuse and testing more difficult and obscures which parts of the system represent stable data concepts versus procedural workflow "glue."

### III. Inconsistent or unstable on-disk conventions
There is clear high-level separation between `_raw`, `_work`, and `tracks`, but some aspects are currently unstable:
- directory naming and hierarchy under `_raw`,
- placement of manifests and checksum files,
- location of logs and index-like artifacts,
- naming and purpose of `_work` as opposed to potential alternatives.

These inconsistencies complicate documentation, user expectations, and future automation.

### IV. Manifest and database ambiguity
SQLite-related artifacts and import/indexing scripts indicates an evolving strategy for persistent indexing, but:
- database usage is optional and loosely integrated,
- responsibilities between filesystem manifests and database records are not clearly defined, and
- the authoritative source of truth (filesystem or database?) is not explicitly defined.

These ambiguities may result in duplicated state or project divergence over time.

### V. Limited visibility into workflow state
Manifests and sidecar files provide detailed local context, but there is no unified view of
- what has been ingested,
- what has been normalized, or
- which tracks are finalized versus in-process.

Data management may become more challenging as the dataset grows, requiring manual inspection to answer basic operational questions.

### VI. Naming drift and conceptual overlap
Terminology and nomenclature is evolving and expected, but it can
- obscure intent for future contributors (including future self),
- increase the cost of documentation and onboarding,
- make it harder to define stable interfaces.

## 5. Key risks
The architectural pain points identified above introduce several concrete risks to the long-term viability and usability of GPSmax.

### I. Maintainability risk
The project faces an elevated risk of becoming difficult to maintain as it evolves. Fragmented entry points, blurred boundaries between orchestration and domain logic, and naming drift increase the likelihood that:
- changes must be duplicated across multiple scripts;
- small modifications require understanding large portions of the codebase;
- refactoring efforts become risky due to unclear ownership of responsibilities.

Over time, this may significantly slow development and increase the chance of regressions.

### II. Data integrity risk
While raw GPX data are preserved immutably, higher-level data integrity is at risk due to:
- inconsistent or unstable on-disk conventions;
- ambiguity between filesystem manifests and database records; and
- lack of a clearly defined authoritative source of truth.

These conditions increase the likelihood of silent divergence between representations of the same data, making it difficult to verify correctness or recover confidently from errors.

### III. User interface and experience risk
The absence of a consolidated command-line interface introduces a risk of inconsistent user experience. With multiple script-style entry points:
- command syntax, options, and defaults may diverge;
- logging and error reporting may vary across commands; and
- user expectations may not transfer cleanly from one workflow stage to another.

This inconsistency increases cognitive load and raises the barrier to effective and reliable use.

### IV. Architectural scalability risk
As the project grows in scope and data volume, its architecture risks becoming harder to extend safely. Naming drift, unstable conventions, and blurred logic boundaries obscure intent and make it increasingly difficult to:
- identify the correct location for new functionality;
- reason about the impact of changes; and
- evolve the system without unintended side effects.

This threatens the project’s ability to scale in complexity, not just size.


## 6. Target architecture
This section describes the intended architectural shape of the system at a high level. The goal is not to be prescriptive, but to outline structural decisions that will eliminate or mitigate the risks identified above.

### I. Single, unified entry point
The system will expose a single primary command-line interface for all user interactions. Individual operations are to be implemented as subcommands under this interface.

This structure ensures consistent loading of configurations, logging behaviour, error handling and exit codes, and filesystem path resolution. Additionally, this will ensure a consistent user experience across all operations, reducing code reproduction and divergence.

### II. Explicit separation of responsibilities
There is to be clear delineation between
- command orchestration and user interaction (procedural logic),
- core domain logic and data transformations (data logic), and
- input/output adapters (filesystem, databases, external tools).

Each layer will have a well-defined responsibility, minimizing coupling and improving testability and reuse.

### III. Stable, well-defined data boundaries
Persistent artifacts are to be organized according to a small number of clearly-defined lifecycle stages. Each stage will have:
- a defined purpose,
- well-documented invariants, and
- explicit rules governing mutability and regeneration.

This is to support reproducibility, traceability, and safe iteration over derived data.

### IV. Authoritative sources of truth
Each category of persistent data will have a single, authoritative representation defined by the system. Derived indexes or caches will be designed as secondary and regenerable.

This reduces the risk of silent divergence while simplifying recovery and validation workflows.

### V. Incremental extensibility
This architecture will support the addition of new functionality by extending existing interfaces as opposed to introducing parallel mechanisms. New features will be integrated by:
- adding new subcommands,
- introducing new adapters, or
- extending domain models.

In this way the system is allowed to evolve without destabilizing existing workflows.

### VI. Constraints and non-goals
The target architecture explicitly avoids introducing:
- mandatory external services,
- tightly coupled UI layers, or
- irreversible transformations of source data.

These constraints preserve the system's original design intent while enabling controlled growth.

## 7. Migration plan
This plan is to incrementally migrate from the current architecture (Section 2) to the target architecture (Section 6). Each step should be independently shippable, verifiable, and reversible, with a bias toward protecting raw data and preserving existing workflows.

### Guiding constraints
- Raw GPX data under `_raw/` remain immutable (no in-place modification).
- Existing workflows remain usable throughout migration (legacy entry points continue to run until explicitly deprecated).
- No new features are to be added during migration unless required to preserve behaviour or data integrity.
- Derived artifacts and indexes must remain regenerable from authoritative sources.


### Milestone 1: Establish unified interface without changing behaviour
**Goal:** Introduce a single user-facing command interface while keeping underlying functionality and artifact production unchanged.

#### 1.1: Define the canonical command surface
- **Implementation:** Document the planned subcommand map (eg. `ingest`, `normalize`, `analyze`, `view`, `manifest` or `index` if applicable) and current equivalents.
- **Acceptance criteria:** A single document enumerates subcommands, their purpose, and how they map to current scripts.
- **Rollback:** Documentation only.

#### 1.2: Add unified CLI wrapper that delegates to existing entry points
- **Implementation:** Introduce a single primary CLI that dispatches to the current operational modules for behaviour parity.
- **Acceptance criteria:**
  - For each operation, invoking via the unified CLI produces the same outputs and exit behaviour as invoking the current module directly.
  - Help output lists all supported subcommands and their options at a high level.
- **Rollback:** Remove the wrapper; direct module execution still works.

#### 1.3: Make legacy entry points delegate to the unified CLI
- **Implementation:** Keep the existing modules executable, but have their "main" path delegate into the unified command surface.
- **Acceptance criteria:**
  - Calling legacy modules still works.
  - Behaviour matches unified CLI invocation.
- **Rollback:** Restore legacy modules to directly execute their prior behaviour.

### Milestone 2: Stabilize cross-cutting concerns
**Goal:** Eliminate duplication and divergence of startup concerns while keeping command behaviour stable.

#### 2.1: Centralize configuration resolution policy
- **Implementation:** Create one authoritative configuration resolution flow (default paths, explicit config option, environment override if used), and route all commands through it.
- **Acceptance criteria:**
  - All subcommands resolve configuration identically.
  - A missing or invalid config produces consistent error messaging and exit codes.
- **Rollback:** Revert to command-local config handling (unified CLI remains).

#### 2.2: Centralize logging policy and output conventions
- **Implementation:** Standardize logging level controls, formatting, and destination across all subcommands.
- **Acceptance criteria:**
  - Same verbosity flags behave consistently across all subcommands.
  - Log output is consistent in structure and severity levels.
- **Rollback:** Revert logging setup to prior per-command setup.

#### 2.3: Centralize filesystem root/path resolution
- **Implementation:** Define one authoritative method for resolving `~/GPS`) (or configured root) and the standard subdirectories.
- **Acceptance criteria:**
  - All commands agree on the same resolved paths for `_raw`, `_work`, `tracks`, etc.
  - Path-related errors are consistently  reported.
- **Rollback:** Revert to prior per-command path resolution.

### Milestone 3: Make data boundaries explicit and stable
**Goal:** Stabilize artifact lifecycle rules and make them enforceable without breaking existing data.

#### 3.1: Document lifecycle stages and invariants
- **Implementation:** Convert the "*Persistent artifacts and on-disk layout*" section into an explicit contract: purpose, mutability, and regeneration rules for each stage.
- **Acceptance criteria:**
  - The contract describes current behaviour accurately.
  - The contract identifies which conventions are stable versus transitional.
- **Rollback:** Documentation only.

#### 3.2: Stabilize manifest location and schema versioning
- **Implementation:** Define a stable manifest schema version and ensure writers emit it. Define a stable location strategy for manifests while supporting legacy locations during a transition.
- **Acceptance criteria:**
  - New manifests include schema versioning.
  - Existing manifests remain readable/importable.
  - Manifest location rules are clearly documented.
- **Rollback:** Continue writing legacy manifests only; stop emitting version field if necessary.

#### 3.3: Add integrity checks as explicit command behaviour
- **Implementation:** Ensure that checksum production/validation and manifest completeness are explicit parts of the ingest workflow (and optionally available as a validation mode).
- **Acceptance criteria:**
  - Ingest outputs can be validated deterministically (hashes match, manifest references resolve).
  - Validation failures are surfaced consistently with clear exit codes.
- **Rollback:** Keep checksum generation but remove validation enforcement.

### Milestone 4: Clarify authoritative sources of truth (filesystem vs. database)
**Goal:** Remove ambiguity about what is authoritative and ensure secondary stores are regenerable.

#### 4.1: Specify authoritative representation per data category
- **Implementation:** Explicitly define which artifacts are authoritative (eg. raw GPX + manifests) and which are derived (indexes, caches, DB).
- **Acceptance criteria:**
  - A single statement exists for each persistent category: authoritative vs. derived.
  - "Derived" categories are documented as regenerable and non-authoritative.
- **Rollback:** Documentation only.

#### 4.2: Make database import/indexing explicitly derived
- **Implementation:** Treat database as content derived from manifests (or other authoritative artifacts) and ensure it can be rebuilt.
- **Acceptance criteria:**
  - A documented "rebuild index/db" workflow exists.
  - Rebuild produces equivalent results from the same authoritative inputs.
- **Rollback:** Keep existing DB behaviour but mark it as experimental/non-authoritative.

### Milestone 5: Enforce separation of responsibilities (layers)
**Goal:** Ensure procedural orchestration, domain logic, and adapters are cleanly separated without changing user-visible behaviour.

#### 5.1: Identify and extract domain functions behind stable interfaces
- **Implementation:** For each subcommand, isolate "core operations" as importable functions that are independent of CLI concerns.
- **Acceptance criteria:**
  - Commands become thin orchestration layers.
  - Core transformations can be tested without invoking the CLI.
- **Rollback:** Revert extraction changes; keep working behaiour via unified CLI.

#### 5.2: Isolate adapters explicitly (devices, filesystem, database)
- **Implementation:** Ensure device discover/mount logic, filesystem IO, and DB IO are behind explicit adapter modules with minimal leakage into domain logic.
- **Acceptance criteria:**
  - Domain logic does not import device-specific or database-specific modules directly.
  - Swapping adapters is structurally possible without rewriting domain logic.
- **Rollback:** Keep adapters in place but document coupling for future work.

### Milestone 6: Deprecate legacy entry points and reduce surface area
**Goal:** Consolidate to the unified entry point as the primary supported interface.

#### 6.1: Deprecation notice period
- **Implementation:** Add warnings when legacy modules are run directly, pointing users to the unified CLI.
- **Acceptance criteria:**
  - Warnings are clear and do not break workflows.
  - Documentation reflects the preferred interface.
- **Rollback:** Remove warnings; keep legacy behaviour.

#### 6.2: Retire legacy module execution paths
- **Implementation:** After an explicit deprecation window (see **Deprecation policy** below), remove or disable direct execution patterns while keeping internal functions intact.
- **Acceptance criteria:**
  - Unified CLI covers all supported workflows.
  - Release notes clearly communicate removal.
- **Rollback:** Reintroduce compatibility wrappers if needed.

### Deprecation policy
Legacy, script-style entry points will remain supported until the unified CLI has been exercised across **three consecutive releases**. During this period, legacy entry points may emit deprecation warnings but will continue to function without loss of capability.

After this deprecation window, legacy entry points may be removed or disabled, provided that:
- all documented workflows are supported by the unified CLI, and
- no data integrity or reproducibility guarantees are weakened.

### Validation strategy: Applies across milestones
- **Unit tests:** focus on domain functions (normalization transforms, checksum logic, manifest read/write).
- **Integration tests:** run ingest -> normalize -> analyze on test fixtures; verify artifact creation and invariants.
- **Data integrity checks:** verify SHA-256 manifest references resolve; confirm raw immutability (no writes under `_raw/` outside of ingestion).
- **Backwards compatibility:** ensure legacy entry points delegate correctly during transition.

### Rollout notes
- Prefer shipping migrations as small releases with clear release notes.
- Keep any on-disk layout transitions explicitly versioned and supported for a defined period (read old, write new), then retire legacy paths.


## 8. Conclusion and next steps

This document captures the current state, strengths, limitations, risks, and intended architectural direction of GPSmax as of January 2026. It reflects a transition from exploratory development toward a more deliberate and sustainable structure, without discarding the working foundations already in place.

The immediate value of this review is clarity:
- the current architecture is well understood and documented;
- existing strengths are explicitly preserved;
- architectural risks are identified and scoped; and
- a concrete, incremental migration path is defined.

### Near-term next steps
The following actions are recommended as the next phase of work, in order:

1. **Freeze this document** as the architectural reference for upcoming changes.
2. **Begin Milestone 1** of the migration plan by defining and documenting the unified command surface.
3. **Validate assumptions** by exercising the unified CLI wrapper without altering underlying behaviour.
4. **Iterate deliberately**, advancing one migration milestone at a time, guided by acceptance criteria rather than implementation convenience.

### Guiding principle going forward
Architectural changes should be justified by:
- documented pain points,
- clearly articulated risks, and
- alignment with the target architecture defined in Section 6.

This approach ensures that GPSmax continues to evolve intentionally, preserving data integrity and usability while remaining adaptable to future needs.

No new features should be introduced until the unified CLI and cross-cutting concerns have been stabilized, as outlined in the migration plan.
