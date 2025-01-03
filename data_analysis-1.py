import pandas as pd

# Load the dataset
file_path = 'Sample-Data.csv'
data = pd.read_csv(file_path)

# Clean the column names by removing newline characters and extra spaces
data.columns = data.columns.str.replace('\n', '').str.strip()

# Convert Date and Time columns to a single DateTime column for easier comparison and analysis
data['DateTime'] = pd.to_datetime(
    data['Year'].astype(str) + '-' + data['Date'] + ' ' + data['Time'],
    format='%Y-%d-%b %I:%M %p',
    errors='coerce'  # Coerce invalid parsing into NaT (Not a Time)
)

# Filter the data to include only Out and AF samples
filtered_data = data[data['Sample Type'].isin(['Out', 'AF'])]

# Group by Participant ID and Date
combined_records = []
grouped = filtered_data.groupby(['Participant ID', 'Date'])

# Combine Out and AF samples for each participant on the same date
for (participant_id, date), group in grouped:
    out_sample = group[group['Sample Type'] == 'Out']
    af_sample = group[group['Sample Type'] == 'AF']
    
    # Ensure both Out and AF samples exist for this participant on this date
    if not out_sample.empty and not af_sample.empty:
        # Combine the two samples into one record
        combined_record = {
            'Participant ID': participant_id,
            'Year': out_sample['Year'].values[0],
            'Date': date,
            'Out Sample Time': out_sample['Time'].values[0],
            'AF Sample Time': af_sample['Time'].values[0],
            'Water System': out_sample['Water System'].values[0],
            'Source': out_sample['Source (1 = SW, GW = GW, Mix = Mix)'].values[0],
            'Disinfectant': out_sample['Disinfectant (1 = Mono, 2 = Chlorine)'].values[0],
            'Filter/Softener': out_sample['Filter = 1, Softener = 2'].values[0],
            # Combine parameters from both Out and AF samples with suffixes
            'Monochloramine_Out': out_sample['Monochloramine'].values[0],
            'Monochloramine_AF': af_sample['Monochloramine'].values[0],
            'Chlorine_Out': out_sample['Chlorine'].values[0],
            'Chlorine_AF': af_sample['Chlorine'].values[0],
            'Ammonia_Out': out_sample['Ammonia'].values[0],
            'Ammonia_AF': af_sample['Ammonia'].values[0],
            'Nitrate_Out': out_sample['Nitrate'].values[0],
            'Nitrate_AF': af_sample['Nitrate'].values[0],
            'Nitrite_Out': out_sample['Nitrite'].values[0],
            'Nitrite_AF': af_sample['Nitrite'].values[0],
            'pH_Out': out_sample['pH'].values[0],
            'pH_AF': af_sample['pH'].values[0],
            'Temperature_Out': out_sample['Temperature'].values[0],
            'Temperature_AF': af_sample['Temperature'].values[0],
            'Turbidity_Out': out_sample.get('Turbidity', pd.Series([None])).values[0],
            'Turbidity_AF': af_sample.get('Turbidity', pd.Series([None])).values[0],
            'Lead_Out': out_sample.get('Lead', pd.Series([None])).values[0],
            'Lead_AF': af_sample.get('Lead', pd.Series([None])).values[0],
            'E. coli_Out': out_sample['E. coli'].values[0],
            'E. coli_AF': af_sample['E. coli'].values[0]
        }
        combined_records.append(combined_record)

# Display the combined records
for record in combined_records:
    print(record)

