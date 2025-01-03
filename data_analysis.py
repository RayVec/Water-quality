import pandas as pd
from decimal import Decimal
import json


# Load the dataset
file_path = 'Sample-Data.csv'
data = pd.read_csv(file_path)

# Clean column names by removing newline characters and extra spaces
data.columns = data.columns.str.replace('\n', '').str.strip()

# Convert 'E. coli' values from 'No' to 0 and 'Yes' to 1
data['E. coli'] = data['E. coli'].replace({'No': 0, 'Yes': 1})
# update the column name from E. coli to Bacteria
data.rename(columns={'E. coli': 'Bacteria'}, inplace=True)

# Verify cleaned column names
# print("Cleaned Columns:", data.columns.tolist())

# Define standards for parameters
standards = {
    'Disinfectant': (0.2, 4),
    'Monochloramine': (0.2, 4),
    'Chlorine': (0.2, 4),
    'Lead': (0, 15),
    'Nitrate': (0, 10),
    'Nitrite': (0, 1),
    'Turbidity': (0, 1),
    'pH': (6.5, 9.5),
    'Bacteria': 'No'
}

# Function to check if value is within standard
def check_standard(value, param_type):
    if pd.isna(value):
        return None
    if param_type in standards:
        if param_type == 'Bacteria':
            print(value)
            return 1 if value == 0 else 0
        if standards[param_type] is not None:
            low, high = standards[param_type]
            return 1 if low <= value <= high else 0
    return None

# Group by Participant ID and Date to combine records
combined_records = []
grouped = data.groupby(['Participant ID', 'Date'])

total_parameters={}
for param in ['Monochloramine', 'Chlorine', 'Ammonia', 'Nitrate', 
                      'Nitrite', 'pH', 'Temperature', 'Turbidity', 
                      'Lead', 'Bacteria']:
            
            total_parameters[f'{param}_Outdoor_Average'] =0
            total_parameters[f'{param}_FF_Average'] =0
            total_parameters[f'{param}_AF_Average'] =0
record_number=0

# Add this helper function near the top of the file
def round_decimal(value):
    if isinstance(value, (float, Decimal)) and not pd.isna(value):
        return round(float(value), 2)
    return value

for (participant_id, date), group in grouped:
    # print(group)
    # print("--------------------------")
    out_sample = group[group['Sample Type'] == 'Out']
    ff_sample = group[group['Sample Type'] == 'FF']
    af_sample = group[group['Sample Type'] == 'AF']

     # Ensure all sample types exist for this participant on this date
    if not out_sample.empty and not ff_sample.empty and not af_sample.empty:
        record_number+=1
        for param in ['Monochloramine', 'Chlorine', 'Ammonia', 'Nitrate', 
                      'Nitrite', 'pH', 'Temperature', 'Turbidity', 
                      'Lead', 'Bacteria']:
            
            # if param=='Nitrite':
            #     print(param)
            #     print(af_sample[param].values[0])

            if not pd.isna(out_sample[param].values[0]):
                total_parameters[f'{param}_Outdoor_Average'] += round_decimal(Decimal(str(out_sample[param].values[0])))
                
            if not pd.isna(ff_sample[param].values[0]):
                total_parameters[f'{param}_FF_Average'] += round_decimal(Decimal(str(ff_sample[param].values[0])))
            if not pd.isna(af_sample[param].values[0]):
                total_parameters[f'{param}_AF_Average'] += round_decimal(Decimal(str(af_sample[param].values[0])))

# print(record_number, total_parameters)

for (participant_id, date), group in grouped:
    # print(group)
    # print("--------------------------")
    out_sample = group[group['Sample Type'] == 'Out']
    ff_sample = group[group['Sample Type'] == 'FF']
    af_sample = group[group['Sample Type'] == 'AF']
    print(out_sample)
    
    # Ensure all sample types exist for this participant on this date
    if not out_sample.empty and not ff_sample.empty and not af_sample.empty:
        
        combined_record = {
            'Participant ID': participant_id,
            'Sample_date': pd.to_datetime(f"{date}-{out_sample['Year'].values[0]}").strftime('%m/%d/%Y'),
            'Water System': out_sample['Water System'].values[0],
           
        }
        
        for param in ['Monochloramine', 'Chlorine', 'Ammonia', 'Nitrate', 
                      'Nitrite', 'pH', 'Temperature', 'Turbidity', 
                      'Lead', 'Bacteria']:
            
            param_type = 1 if param in ['Monochloramine','Chlorine', 'Lead', 'Nitrate', 
                                        'Nitrite', 'Turbidity', 'pH'] else 3 if param == 'Bacteria' else 2
            
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

            if pd.isna(combined_record[f'{param}_Outdoor']) and pd.isna(combined_record[f'{param}_FF']) and pd.isna(combined_record[f'{param}_AF']):
                combined_record[f'{param}_Overall'] = 0
            else:
                combined_record[f'{param}_Overall'] = 1
            
        
        # Calculate overall result
        overall_result = all(combined_record[f'{param}_{loc}_Standard'] in (1,None) 
                             for param in ['Chlorine', 'Lead', 
                                           'Nitrate', 'Nitrite', 
                                           'Turbidity', 'pH', 
                                           'Bacteria']
                             for loc in ['Outdoor', 'FF', 'AF'])
        
        combined_record['Overall_Result'] = 1 if overall_result else 0

        
        combined_record['Disinfectant_type'] = 1
        if out_sample['Disinfectant (1 = Mono, 2 = Chlorine)'].values[0]==1:
            combined_record['Disinfectant_Outdoor'] = combined_record['Monochloramine_Outdoor']
            combined_record['Disinfectant_Outdoor_Standard'] = combined_record['Monochloramine_Outdoor_Standard']
            combined_record['Disinfectant_Outdoor_Average'] = combined_record['Monochloramine_Outdoor_Average']
        else:
            combined_record['Disinfectant_Outdoor'] = combined_record['Chlorine_Outdoor']
            combined_record['Disinfectant_Outdoor_Standard'] = combined_record['Chlorine_Outdoor_Standard']
            combined_record['Disinfectant_Outdoor_Average'] = combined_record['Chlorine_Outdoor_Average']
        if ff_sample['Disinfectant (1 = Mono, 2 = Chlorine)'].values[0]==1:
            combined_record['Disinfectant_FF'] = combined_record['Monochloramine_FF']
            combined_record['Disinfectant_FF_Standard'] = combined_record['Monochloramine_FF_Standard']
            combined_record['Disinfectant_FF_Average'] = combined_record['Monochloramine_FF_Average']
        else:
            combined_record['Disinfectant_FF'] = combined_record['Chlorine_FF']
            combined_record['Disinfectant_FF_Standard'] = combined_record['Chlorine_FF_Standard']
            combined_record['Disinfectant_FF_Average'] = combined_record['Chlorine_FF_Average']
        if af_sample['Disinfectant (1 = Mono, 2 = Chlorine)'].values[0]==1:
            combined_record['Disinfectant_AF'] = combined_record['Monochloramine_AF']
            combined_record['Disinfectant_AF_Standard'] = combined_record['Monochloramine_AF_Standard']
        else:
            combined_record['Disinfectant_AF'] = combined_record['Chlorine_AF']
            combined_record['Disinfectant_AF_Standard'] = combined_record['Chlorine_AF_Standard']
        
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

