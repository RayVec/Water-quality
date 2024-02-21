import subprocess
from weasyprint import HTML

HTML('https://weasyprint.org/').write_pdf('/tmp/weasyprint-website.pdf')
# command = "weasyprint report/report.html report/report.pdf &"
#
# # Execute the shell command and capture the output
# result = subprocess.run(command, shell=True, capture_output=True, text=True)
#
# # Check the result
# if result.returncode == 0:
#     print("Command executed successfully.")
#     print("Output:", result.stdout)
# else:
#     print("Error executing the command.")
#     print("Error message:", result.stderr)
