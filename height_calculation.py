import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time
import tempfile

def calculate_rendered_heights(html_path, css_code=None, element_ids=None, width=800):
    """
    Calculate the rendered height of multiple elements from an HTML file using a single browser instance
    
    Args:
        html_path (str): Path to the HTML file to render
        css_code (str, optional): Additional CSS code to apply. If None, only the CSS in the HTML file is used.
        element_ids (list): List of element IDs to measure
        width (int, optional): The width to render the content at. Defaults to 800px.
        
    Returns:
        dict: Dictionary mapping element IDs to their heights in pixels
    """
    # Get the absolute path of the HTML file
    abs_html_path = os.path.abspath(html_path)
    
    try:
        # Set up headless Chrome browser
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument(f"--window-size={width},2000")  # Set width, height tall enough
        
        driver = webdriver.Chrome(options=chrome_options)
        
        # Load the HTML file directly using its file:// URL
        driver.get(f"file://{abs_html_path}")
        
        # If additional CSS is provided, inject it
        if css_code:
            driver.execute_script(f"""
                var style = document.createElement('style');
                style.type = 'text/css';
                style.innerHTML = `{css_code}`;
                document.head.appendChild(style);
            """)
        
        # Wait for the page to render and images to load
        time.sleep(0.5)  # Increase wait time to allow for image loading
        
        # Get heights for all requested elements
        heights = {}
        for element_id in element_ids:
            try:
                element = driver.find_element(By.ID, element_id)
                heights[element_id] = element.size['height']
            except Exception as e:
                print(f"Error getting height for {element_id}: {str(e)}")
                heights[element_id] = None
        
        return heights
    
    except Exception as e:
        raise Exception(f"Error calculating height: {str(e)}")
    
    finally:
        # Clean up
        if 'driver' in locals():
            driver.quit()

# Keep the original function for backward compatibility
def calculate_rendered_height(html_path, css_code=None, element_id=None, width=800):
    """
    Calculate the rendered height of a specific element from an HTML file
    
    Args:
        html_path (str): Path to the HTML file to render
        css_code (str, optional): Additional CSS code to apply. If None, only the CSS in the HTML file is used.
        element_id (str): The ID of the element whose height we want to measure
        width (int, optional): The width to render the content at. Defaults to 800px.
        
    Returns:
        int: The height of the rendered element in pixels
    """
    result = calculate_rendered_heights(html_path, css_code, [element_id], width)
    return result.get(element_id)

def test_template_heights():
    """Test function to measure heights of various elements in the template.html"""
    # Specify the path to the HTML file
    report_path = os.path.abspath("reports/7/2024-09-07.html")
    
    # Load additional CSS if needed (optional)
    css_path = "report.css"
    css_content = ""
    
    try:
        with open(css_path, 'r', encoding='utf-8') as file:
            css_content = file.read()
    except FileNotFoundError:
        print(f"CSS file not found at {css_path}. Using only CSS in the HTML file.")
        css_content = None
    
    # List of element IDs to measure from the report
    elements_to_measure = [
        "page2",
        "page3",
        "page4",
        "page5",
        "page6",
        "page7",
        "page8",
        "page9",
        "page10"
    ]
    
    # Measure each element and print results
    print("Element Heights in Report:")
    print("-" * 40)
    
    for element_id in elements_to_measure:
        try:
            # Measure the height using the direct HTML file path
            height = calculate_rendered_height(report_path, css_content, element_id)
            print(f"{element_id}: {height}px")
        except Exception as e:
            print(f"{element_id}: Error - {str(e)}")
    
    print("-" * 40)

if __name__ == "__main__":
    test_template_heights()