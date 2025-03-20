import pandas as pd
import csv

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

# Function to check if a value is within standard range
def is_within_standard(value, param):
    if pd.isna(value):
        return True  # Consider missing values as within range
    
    if param == 'Bacteria':
        return value == standards[param]
    else:
        low, high = standards[param]
        return low <= value <= high

# Load the dataset
df = pd.read_csv('/Users/ray/Projects/WCWH/Water-quality/B6_Data_Converted.csv')

# Initialize list to store out-of-range results
csv_rows = []

# Process each row in the dataset
for _, row in df.iterrows():
    participant_id = row['Participant ID']
    sample_id = row['Sample ID']
    sample_type = row['Sample Type']
    date = row['Date']
    water_system = row['Water System']
    
    # Special handling for Disinfectant based on Disinfectant_type
    disinfectant_type = row['Disinfectant (1 = Mono, 2 = Chlorine)']
    if disinfectant_type == 1:  # Monochloramine
        disinfectant_value = row['Monochloramine']
        disinfectant_name = 'Monochloramine'
    else:  # Chlorine
        disinfectant_value = row['Chlorine']
        disinfectant_name = 'Chlorine'
    
    if not is_within_standard(disinfectant_value, 'Disinfectant'):
        if isinstance(standards['Disinfectant'], tuple):
            standard_str = f"{standards['Disinfectant'][0]} - {standards['Disinfectant'][1]}"
        else:
            standard_str = standards['Disinfectant']
            
        csv_rows.append({
            'Participant ID': participant_id,
            'Sample ID': sample_id,
            'Date': date,
            'Water System': water_system,
            'Sample Type': sample_type,
            'Parameter': disinfectant_name,
            'Value': disinfectant_value,
            'Standard Range': standard_str,
            'Status': 'Out of Range'
        })
    
    # Check other parameters
    for param in ['Lead', 'Nitrate', 'Nitrite', 'Turbidity', 'pH']:
        value = row[param]
        if not is_within_standard(value, param):
            if isinstance(standards[param], tuple):
                standard_str = f"{standards[param][0]} - {standards[param][1]}"
            else:
                standard_str = standards[param]
                
            csv_rows.append({
                'Participant ID': participant_id,
                'Sample ID': sample_id,
                'Date': date,
                'Water System': water_system,
                'Sample Type': sample_type,
                'Parameter': param,
                'Value': value,
                'Standard Range': standard_str,
                'Status': 'Out of Range'
            })
    
    # Check Bacteria (E. coli)
    bacteria_value = row['E. coli']
    if not is_within_standard(bacteria_value, 'Bacteria'):
        csv_rows.append({
            'Participant ID': participant_id,
            'Sample ID': sample_id,
            'Date': date,
            'Water System': water_system,
            'Sample Type': sample_type,
            'Parameter': 'Bacteria',
            'Value': bacteria_value,
            'Standard Range': standards['Bacteria'],
            'Status': 'Out of Range'
        })

# Convert to DataFrame and save as CSV
output_df = pd.DataFrame(csv_rows)
csv_file = '/Users/ray/Projects/WCWH/Water-quality/out_of_range_results.csv'
output_df.to_csv(csv_file, index=False)

# Print summary of results
participant_count = len(output_df['Participant ID'].unique())
print(f"Found {participant_count} participants with out-of-range results")
print(f"Total out-of-range results: {len(csv_rows)}")
print(f"\nResults saved to {csv_file}")