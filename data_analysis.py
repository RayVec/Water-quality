import pandas as pd
from decimal import Decimal, InvalidOperation
import json
import sys
from datetime import datetime
import os
import logging

def convert_id_number_to_participant_id(number):
    hornsense_map_path = 'Participant_Hornsense_ID_Map.xlsx'
    if not os.path.exists(hornsense_map_path):
        logging.error(f"Hornsense ID mapping file not found: {hornsense_map_path}")
        return None

    try:
        hornsense_df = pd.read_excel(hornsense_map_path)
    except Exception as exc:
        logging.error(f"Failed to read Hornsense mapping file '{hornsense_map_path}': {exc}")
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

# --- Load Config and Get Input File Path --- 
try:
    with open('config.json', 'r') as config_file:
        config = json.load(config_file)
    
    # Get configuration values
    parameter_ranges = config['parameterRanges']
    parameter_types = config['parameterTypes']  # Load parameter types from config
    parameters = config['parameters']['all']  # Load parameter list from config
    # Allow environment variable override for data source path
    env_data_path = os.environ.get('DATA_SOURCE_PATH')
    if env_data_path:
        data_filename = env_data_path
    else:
        # Get the data source filename, default to 'data_source.xlsx'
        data_filename = config.get('data_source_filename', 'data_source.xlsx')
    
except FileNotFoundError:
    print("❌ Error: Configuration file 'config.json' not found.")
    sys.exit(1)
except json.JSONDecodeError:
    print("❌ Error: Configuration file 'config.json' is not valid JSON.")
    sys.exit(1)
except KeyError as e:
    print(f"❌ Error: Missing required key '{e}' in 'config.json'.")
    sys.exit(1)

# Construct the full file path (assuming script is run from project root)
file_path = os.path.join(".", data_filename) 

# Check if the input file path exists
if not os.path.exists(file_path):
    print(f"❌ Error: Input file '{data_filename}' not found at expected path '{file_path}'. Check config.json.")
    sys.exit(1)

print(f"Processing data from: {file_path}")
try:
    data = pd.read_excel(file_path)

    # Load Hornsense ID mapping
    hornsense_map_path = os.path.join('.', 'Participant_Hornsense_ID_Map.xlsx')
    if not os.path.exists(hornsense_map_path):
        print(f"❌ Error: Hornsense ID mapping file '{hornsense_map_path}' not found.")
        sys.exit(1)

    hornsense_df = pd.read_excel(hornsense_map_path)
    hornsense_df.columns = hornsense_df.columns.str.strip()
    HORNSENSE_ID_COLUMN = 'Hornsense User Name'
    PARTICIPANT_ID_COLUMN = 'Internal Participant ID'

    if PARTICIPANT_ID_COLUMN not in hornsense_df.columns or HORNSENSE_ID_COLUMN not in hornsense_df.columns:
        print("❌ Error: Hornsense ID mapping file is missing required columns.")
        sys.exit(1)

    hornsense_dict = hornsense_df.set_index(PARTICIPANT_ID_COLUMN)[HORNSENSE_ID_COLUMN].to_dict()
except Exception as e:
    print(f"❌ Error: Failed to read or process Excel file '{file_path}': {e}")
    sys.exit(1)
# --- End Load Config and Get Input File Path ---

# add monochloramine and chlorine to parameters list loaded from config
# Note: Ensure 'Chloramine' and 'Chlorine' ranges/types are defined in config.json if they need specific handling
if 'Chloramine' not in parameters:
    parameters.append('Chloramine')
if 'Chlorine' not in parameters:
    parameters.append('Chlorine')

# Map internal parameter names to source data column names
PARAMETER_COLUMN_MAP = {
    'Chloramine': 'Monochloramine',
    'Chlorine': 'Chlorine',
    'pH': 'pH',
    'Turbidity': 'Turbidity',
    'Nitrate': 'Nitrate',
    'Nitrite': 'Nitrite',
    'Ammonia': 'Ammonia',
    'Lead': 'Lead',
    'Bacteria': 'E.coli'
}

# Convert parameter ranges from config to the format needed by check_standard
standards = {}
for param, values in parameter_ranges.items():
    # Get parameter type from config
    param_type = parameter_types.get(param, 1)  # Default to type 1 if not found
    
    if param_type == 1:
        # Type 1: Use standard ranges (min, max) from the first two elements
        # Expected format in config: [min_standard, max_standard, max_bar_value]
        if isinstance(values, list) and len(values) >= 2 and not isinstance(values[0], str) and not isinstance(values[1], str):
            standards[param] = (values[0], values[1]) # Use only the first two values
        else:
            logging.warning(f"Invalid or insufficient range format for Type 1 parameter '{param}' in config.json: {values}. Requires at least two numeric values. Ignoring.")
    elif param_type == 3:
        # Type 3: Special case for Bacteria - expects "No" or [0, 0, 1]
        # Handle both "No" string and the [0, 0, 1] list format for Bacteria
        if isinstance(values, str) and values.upper() == "NO":
            standards[param] = "No"
        elif isinstance(values, list) and len(values) == 3 and values[0] == 0 and values[1] == 0:
             standards[param] = "No" # Treat [0, 0, 1] as equivalent to "No" for standard check
        else:
            logging.warning(f"Invalid format for Type 3 parameter '{param}' in config.json: {values}. Expected 'No' or [0, 0, 1]. Ignoring.")
    # Types 0 and 2 do not have explicit standards stored here
    # elif param_type == 2:
    #     standards[param] = None # Type 2: No specific range
    # elif param_type == 0:
    #     standards[param] = None # Type 0: Custom ranges
    else:
        # Default case for unknown types, no standard stored
        pass # Or potentially log a warning for unhandled type

# Clean column names by removing newline characters and extra spaces
data.columns = data.columns.str.replace('\n', '').str.strip()

# Convert Participant IDs using the conversion function
data['Participant_ID'] = data['Participant_ID'].apply(lambda x: convert_id_number_to_participant_id(x) 
                                                    if pd.notnull(x) else x)

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

# Function to check if value is within standard
def check_standard(value, param_type):
        
    # Get parameter type from config
    param_type_value = parameter_types.get(param_type, 1)
    
    # Convert value to float if it's a string and represents a number
    try:
        if isinstance(value, str):
            if value.replace('.', '', 1).isdigit():
                value = float(value)
    except (ValueError, TypeError):
        # do nothing
        pass
    
    # Type 1: Regulated standard
    if param_type_value == 1:
        if pd.isna(value):
            return None
        if param_type in standards:
            low, high = standards[param_type]
            try:
                return 1 if low <= float(value) <= high else 0
            except (ValueError, TypeError):
                return None
    # Type 2: No standard
    elif param_type_value == 2:
            return None
    # Type 3: Special case for Bacteria
    elif param_type_value == 3:
        try:
            return 1 if float(value) == 0 or pd.isna(value) else 0
        except (ValueError, TypeError):
            return None
    # Other types: No standard checking applies
    else:
        return None
        
    return None

# Group by Participant ID and Sample_date to combine records
combined_records = []
grouped = data.groupby(['Participant_ID', 'Sample_date'])

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

# Add this helper function near the top of the file
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

            source_param = PARAMETER_COLUMN_MAP.get(param, param)
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
            source_param = PARAMETER_COLUMN_MAP.get(param, param)
            
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
            
        # Old calculation logic (commented out)
        # Only consider parameters with types 1 and 3 for overall result calculation, 
        # exclude Chloramine and Chlorine, but include Disinfectant
        # overall_result = all(
        #     combined_record[f'{param}_{loc}_Standard'] in (1, None)
        #     for param in ([p for p in parameters if p not in ['Chloramine', 'Chlorine']] + ['Disinfectant'])
        #     for loc in ['Outdoor', 'FF', 'AF']
        #     if parameter_types.get(param, 1) in [1, 3]  # Only include type 1 and 3 parameters
        # )
        # 
        # combined_record['Overall_Result'] = 1 if overall_result else 0
        
        combined_records.append(combined_record)

# Convert to DataFrame for easier manipulation or export
combined_df = pd.DataFrame(combined_records)

# Handle NaN values
for record in combined_records:
    for key, value in record.items():
        if pd.isna(value):
            record[key] = None

# Export combined_records to JSON file
json_file_path = 'data.json'

with open(json_file_path, 'w') as json_file:
    json.dump(combined_records, json_file, indent=4, default=str)

print(f"Combined records have been exported to {json_file_path}")

