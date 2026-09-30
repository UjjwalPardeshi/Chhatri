"""The data pipeline behind `make data` (SPEC §7, §17.4, §23; decision B6).

config: paths and training parameters · world: the demo world and the training history ·
model_store: ``artifacts/model`` · scenario_eval / area_claims / golden: the monsoon day through
the SPEC §24 functions and its golden numbers · search / level_search / day_search /
calibration_run: the SPEC §17.4 calibration fixed point · calibration_io: ``calibration.json`` ·
geo_files: the committed geography · manifest: ``MANIFEST.json`` · steps / cli: the command lines.
"""
