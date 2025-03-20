import pandas as pd
from decimal import Decimal
import json
import sys

# Load the shared configuration
with open('config.json', 'r') as config_file:
    config = json.load(config_file)
    parameter_ranges = config['parameterRanges']
    parameter_types = config['parameterTypes']  # Load parameter types from config
    parameters = config['parameters']['all']  # Load parameter list from config

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
file_path = sys.argv[1] if len(sys.argv) > 1 else 'B6_Data_Converted.csv'
data = pd.read_csv(file_path)

# Clean column names by removing newline characters and extra spaces
data.columns = data.columns.str.replace('\n', '').str.strip()

# Convert 'E. coli' values from 'No' to 0 and 'Yes' to 1
data['E. coli'] = data['E. coli'].replace({'No': 0, 'Yes': 1})
# update the column name from E. coli to Bacteria
data.rename(columns={'E. coli': 'Bacteria'}, inplace=True)

# Verify cleaned column names
# print("Cleaned Columns:", data.columns.tolist())

# Function to check if value is within standard
def check_standard(value, param_type):
    if pd.isna(value):
        return None
        
    # Get parameter type from config
    param_type_value = parameter_types.get(param_type, 1)
    
    # Type 1: Check against standard range
    if param_type_value == 1:
        if param_type in standards:
            low, high = standards[param_type]
            return 1 if low <= value <= high else 0
    # Type 2: Check if value is larger than 1
    elif param_type_value == 2:
        return 1 if value >= 1 else 0
    # Type 3: Special case for Bacteria
    elif param_type_value == 3 :
        return 1 if value == 0 else 0
    # Other types: No standard checking applies
    else:
        return None
        
    return None

# Group by Participant ID and Date to combine records
combined_records = []
grouped = data.groupby(['Participant ID', 'Date'])

# Initialize total_parameters using config parameters
total_parameters = {}
for param in parameters:
    total_parameters[f'{param}_Outdoor_Average'] = 0
    total_parameters[f'{param}_FF_Average'] = 0
    total_parameters[f'{param}_AF_Average'] = 0
record_number = 0

# Add this helper function near the top of the file
def round_decimal(value):
    if isinstance(value, (float, Decimal)) and not pd.isna(value):
        return round(float(value), 2)
    return value

# Replace hardcoded parameter lists with config version
for (participant_id, date), group in grouped:
    # print(group)
    # print("--------------------------")
    out_sample = group[group['Sample Type'] == 'Out']
    ff_sample = group[group['Sample Type'] == 'FF']
    af_sample = group[group['Sample Type'] == 'AF']

     # Ensure all sample types exist for this participant on this date
    if not out_sample.empty and not ff_sample.empty and not af_sample.empty:
        record_number+=1
        for param in parameters:  # Use parameters from config instead of hardcoded list
            
            # if param=='Nitrite':
            #     print(param)
            #     print(af_sample[param].values[0])

            if not pd.isna(out_sample[param].values[0]):
                total_parameters[f'{param}_Outdoor_Average'] += round_decimal(Decimal(str(out_sample[param].values[0])))
                
            if not pd.isna(ff_sample[param].values[0]):
                total_parameters[f'{param}_FF_Average'] += round_decimal(Decimal(str(ff_sample[param].values[0])))
            if not pd.isna(af_sample[param].values[0]):
                total_parameters[f'{param}_AF_Average'] += round_decimal(Decimal(str(af_sample[param].values[0])))

for (participant_id, date), group in grouped:
    # print(group)
    # print("--------------------------")
    out_sample = group[group['Sample Type'] == 'Out']
    ff_sample = group[group['Sample Type'] == 'FF']
    af_sample = group[group['Sample Type'] == 'AF']    
    # Ensure all sample types exist for this participant on this date
    if not out_sample.empty and not ff_sample.empty and not af_sample.empty:
        
        combined_record = {
            'Participant ID': participant_id,
            'Sample_date': pd.to_datetime(f"{date}-{out_sample['Year'].values[0]}").strftime('%m/%d/%Y'),
            'Water System': out_sample['Water System'].values[0],
        }
        
        for param in parameters:  # Changed from hardcoded list to config parameters
            
            # Get parameter type from config instead of hardcoding
            param_type = parameter_types.get(param, 1)  # Default to type 1 if not found
            
            combined_record[f'{param}_type'] = param_type
            
            # Outdoor values
            combined_record[f'{param}_Outdoor'] = round_decimal(out_sample[param].values[0])
            combined_record[f'{param}_Outdoor_Standard'] = check_standard(out_sample[param].values[0], param)
            combined_record[f'{param}_Outdoor_Average'] = round_decimal(total_parameters[f'{param}_Outdoor_Average']/record_number)
            
            # Indoor FF values
            combined_record[f'{param}_FF'] = round_decimal(ff_sample[param].values[0])
            combined_record[f'{param}_FF_Standard'] = check_standard(ff_sample[param].values[0], param)
            combined_record[f'{param}_FF_Average'] = round_decimal(total_parameters[f'{param}_FF_Average']/record_number)
            
            # Indoor AF values
            combined_record[f'{param}_AF'] = round_decimal(af_sample[param].values[0])
            combined_record[f'{param}_AF_Standard'] = check_standard(af_sample[param].values[0], param)
            combined_record[f'{param}_AF_Average'] = round_decimal(total_parameters[f'{param}_AF_Average']/record_number)

            # Check if all standards for this parameter are either 1 or None
            if all(combined_record[f'{param}_{loc}_Standard'] in (1, None) for loc in ['Outdoor', 'FF', 'AF']):
                combined_record[f'{param}_Overall'] = 1
            else:
                combined_record[f'{param}_Overall'] = 0

        
        combined_record['Disinfectant_type'] = 1
        if out_sample['Disinfectant (1 = Mono, 2 = Chlorine)'].values[0]==1:
            combined_record['Disinfectant_Outdoor'] = combined_record['Monochloramine_Outdoor']
            combined_record['Disinfectant_Outdoor_Standard'] = combined_record['Monochloramine_Outdoor_Standard']
            combined_record['Disinfectant_Outdoor_Average'] = combined_record['Monochloramine_Outdoor_Average']
            combined_record['Disinfectant_FF'] = combined_record['Monochloramine_FF']
            combined_record['Disinfectant_FF_Standard'] = combined_record['Monochloramine_FF_Standard']
            combined_record['Disinfectant_FF_Average'] = combined_record['Monochloramine_FF_Average']
            combined_record['Disinfectant_AF'] = combined_record['Monochloramine_AF']
            combined_record['Disinfectant_AF_Standard'] = combined_record['Monochloramine_AF_Standard']
            combined_record['Disinfectant_Overall'] = combined_record['Monochloramine_Overall']
        else:
            combined_record['Disinfectant_Outdoor'] = combined_record['Chlorine_Outdoor']
            combined_record['Disinfectant_Outdoor_Standard'] = combined_record['Chlorine_Outdoor_Standard']
            combined_record['Disinfectant_Outdoor_Average'] = combined_record['Chlorine_Outdoor_Average']
            combined_record['Disinfectant_FF'] = combined_record['Chlorine_FF']
            combined_record['Disinfectant_FF_Standard'] = combined_record['Chlorine_FF_Standard']
            combined_record['Disinfectant_FF_Average'] = combined_record['Chlorine_FF_Average']
            combined_record['Disinfectant_AF'] = combined_record['Chlorine_AF']
            combined_record['Disinfectant_AF_Standard'] = combined_record['Chlorine_AF_Standard']
            combined_record["Disinfectant_Overall"] = combined_record["Chlorine_Overall"]
        # if ff_sample['Disinfectant (1 = Mono, 2 = Chlorine)'].values[0]==1:
        #     combined_record['Disinfectant_FF'] = combined_record['Monochloramine_FF']
        #     combined_record['Disinfectant_FF_Standard'] = combined_record['Monochloramine_FF_Standard']
        #     combined_record['Disinfectant_FF_Average'] = combined_record['Monochloramine_FF_Average']
        # else:
        #     combined_record['Disinfectant_FF'] = combined_record['Chlorine_FF']
        #     combined_record['Disinfectant_FF_Standard'] = combined_record['Chlorine_FF_Standard']
        #     combined_record['Disinfectant_FF_Average'] = combined_record['Chlorine_FF_Average']
        # if af_sample['Disinfectant (1 = Mono, 2 = Chlorine)'].values[0]==1:
        #     combined_record['Disinfectant_AF'] = combined_record['Monochloramine_AF']
        #     combined_record['Disinfectant_AF_Standard'] = combined_record['Monochloramine_AF_Standard']
        # else:
        #     combined_record['Disinfectant_AF'] = combined_record['Chlorine_AF']
        #     combined_record['Disinfectant_AF_Standard'] = combined_record['Chlorine_AF_Standard']
        
        # Calculate overall result
        # Only consider parameters with types 1 and 3 for overall result calculation, 
        # exclude Monochloramine and Chlorine, but include Disinfectant
        overall_result = all(
            combined_record[f'{param}_{loc}_Standard'] in (1, None)
            for param in ([p for p in parameters if p not in ['Monochloramine', 'Chlorine']] + ['Disinfectant'])
            for loc in ['Outdoor', 'FF', 'AF']
            if parameter_types.get(param, 1) in [1, 3]  # Only include type 1 and 3 parameters
        )
        
        combined_record['Overall_Result'] = 1 if overall_result else 0
        combined_records.append(combined_record)

# Convert to DataFrame for easier manipulation or export
combined_df = pd.DataFrame(combined_records)

# Display the combined records
# print(combined_df.head())

for record in combined_records:
    for key, value in record.items():
        if pd.isna(value):
            record[key] = None


# Export combined_records to JSON file
json_file_path = 'data.json'

with open(json_file_path, 'w') as json_file:
    json.dump(combined_records, json_file, indent=4, default=str)

print(f"Combined records have been exported to {json_file_path}")

