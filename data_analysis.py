import pandas as pd
from decimal import InvalidOperation
import json
import sys
import os
import logging
import numbers
from datetime import datetime
from typing import Any, Dict, List

import settings


# --- Record finishing (moved in from report_gen.py, Step 1 of the multi-type
# refactor: the engine should not carry water-quality-specific record logic).
# analyze() calls this on every record it produces, and any mock-data builder
# must call it too, so records.json is always "render-ready" regardless of
# where a record came from. ---

def is_valid_numeric_value(value: Any) -> bool:
    """Check if a value is a number (int, float, or numeric string)."""
    if value is None:
        return False
    if isinstance(value, numbers.Number):  # Catches int, float
        return True
    if isinstance(value, str):
        # Check if string represents a number (allowing for decimals)
        # Remove leading/trailing whitespace before checking
        return value.strip().replace('.', '', 1).isdigit()
    return False  # Not a number or numeric string


def _process_record_parameters(record: Dict[str, Any], all_parameters_config: List[str]) -> Dict[str, Any]:
    """Processes parameter-related data for a single record."""

    # Add a list to track which parameters to display
    record["display_parameters"] = []

    locations = ["Outdoor", "FF", "Filtered"]

    for parameter in all_parameters_config:
        # Check if the parameter has AT LEAST ONE valid numeric value for any location
        is_displayed = False
        for location in locations:
            value = record.get(f"{parameter}_{location}")
            # Use the helper function to check for numeric or None
            if is_valid_numeric_value(value) or value is None:
                is_displayed = True
                break  # Found a displayable value, no need to check other locations

        # Only include parameter in display list if it has valid data or is None
        if is_displayed:
            record["display_parameters"].append(parameter)

        # Calculate overall standard only across available locations
        standard_values = []
        for location in locations:
            standard_val = record.get(f'{parameter}_{location}_Standard')
            available_flag = record.get(f'{parameter}_{location}_Available')
            if available_flag is None or available_flag is True:
                standard_values.append(standard_val)

        if all(val in (1, None) for val in standard_values):
            record[f'{parameter}_Standard'] = 1
        else:
            record[f'{parameter}_Standard'] = 0  # At least one location is out of standard (and not None)

    # Calculate how many parameters meet the overall standard
    in_range_count = 0
    # Use count of parameters actually having data for this record
    total_parameters_count = len(record["display_parameters"])
    for parameter in record["display_parameters"]:  # Iterate through parameters with data only
        # Check if the overall standard for this parameter is 1
        # (standard calculation already handles None implicitly)
        if record.get(f'{parameter}_Standard') == 1:
            in_range_count += 1

    # Add count and total to the record for template rendering
    record['in_range_count'] = in_range_count
    record['total_parameters_count'] = total_parameters_count

    # Identify parameters not tested or without valid data for this specific record
    record['not_tested_parameters'] = []
    tested_params_set = set(record["display_parameters"])

    # Iterate the config list rather than a set difference: sets have no order, so
    # the previous version produced a different ordering on every run, which made
    # the same input generate byte-different PDFs.
    missing_params = [p for p in all_parameters_config if p not in tested_params_set]

    for param in missing_params:
        reason = "No data available for this parameter in the sample."
        # Check original fields for explanatory text (if it's a string and not numeric)
        outdoor_val = record.get(f'{param}_Outdoor')
        ff_val = record.get(f'{param}_FF')
        filtered_val = record.get(f'{param}_Filtered')

        # Prioritize explanatory text if available
        if isinstance(outdoor_val, str) and not is_valid_numeric_value(outdoor_val):
            reason = outdoor_val
        elif isinstance(ff_val, str) and not is_valid_numeric_value(ff_val):
            reason = ff_val
        elif isinstance(filtered_val, str) and not is_valid_numeric_value(filtered_val):
            reason = filtered_val

        record['not_tested_parameters'].append({
            'name': param,
            'reason': reason
        })

    return record  # Return the modified record


def finalize_record(record: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    """Turn a raw combined record into a render-ready one.

    Everything here used to be computed by report_gen.py at render time.
    Doing it once, here, means records.json is a self-contained artifact
    that doesn't depend on the moment it happens to be rendered, and any
    mock-data builder that calls this gets the exact same record shape a
    real batch does.
    """
    all_parameters = config['parameters']['all']
    water_utilities = config.get('waterUtilities', {})

    record['date'] = datetime.strptime(str(record.get("Sample_date", "")), '%m/%d/%Y').strftime('%Y-%m-%d')
    record = _process_record_parameters(record, all_parameters)

    water_utility_key = record.get("Water_System")
    if water_utility_key and water_utility_key in water_utilities:
        record["water_utility"] = water_utilities[water_utility_key]
    else:
        record["water_utility"] = None
        logging.warning(f"Water utility '{water_utility_key}' not found for {record.get('Participant_ID')}")

    record['latest_annual_report_year'] = datetime.now().year - 1

    # The engine-facing Record contract: id / date / language. `date` is set
    # above already; these two are aliases so the engine never has to know
    # this type calls them Participant_ID / Language.
    record['id'] = str(record["Participant_ID"])
    record['language'] = record.get("Language", "English")

    return record


# --- Excel batch -> records (today's analysis logic, unchanged except for
# taking its inputs as parameters instead of module-level globals) ---

def convert_id_number_to_participant_id(number, id_map_file: str):
    if not os.path.exists(id_map_file):
        logging.error(f"Hornsense ID mapping file not found: {id_map_file}")
        return None

    try:
        hornsense_df = pd.read_excel(id_map_file)
    except Exception as exc:
        logging.error(f"Failed to read Hornsense mapping file '{id_map_file}': {exc}")
        return None
    hornsense_df.columns = hornsense_df.columns.str.strip()

    internal_id_col = 'Internal Participant ID'
    if internal_id_col not in hornsense_df.columns:
        logging.error(f"Column '{internal_id_col}' not found in Hornsense mapping file.")
        return None

    padded_number = str(number).zfill(4)
    candidate_ids = [f'P{padded_number}T', f'P{padded_number}B', f'P{padded_number}H']

    match = hornsense_df[hornsense_df[internal_id_col].isin(candidate_ids)]
    if not match.empty:
        return match[internal_id_col].iloc[0]

    logging.warning(f"No Hornsense mapping found for participant number {number} using IDs {candidate_ids}")
    return None


def round_decimal(value):
    if pd.isna(value):
        return None
    try:
        if isinstance(value, (float, int)):
            return round(float(value), 2)
        elif isinstance(value, str):
            # Try to convert string to float
            return round(float(value), 2)
        else:
            return value
    except (ValueError, TypeError, InvalidOperation):
        # If conversion fails, return the original value
        return value


def analyze(source_path: str, config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Excel batch -> render-ready records. The sole data entry point for the
    water_quality type: reads the source workbook, resolves participant IDs,
    computes community averages (two passes: totals, then per-record values),
    and returns each record already finalized via finalize_record().
    """
    try:
        parameter_ranges = config['parameterRanges']
        parameter_types = config['parameterTypes']
        # 'measured' is what this stage computes: the reported parameters plus the
        # raw Chlorine/Chloramine columns that the virtual 'Disinfectant' resolves to.
        # The render side uses parameters.all, which omits those two.
        parameters = config['parameters']['measured']
        # Internal parameter name -> column name in the source workbook
        parameter_column_map = config['columnMap']
        id_map_file = str(settings.REFERENCE_DIR / config['files']['idMap'])
    except KeyError as e:
        print(f"❌ Error: Missing required key '{e}' in 'config.json'.")
        sys.exit(1)

    if not os.path.exists(source_path):
        print(f"❌ Error: Input workbook not found: {source_path}")
        sys.exit(1)

    print(f"Processing data from: {source_path}")
    try:
        data = pd.read_excel(source_path)

        if not os.path.exists(id_map_file):
            print(f"❌ Error: Hornsense ID mapping file '{id_map_file}' not found.")
            sys.exit(1)

        hornsense_df = pd.read_excel(id_map_file)
        hornsense_df.columns = hornsense_df.columns.str.strip()
        HORNSENSE_ID_COLUMN = 'Hornsense User Name'
        PARTICIPANT_ID_COLUMN = 'Internal Participant ID'

        if PARTICIPANT_ID_COLUMN not in hornsense_df.columns or HORNSENSE_ID_COLUMN not in hornsense_df.columns:
            print("❌ Error: Hornsense ID mapping file is missing required columns.")
            sys.exit(1)

        hornsense_dict = hornsense_df.set_index(PARTICIPANT_ID_COLUMN)[HORNSENSE_ID_COLUMN].to_dict()
    except Exception as e:
        print(f"❌ Error: Failed to read or process Excel file '{source_path}': {e}")
        sys.exit(1)

    # Convert parameter ranges from config to the format needed by check_standard
    standards: Dict[str, Any] = {}
    for param, values in parameter_ranges.items():
        param_type = parameter_types.get(param, 1)  # Default to type 1 if not found

        if param_type == 1:
            # Type 1: Use standard ranges (min, max) from the first two elements
            # Expected format in config: [min_standard, max_standard, max_bar_value]
            if isinstance(values, list) and len(values) >= 2 and not isinstance(values[0], str) and not isinstance(values[1], str):
                standards[param] = (values[0], values[1])  # Use only the first two values
            else:
                logging.warning(f"Invalid or insufficient range format for Type 1 parameter '{param}' in config.json: {values}. Requires at least two numeric values. Ignoring.")
        elif param_type == 3:
            # Type 3: Special case for Bacteria - expects "No" or [0, 0, 1]
            if isinstance(values, str) and values.upper() == "NO":
                standards[param] = "No"
            elif isinstance(values, list) and len(values) == 3 and values[0] == 0 and values[1] == 0:
                standards[param] = "No"  # Treat [0, 0, 1] as equivalent to "No" for standard check
            else:
                logging.warning(f"Invalid format for Type 3 parameter '{param}' in config.json: {values}. Expected 'No' or [0, 0, 1]. Ignoring.")
        # Types 0 and 2 do not have explicit standards stored here
        else:
            pass

    # Clean column names by removing newline characters and extra spaces
    data.columns = data.columns.str.replace('\n', '').str.strip()

    # Convert Participant IDs using the conversion function
    data['Participant_ID'] = data['Participant_ID'].apply(
        lambda x: convert_id_number_to_participant_id(x, id_map_file) if pd.notnull(x) else x
    )

    # Normalize flush types for consistent comparisons
    data['Flush_type_normalized'] = data['Flush_type'].astype(str).str.strip().str.lower()

    # Normalize filter status to detect filtered samples
    def normalize_filter_status(value):
        if pd.isna(value):
            return ''
        return str(value).strip().lower()

    data['Filter_softener_normalized'] = data['Filter_softener_none'].apply(normalize_filter_status)
    FILTER_KEYWORDS = {'filter', 'filtered'}
    data['is_filtered_sample'] = data['Filter_softener_normalized'].isin(FILTER_KEYWORDS)

    def check_standard(value, param_type):
        param_type_value = parameter_types.get(param_type, 1)

        try:
            if isinstance(value, str):
                if value.replace('.', '', 1).isdigit():
                    value = float(value)
        except (ValueError, TypeError):
            pass

        if param_type_value == 1:
            if pd.isna(value):
                return None
            if param_type in standards:
                low, high = standards[param_type]
                try:
                    return 1 if low <= float(value) <= high else 0
                except (ValueError, TypeError):
                    return None
        elif param_type_value == 2:
            return None
        elif param_type_value == 3:
            try:
                return 1 if float(value) == 0 or pd.isna(value) else 0
            except (ValueError, TypeError):
                return None
        else:
            return None

        return None

    # Community aggregation helpers
    DISINFECTANT_PARAMS = {'Disinfectant', 'Chloramine', 'Chlorine'}
    COHORT_ALL = 'all'
    COHORT_CHLORINE = 'chlorine'
    COHORT_CHLORAMINE = 'chloramine'

    def create_location_totals():
        return {
            'Outdoor': {'sum': 0.0, 'count': 0},
            'FF': {'sum': 0.0, 'count': 0},
            'Filtered': {'sum': 0.0, 'count': 0},
        }

    def initialize_totals():
        totals = {COHORT_ALL: {}}
        for param in parameters:
            totals[COHORT_ALL][param] = create_location_totals()

        disinfectant_specific_params = ['Chlorine', 'Chloramine', 'Disinfectant']
        totals[COHORT_CHLORINE] = {param: create_location_totals() for param in disinfectant_specific_params}
        totals[COHORT_CHLORAMINE] = {param: create_location_totals() for param in disinfectant_specific_params}
        return totals

    total_parameters = initialize_totals()

    def normalize_disinfectant_type(value):
        if isinstance(value, str):
            cleaned = value.strip().lower()
            if 'chloramine' in cleaned:
                return COHORT_CHLORAMINE
            if 'chlorine' in cleaned:
                return COHORT_CHLORINE
        return None

    def update_totals(param, location_key, numeric_value, disinfectant_group, is_filtered_sample=False):
        if location_key not in ['Outdoor', 'FF', 'Filtered']:
            return

        if is_filtered_sample and location_key != 'Filtered':
            # Skip filtered values for non-filtered community averages
            return

        if location_key == 'Filtered' and param in DISINFECTANT_PARAMS:
            # Skip filtered values for disinfectant-related community averages
            return

        if param not in total_parameters[COHORT_ALL]:
            total_parameters[COHORT_ALL][param] = create_location_totals()

        # Always update the aggregate "all" cohort
        total_parameters[COHORT_ALL][param][location_key]['sum'] += numeric_value
        total_parameters[COHORT_ALL][param][location_key]['count'] += 1

        # Only track disinfectant-specific cohorts for the relevant parameters
        if param == 'Chlorine' and disinfectant_group == COHORT_CHLORINE and location_key != 'Filtered':
            totals = total_parameters[COHORT_CHLORINE].setdefault(param, create_location_totals())
            totals[location_key]['sum'] += numeric_value
            totals[location_key]['count'] += 1
        elif param == 'Chloramine' and disinfectant_group == COHORT_CHLORAMINE and location_key != 'Filtered':
            totals = total_parameters[COHORT_CHLORAMINE].setdefault(param, create_location_totals())
            totals[location_key]['sum'] += numeric_value
            totals[location_key]['count'] += 1

    def calculate_average(param, location_key, cohort=COHORT_ALL):
        if cohort is None:
            return None

        cohort_totals = total_parameters.get(cohort, {})
        param_totals = cohort_totals.get(param)
        if not param_totals:
            return None

        location_totals = param_totals.get(location_key, {})
        count = location_totals.get('count', 0)
        if count == 0:
            return None
        return round_decimal(location_totals['sum'] / count)

    def resolve_average_cohort(param, disinfectant_group):
        if param == 'Chlorine':
            return COHORT_CHLORINE if disinfectant_group == COHORT_CHLORINE else None
        if param == 'Chloramine':
            return COHORT_CHLORAMINE if disinfectant_group == COHORT_CHLORAMINE else None
        return COHORT_ALL

    # Group by Participant ID and Sample_date to combine records
    combined_records: List[Dict[str, Any]] = []
    grouped = data.groupby(['Participant_ID', 'Sample_date'])

    # First pass to calculate averages
    for (participant_id, date), group in grouped:
        out_sample = group[group['Flush_type_normalized'] == 'out']
        ff_sample = group[group['Flush_type_normalized'] == 'ff']
        filtered_sample = group[group['is_filtered_sample']]

        if out_sample.empty or ff_sample.empty:
            continue

        disinfectant_group = None
        if 'Disinfectant_type' in out_sample.columns and not out_sample.empty:
            disinfectant_group = normalize_disinfectant_type(out_sample['Disinfectant_type'].values[0])

        for location_key, sample_df in [('Outdoor', out_sample), ('FF', ff_sample), ('Filtered', filtered_sample)]:
            if sample_df.empty:
                continue

            for param in parameters:
                if param == 'Disinfectant':
                    continue

                source_param = parameter_column_map.get(param, param)
                if source_param not in sample_df.columns:
                    continue

                value = sample_df[source_param].values[0]
                if pd.isna(value):
                    continue

                try:
                    numeric_value = round_decimal(value)
                    if isinstance(numeric_value, (int, float)):
                        is_filtered_sample = bool(sample_df['is_filtered_sample'].values[0]) if 'is_filtered_sample' in sample_df else False
                        update_totals(param, location_key, float(numeric_value), disinfectant_group, is_filtered_sample)
                except (ValueError, TypeError):
                    continue

    # Second pass to create combined records
    for (participant_id, date), group in grouped:
        out_sample = group[group['Flush_type_normalized'] == 'out']
        ff_sample = group[group['Flush_type_normalized'] == 'ff']
        filtered_sample = group[group['is_filtered_sample']]

        # Ensure all sample types exist for this participant on this date
        if not out_sample.empty and not ff_sample.empty:
            # Get the first sample for participant and date info
            first_sample = out_sample.iloc[0]

            disinfectant_group = None
            if 'Disinfectant_type' in out_sample.columns and not out_sample.empty:
                disinfectant_group = normalize_disinfectant_type(out_sample['Disinfectant_type'].values[0])

            report_evaluation = first_sample.get('Water_system_report_evaluation') if 'Water_system_report_evaluation' in first_sample else None
            if pd.isna(report_evaluation):
                report_evaluation = None
            elif isinstance(report_evaluation, str):
                cleaned_eval = report_evaluation.strip()
                if cleaned_eval.upper() in {'NA', 'N/A', ''}:
                    report_evaluation = None
                else:
                    report_evaluation = cleaned_eval

            combined_record = {
                'Participant_ID': participant_id,
                'Sample_date': pd.to_datetime(date).strftime('%m/%d/%Y'),
                'Language': first_sample['Language'],
                'Water_System': first_sample['Water_system_name'],
                'Water_System_Report_Link': first_sample['Water_system_report_link'],
                'Water_System_Phone_Number': first_sample['Water_system_phone_number'],
                'Water_System_Report_Evaluation': report_evaluation,
                'Results': first_sample['Results'] if 'Results' in first_sample else None
            }

            # Attach Hornsense ID if available
            combined_record['Hornsense_ID'] = hornsense_dict.get(participant_id)

            for param in parameters:
                source_param = parameter_column_map.get(param, param)

                # Get parameter type from config instead of hardcoding
                param_type = parameter_types.get(param, 1)  # Default to type 1 if not found

                combined_record[f'{param}_type'] = param_type
                cohort_key = resolve_average_cohort(param, disinfectant_group)

                # Outdoor values
                if source_param in out_sample.columns:
                    outdoor_value = out_sample[source_param].values[0]
                    combined_record[f'{param}_Outdoor'] = round_decimal(outdoor_value)
                    combined_record[f'{param}_Outdoor_Standard'] = check_standard(outdoor_value, param)
                    combined_record[f'{param}_Outdoor_Average'] = calculate_average(param, 'Outdoor', cohort_key)
                    # Add evaluation if available
                    eval_col = f'{source_param}_evaluation'
                    if eval_col in out_sample.columns and not pd.isna(out_sample[eval_col].values[0]):
                        combined_record[f'{param}_Outdoor_Evaluation'] = out_sample[eval_col].values[0]
                    else:
                        combined_record[f'{param}_Outdoor_Evaluation'] = None
                else:
                    combined_record[f'{param}_Outdoor'] = None
                    combined_record[f'{param}_Outdoor_Standard'] = None
                    combined_record[f'{param}_Outdoor_Average'] = None
                    combined_record[f'{param}_Outdoor_Evaluation'] = None

                # Indoor FF values
                if source_param in ff_sample.columns:
                    ff_value = ff_sample[source_param].values[0]
                    combined_record[f'{param}_FF'] = round_decimal(ff_value)
                    combined_record[f'{param}_FF_Standard'] = check_standard(ff_value, param)
                    combined_record[f'{param}_FF_Average'] = calculate_average(param, 'FF', cohort_key)
                    # Add evaluation if available
                    eval_col = f'{source_param}_evaluation'
                    if eval_col in ff_sample.columns and not pd.isna(ff_sample[eval_col].values[0]):
                        combined_record[f'{param}_FF_Evaluation'] = ff_sample[eval_col].values[0]
                    else:
                        combined_record[f'{param}_FF_Evaluation'] = None
                else:
                    combined_record[f'{param}_FF'] = None
                    combined_record[f'{param}_FF_Standard'] = None
                    combined_record[f'{param}_FF_Average'] = None
                    combined_record[f'{param}_FF_Evaluation'] = None

                # Indoor AF values
                filter_value = None
                filter_eval_value = None
                if not filtered_sample.empty and source_param in filtered_sample.columns:
                    filter_value = filtered_sample[source_param].values[0]
                    eval_col = f'{source_param}_evaluation'
                    if eval_col in filtered_sample.columns and not pd.isna(filtered_sample[eval_col].values[0]):
                        filter_eval_value = filtered_sample[eval_col].values[0]

                filtered_available = filter_value is not None and not pd.isna(filter_value)

                combined_record[f'{param}_Filtered_Available'] = filtered_available
                combined_record[f'{param}_Filtered'] = round_decimal(filter_value) if filtered_available else None
                combined_record[f'{param}_Filtered_Standard'] = check_standard(filter_value, param) if filtered_available else None
                combined_record[f'{param}_Filtered_Average'] = calculate_average(param, 'Filtered', cohort_key) if filtered_available else None

                combined_record[f'{param}_Filtered_Evaluation'] = filter_eval_value if filtered_available else None

                # Check if all standards for this parameter are either 1 or None
                if all(combined_record[f'{param}_{loc}_Standard'] in (1, None) for loc in ['Outdoor', 'FF', 'Filtered']):
                    combined_record[f'{param}_Overall'] = 1
                else:
                    combined_record[f'{param}_Overall'] = 0

            # Handle Disinfectant based on Disinfectant_type
            combined_record['Disinfectant_type'] = 1
            if out_sample['Disinfectant_type'].values[0] == 'Chloramines':
                combined_record['Disinfectant_Outdoor'] = combined_record['Chloramine_Outdoor']
                combined_record['Disinfectant_Source'] = 'Chloramine'
                combined_record['Disinfectant_Outdoor_Standard'] = combined_record['Chloramine_Outdoor_Standard']
                combined_record['Disinfectant_Outdoor_Average'] = combined_record['Chloramine_Outdoor_Average']
                combined_record['Disinfectant_Outdoor_Evaluation'] = combined_record['Chloramine_Outdoor_Evaluation']

                combined_record['Disinfectant_FF'] = combined_record['Chloramine_FF']
                combined_record['Disinfectant_FF_Standard'] = combined_record['Chloramine_FF_Standard']
                combined_record['Disinfectant_FF_Average'] = combined_record['Chloramine_FF_Average']
                combined_record['Disinfectant_FF_Evaluation'] = combined_record['Chloramine_FF_Evaluation']

                combined_record['Disinfectant_Filtered_Available'] = combined_record.get('Chloramine_Filtered_Available', False)
                combined_record['Disinfectant_Filtered'] = combined_record['Chloramine_Filtered'] if combined_record['Disinfectant_Filtered_Available'] else None
                combined_record['Disinfectant_Filtered_Standard'] = combined_record['Chloramine_Filtered_Standard'] if combined_record['Disinfectant_Filtered_Available'] else None
                combined_record['Disinfectant_Filtered_Average'] = combined_record['Chloramine_Filtered_Average'] if combined_record['Disinfectant_Filtered_Available'] else None
                combined_record['Disinfectant_Filtered_Evaluation'] = combined_record['Chloramine_Filtered_Evaluation'] if combined_record['Disinfectant_Filtered_Available'] else None

                combined_record['Disinfectant_Overall'] = combined_record['Chloramine_Overall']
            else:
                combined_record['Disinfectant_Outdoor'] = combined_record['Chlorine_Outdoor']
                combined_record['Disinfectant_Source'] = 'Chlorine'
                combined_record['Disinfectant_Outdoor_Standard'] = combined_record['Chlorine_Outdoor_Standard']
                combined_record['Disinfectant_Outdoor_Average'] = combined_record['Chlorine_Outdoor_Average']
                combined_record['Disinfectant_Outdoor_Evaluation'] = combined_record['Chlorine_Outdoor_Evaluation']

                combined_record['Disinfectant_FF'] = combined_record['Chlorine_FF']
                combined_record['Disinfectant_FF_Standard'] = combined_record['Chlorine_FF_Standard']
                combined_record['Disinfectant_FF_Average'] = combined_record['Chlorine_FF_Average']
                combined_record['Disinfectant_FF_Evaluation'] = combined_record['Chlorine_FF_Evaluation']

                combined_record['Disinfectant_Filtered_Available'] = combined_record.get('Chlorine_Filtered_Available', False)
                combined_record['Disinfectant_Filtered'] = combined_record['Chlorine_Filtered'] if combined_record['Disinfectant_Filtered_Available'] else None
                combined_record['Disinfectant_Filtered_Standard'] = combined_record['Chlorine_Filtered_Standard'] if combined_record['Disinfectant_Filtered_Available'] else None
                combined_record['Disinfectant_Filtered_Average'] = combined_record['Chlorine_Filtered_Average'] if combined_record['Disinfectant_Filtered_Available'] else None
                combined_record['Disinfectant_Filtered_Evaluation'] = combined_record['Chlorine_Filtered_Evaluation'] if combined_record['Disinfectant_Filtered_Available'] else None

                combined_record["Disinfectant_Overall"] = combined_record["Chlorine_Overall"]

            # Calculate overall result based on the Results field
            if combined_record.get('Results') == "Standard":
                combined_record['Overall_Result'] = 1
            else:
                combined_record['Overall_Result'] = 0

            combined_records.append(combined_record)

    # Handle NaN values
    for record in combined_records:
        for key, value in record.items():
            if pd.isna(value):
                record[key] = None

    return [finalize_record(record, config) for record in combined_records]


def main() -> None:
    # Every path for this run comes from the manifest named by $MANIFEST
    manifest = settings.load_manifest()

    try:
        config = settings.load_config()
    except FileNotFoundError:
        print("❌ Error: Configuration file 'config.json' not found.")
        sys.exit(1)
    except json.JSONDecodeError:
        print("❌ Error: Configuration file 'config.json' is not valid JSON.")
        sys.exit(1)

    records = analyze(manifest['source'], config)

    # Export records to the path the manifest designates
    json_file_path = manifest['records']
    os.makedirs(os.path.dirname(json_file_path), exist_ok=True)

    with open(json_file_path, 'w') as json_file:
        json.dump(records, json_file, indent=4, default=str)

    print(f"Combined records have been exported to {json_file_path}")


if __name__ == "__main__":
    main()
