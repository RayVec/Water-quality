import os
from jinja2 import Environment, FileSystemLoader
import subprocess
import json
from datetime import datetime


def gen_report(output_file_name):
    print("begin generating report ", output_file_name.replace(".html", ".pdf"))
    command = "weasyprint "+output_file_name+" "+output_file_name.replace(".html", ".pdf")

    # Execute the shell command and capture the output
    result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    # result = subprocess.run(['bash', script_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    # print("stdout:", result.stdout)
    # print("stderr:", result.stderr)
    # Check the result
    if result.returncode == 0:
        print("Command executed successfully.")
        print("Output:", result.stdout, result.stderr)
    else:
        print("Error executing the command.")
        print("Error message:", result.stderr)


def gen_template(record):
    id = str(record["Participant ID"])
    # Use dictionary syntax to access the date
    date = record['date']   
    # Load the template environment
    env = Environment(loader=FileSystemLoader('./'))
    # script_path = './printall.sh'm 
    #check if a foler like /report_template/id/ exists, if not, create it
    if not os.path.exists('./reports/'+id):
        os.makedirs('./reports/'+id)
    # Load the template file
    template = env.get_template('./reports/template/template.html')
    # Render the template with the data
    output = template.render(record)
    output_file_name = "./reports/"+id+"/"+date+".html"
    # Create all parent directories
    os.makedirs(os.path.dirname(output_file_name), exist_ok=True)
    # Write the rendered content to an HTML file
    with open(output_file_name, 'w') as f:
        print("start to write the output", output_file_name)
        f.write(output)
        f.flush()  # Ensure data is written to disk
    gen_report(output_file_name)

file_path = 'data.json'  # Replace with your file path
water_utilities = {
    "Austin Water":{
        "name": "Austin Water",
        "website": "https://www.austintexas.gov/department/water",
        "phone": "311",
        "location": "625 E. 10th St. Austin, TX 78701",
        "annual_report": "https://www.austintexas.gov/sites/default/files/files/Water/WaterQualityReports/AW_WQR_Report_2023.pdf",
        "image":"../../icons/austin-water.png"
    },
    "Goforth":{
        "name": "Goforth",
        "website":"https://www.goforthwater.org/home.php?p=gf_home",
        "phone":"(512) 376-5695",
        "location":"Goforth SUD 8900 Niederwald Strasse Kyle, Texas 78640.",
        "annual_report":"https://www.goforthwater.org/pdf/Docs-AnnualWaterReport-2023.pdf",
        "image":"../../icons/goforth.png"
    },
    "City of Manor":{
        "name": "City of Manor",
        "website":"https://www.cityofmanor.org/",
        "phone":"(512) 272-5555",
        "location":"Manor City Hall 105 E. Eggleston St.",
        "annual_report":"https://www.cityofmanor.org/upload/page/0113/docs/2023%20Consumer%20Confidence%20Report%20for%20Public%20Water%20System%20CITY%20OF%20MANOR_v2.pdf",
        "image":"../../icons/city-of-manor.png"
    }
}
with open(file_path, 'r') as file:
    records = json.load(file)  # Load the JSON data as a Python list
    # direct convert the record["Sample_date"] to yyyy-mm-dd
    for record in records:
        record['date'] = datetime.strptime(str(record["Sample_date"]), '%m/%d/%Y').strftime('%Y-%m-%d')
        record["Participant_ID"] = record["Participant ID"]
        for parameter in ["Disinfectant", 'Nitrate', 'Nitrite', 'pH', 'Turbidity', 'Lead', 'Bacteria']:
            # if parameter's outdoor, af and ff standard are all 1, then set the parameter_standard to 1, or set it to be 0
            if record[parameter+'_Outdoor_Standard'] in [1,None] and record[parameter+'_FF_Standard'] in [1,None] and record[parameter+'_AF_Standard'] in [1,None]:
                record[parameter+'_Standard'] = 1
            else:
                record[parameter+'_Standard'] = 0

            water_utility=record["Water System"]
            if water_utility in water_utilities:
                record["water_utility"] = water_utilities[water_utility]
        gen_template(record)
    # for record in records:
    #     print(record)
    #     gen_template(record)
# except Exception as e:
#     print(e)
