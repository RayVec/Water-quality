from jinja2 import Environment, FileSystemLoader
import subprocess
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

def gen_report(id):
    print("begin generating report")
    command = "weasyprint output_"+id+".html report_"+id+".pdf"

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


def gen_template(data):
    id = str(data["_id"])
    # Load the template environment
    env = Environment(loader=FileSystemLoader('./'))
    # script_path = './printall.sh'
    # Load the template file
    template = env.get_template('template.html')
    print(data["overall_result"])

    # Render the template with the data
    output = template.render(data)
    output_file_name = "output_"+id+".html"
    # Write the rendered content to an HTML file
    with open(output_file_name, 'w') as f:
        print("start to write the output", output_file_name)
        f.write(output)
        f.flush()  # Ensure data is written to disk
    gen_report(id)

uri = "mongodb+srv://rayvec:rayvec@cluster0.e6oynif.mongodb.net/?retryWrites=true&w=majority"
# Create a new client and connect to the server
client = MongoClient(uri, server_api=ServerApi('1'))
# Send a ping to confirm a successful connection
# try:
database = client.get_database("wcwh")
collection = database.get_collection("water_quality")
records = collection.find()
for record in records:
    gen_template(record)
# except Exception as e:
#     print(e)
