import pandas as pd

# Read the Excel file
df = pd.read_excel('B6 Data.xlsx')

# Print column names to debug
print("Original column names:", df.columns.tolist())

# Rename columns to match Sample-Data.csv format
column_mapping = {
    'Sample_ID': 'Sample ID',
    'Participant_ID': 'Participant ID', 
    'Date': 'Date',
    'Water_system': 'Water System',
    'Disinfectant_type': 'Disinfectant (1 = Mono, 2 = Chlorine)',
    'Flush_type': 'Sample Type',
    # Removed the Filter_softener_none mapping
    'Monochloramine': 'Monochloramine',
    'Chlorine': 'Chlorine',
    'Ammonia': 'Ammonia', 
    'Nitrate': 'Nitrate',
    'Nitrite': 'Nitrite',
    'pH': 'pH',
    'Turbidity': 'Turbidity',
    'Lead': 'Lead',
    'E.coli': 'E. coli'
}

# Rename the columns
df = df.rename(columns=column_mapping)

# Print column names after renaming to debug
print("Renamed column names:", df.columns.tolist())

# Add missing columns with default values if needed
# Extract year from date before formatting the date
if 'Year' not in df.columns:
    # Convert to datetime first to extract year
    df['Date'] = pd.to_datetime(df['Date'])
    df['Year'] = df['Date'].dt.year

if 'Time' not in df.columns:
    df['Time'] = 'N/A'  # Default value

if 'Source (1 = SW, GW\n = GW, Mix = Mix\n)' not in df.columns:
    df['Source (1 = SW, GW\n = GW, Mix = Mix\n)'] = 'N/A'  # Default value

if 'Temperature' not in df.columns:
    df['Temperature'] = 'N/A'  # Default value

# Convert Disinfectant values
disinfectant_mapping = {
    'Chloramines': 1,  # Changed from 'Mono' to 'Chloramines'
    'Chlorine': 2
}
df['Disinfectant (1 = Mono, 2 = Chlorine)'] = df['Disinfectant (1 = Mono, 2 = Chlorine)'].map(disinfectant_mapping)

# Convert Sample Type values if needed
sample_type_mapping = {
    'Out': 'Out',
    'FF': 'FF',
    'AF': 'AF'
}
df['Sample Type'] = df['Sample Type'].map(sample_type_mapping)

# Convert E. coli values to match format and handle None values
df['E. coli'] = df['E. coli'].map({'Positive': 'Yes', 'Negative': 'No'})
df['E. coli'] = df['E. coli'].fillna('No')  # Convert None values to 'No'

# Format the date to match the target format (e.g., '24-May')
df['Date'] = df['Date'].dt.strftime('%-d-%b')

# Save to new CSV file
output_file = 'B6_Data_Converted.csv'
df.to_csv(output_file, index=False)

print(f"Conversion complete. Output saved to {output_file}")