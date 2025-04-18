import pandas as pd
from decimal import Decimal, InvalidOperation
import json
import sys
from datetime import datetime

def convert_id_number_to_participant_id(number):
    # Read the WCWH Participant.csv file
    wcwh_df = pd.read_csv('WCWH Participant.csv')
    
    # Convert number to the format we're looking for (e.g., 88 -> '0088')
    padded_number = str(number).zfill(4)
    
    # Look for any ID that contains this number
    matching_ids = wcwh_df[wcwh_df['Participant ID'].str.contains(f'P{padded_number}[TBH]', regex=True)]
    
    if len(matching_ids) > 0:
        return matching_ids['Participant ID'].iloc[0]
    else:
        return None

# Load the shared configuration
with open('config.json', 'r') as config_file:
    config = json.load(config_file)
    parameter_ranges = config['parameterRanges']
    parameter_types = config['parameterTypes']  # Load parameter types from config
    parameters = config['parameters']['all']  # Load parameter list from config

# add monochloramine and chlorine to parameters
parameters.append('Chloramine')
parameters.append('Chlorine')

# Convert parameter ranges to standards format based on parameter types
standards = {}
for param, values in parameter_ranges.items():
    # Get parameter type from config
    param_type = parameter_types.get(param, 1)  # Default to type 1 if not found
    
    if param_type == 1:
        # Type 1: Use standard ranges (min, max)
        if isinstance(values, list) and not isinstance(values[0], str):
            standards[param] = (values[0], values[1])
    elif param_type == 3:
        # Type 3: Special case for Bacteria
        standards[param] = "No"
    elif param_type == 2:
        # Type 2: No specific range, just check if value >= 1
        standards[param] = None
    elif param_type == 0:
        # Type 0: Custom ranges with labels, no standard checking
        standards[param] = None
    else:
        # Default case
        standards[param] = None

# Get file path from command line argument or use default
file_path = sys.argv[1] if len(sys.argv) > 1 else 'data_source.xlsx'
data = pd.read_excel(file_path)

# Clean column names by removing newline characters and extra spaces
data.columns = data.columns.str.replace('\n', '').str.strip()

# Convert Participant IDs using the conversion function
data['Participant_ID'] = data['Participant_ID'].apply(lambda x: convert_id_number_to_participant_id(x) 
                                                    if pd.notnull(x) else x)

# Function to check if value is within standard
def check_standard(value, param_type):
    if pd.isna(value):
        return None
        
    # Get parameter type from config
    param_type_value = parameter_types.get(param_type, 1)
    
    # Convert value to float if it's a string and represents a number
    try:
        if isinstance(value, str):
            if value.replace('.', '', 1).isdigit():
                value = float(value)
            else:
                return None
    except (ValueError, TypeError):
        return None
    
    # Type 1: Regulated standard
    if param_type_value == 1:
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
            return 1 if float(value) == 0 else 0
        except (ValueError, TypeError):
            return None
    # Other types: No standard checking applies
    else:
        return None
        
    return None

# Group by Participant ID and Sample_date to combine records
combined_records = []
grouped = data.groupby(['Participant_ID', 'Sample_date'])

# Initialize total_parameters using config parameters
total_parameters = {}
for param in parameters:
    total_parameters[f'{param}_Outdoor_Average'] = 0
    total_parameters[f'{param}_FF_Average'] = 0
    total_parameters[f'{param}_AF_Average'] = 0
record_number = 0

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
    out_sample = group[group['Flush_type'] == 'Out']
    ff_sample = group[group['Flush_type'] == 'FF']
    af_sample = group[group['Flush_type'] == 'AF']

    # Ensure all sample types exist for this participant on this date
    if not out_sample.empty and not ff_sample.empty and not af_sample.empty:
        record_number += 1
        for param in parameters:
            # skip disinfectant
            if param == 'Disinfectant':
                continue

            # Map parameter names from data_source.xlsx to parameters list
            param_map = {
                'Chloramine': 'Chloramine',
                'Chlorine': 'Chlorine',
                'pH': 'pH',
                'Turbidity': 'Turbidity',
                'Nitrate': 'Nitrate',
                'Nitrite': 'Nitrite',
                'Ammonia': 'Ammonia',
                'Lead': 'Lead',
                'E.coli': 'Bacteria'  # Map E.coli to Bacteria
            }
            
            source_param = param_map.get(param, param)
            
            if source_param in out_sample.columns and not pd.isna(out_sample[source_param].values[0]):
                try:
                    value = out_sample[source_param].values[0]
                    if isinstance(value, (int, float)) or (isinstance(value, str) and value.replace('.', '', 1).isdigit()):
                        total_parameters[f'{param}_Outdoor_Average'] += round_decimal(value)
                except (ValueError, TypeError):
                    pass
                
            if source_param in ff_sample.columns and not pd.isna(ff_sample[source_param].values[0]):
                try:
                    value = ff_sample[source_param].values[0]
                    if isinstance(value, (int, float)) or (isinstance(value, str) and value.replace('.', '', 1).isdigit()):
                        total_parameters[f'{param}_FF_Average'] += round_decimal(value)
                except (ValueError, TypeError):
                    pass
                
            if source_param in af_sample.columns and not pd.isna(af_sample[source_param].values[0]):
                try:
                    value = af_sample[source_param].values[0]
                    if isinstance(value, (int, float)) or (isinstance(value, str) and value.replace('.', '', 1).isdigit()):
                        total_parameters[f'{param}_AF_Average'] += round_decimal(value)
                except (ValueError, TypeError):
                    pass

# Second pass to create combined records
for (participant_id, date), group in grouped:
    out_sample = group[group['Flush_type'] == 'Out']
    ff_sample = group[group['Flush_type'] == 'FF']
    af_sample = group[group['Flush_type'] == 'AF']
    
    # Ensure all sample types exist for this participant on this date
    if not out_sample.empty and not ff_sample.empty and not af_sample.empty:
        # Get the first sample for participant and date info
        first_sample = out_sample.iloc[0]
        
        combined_record = {
            'Participant_ID': participant_id,
            'Sample_date': pd.to_datetime(date).strftime('%m/%d/%Y'),
            'Language': first_sample['Language'],
            'Water_System': first_sample['Water_system_name'],
            'Water_System_Report_Link': first_sample['Water_system_report_link'],
            'Water_System_Phone_Number': first_sample['Water_system_phone_number'],
            'Results': first_sample['Results'] if 'Results' in first_sample else None
        }
        
        for param in parameters:
            # Map parameter names from data_source.xlsx to parameters list
            param_map = {
                'Chloramine': 'Chloramine',
                'Chlorine': 'Chlorine',
                'pH': 'pH',
                'Turbidity': 'Turbidity',
                'Nitrate': 'Nitrate',
                'Nitrite': 'Nitrite',
                'Ammonia': 'Ammonia',
                'Lead': 'Lead',
                'E.coli': 'Bacteria'  # Map E.coli to Bacteria
            }
            
            source_param = param_map.get(param, param)
            
            if param == 'Disinfectant':
                # Skip disinfectant for now, will handle it separately
                continue
            
            # Get parameter type from config instead of hardcoding
            param_type = parameter_types.get(param, 1)  # Default to type 1 if not found
            
            combined_record[f'{param}_type'] = param_type
            
            # Outdoor values
            if source_param in out_sample.columns:
                combined_record[f'{param}_Outdoor'] = round_decimal(out_sample[source_param].values[0])
                combined_record[f'{param}_Outdoor_Standard'] = check_standard(out_sample[source_param].values[0], param)
                combined_record[f'{param}_Outdoor_Average'] = round_decimal(total_parameters[f'{param}_Outdoor_Average']/record_number) if record_number > 0 else None
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
                combined_record[f'{param}_FF'] = round_decimal(ff_sample[source_param].values[0])
                combined_record[f'{param}_FF_Standard'] = check_standard(ff_sample[source_param].values[0], param)
                combined_record[f'{param}_FF_Average'] = round_decimal(total_parameters[f'{param}_FF_Average']/record_number) if record_number > 0 else None
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
            if source_param in af_sample.columns:
                combined_record[f'{param}_AF'] = round_decimal(af_sample[source_param].values[0])
                combined_record[f'{param}_AF_Standard'] = check_standard(af_sample[source_param].values[0], param)
                combined_record[f'{param}_AF_Average'] = round_decimal(total_parameters[f'{param}_AF_Average']/record_number) if record_number > 0 else None
                # Add evaluation if available
                eval_col = f'{source_param}_evaluation'
                if eval_col in af_sample.columns and not pd.isna(af_sample[eval_col].values[0]):
                    combined_record[f'{param}_AF_Evaluation'] = af_sample[eval_col].values[0]
                else:
                    combined_record[f'{param}_AF_Evaluation'] = None
            else:
                combined_record[f'{param}_AF'] = None
                combined_record[f'{param}_AF_Standard'] = None
                combined_record[f'{param}_AF_Average'] = None
                combined_record[f'{param}_AF_Evaluation'] = None

            # Check if all standards for this parameter are either 1 or None
            if all(combined_record[f'{param}_{loc}_Standard'] in (1, None) for loc in ['Outdoor', 'FF', 'AF']):
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
            
            combined_record['Disinfectant_AF'] = combined_record['Chloramine_AF']
            combined_record['Disinfectant_AF_Standard'] = combined_record['Chloramine_AF_Standard']
            combined_record['Disinfectant_AF_Average'] = combined_record['Chloramine_AF_Average']
            combined_record['Disinfectant_AF_Evaluation'] = combined_record['Chloramine_AF_Evaluation']
            
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
            
            combined_record['Disinfectant_AF'] = combined_record['Chlorine_AF']
            combined_record['Disinfectant_AF_Standard'] = combined_record['Chlorine_AF_Standard']
            combined_record['Disinfectant_AF_Average'] = combined_record['Chlorine_AF_Average']
            combined_record['Disinfectant_AF_Evaluation'] = combined_record['Chlorine_AF_Evaluation']
            
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

