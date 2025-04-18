import pandas as pd
import json

# Read the Excel file
df = pd.read_excel('data_source.xlsx')

# Get basic information about the DataFrame
print("\n=== Basic Information ===")
print(f"Number of rows: {df.shape[0]}")
print(f"Number of columns: {df.shape[1]}")

# Get column names and their data types
print("\n=== Column Information ===")
column_info = df.dtypes.to_dict()
for col, dtype in column_info.items():
    print(f"{col}: {dtype}")

# Get sample data (first 5 rows)
print("\n=== Sample Data (First 5 Rows) ===")
print(df.head().to_string())

# Check for missing values
print("\n=== Missing Values ===")
missing_values = df.isnull().sum()
for col, count in missing_values.items():
    if count > 0:
        print(f"{col}: {count} missing values")

# Get unique values for each column
print("\n=== Unique Values per Column ===")
for col in df.columns:
    unique_values = df[col].unique()
    print(f"\n{col}:")
    print(f"Number of unique values: {len(unique_values)}")
    if len(unique_values) <= 10:  # Only show all values if there are 10 or fewer
        print(f"Values: {unique_values.tolist()}")
    else:
        print(f"First 5 values: {unique_values[:5].tolist()}")

# Save the analysis to a JSON file for reference
analysis = {
    "basic_info": {
        "rows": df.shape[0],
        "columns": df.shape[1],
        "column_types": {col: str(dtype) for col, dtype in column_info.items()}
    },
    "missing_values": missing_values.to_dict(),
    "unique_values": {col: df[col].unique().tolist() for col in df.columns}
}

with open('data_source_analysis.json', 'w') as f:
    json.dump(analysis, f, indent=4)

print("\nAnalysis saved to data_source_analysis.json") 