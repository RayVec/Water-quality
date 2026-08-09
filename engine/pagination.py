import atexit
import os
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

# One headless Chrome is reused for the whole batch.
#
# This used to launch and quit a browser per report, which cost about 2.2s each
# and was almost entirely cold-start overhead: the measuring itself is a handful
# of DOM reads. The driver is created on first use and closed at interpreter
# exit, so callers do not have to manage it.
_driver = None


def _get_driver(width):
    """Return the shared headless Chrome, starting it on first use."""
    global _driver
    if _driver is None:
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument(f"--window-size={width},2000")
        _driver = webdriver.Chrome(options=chrome_options)
        atexit.register(close_driver)
    # Reassert the viewport: the launch argument only applies to the first
    # window, and a later call may ask for a different width.
    _driver.set_window_size(width, 2000)
    return _driver


def close_driver():
    """Quit the shared browser. Safe to call more than once."""
    global _driver
    if _driver is not None:
        try:
            _driver.quit()
        except Exception:
            pass
        _driver = None


def calculate_rendered_heights(html_path, css_code=None, element_ids=None, width=800):
    """
    Calculate the rendered height of multiple elements from an HTML file.

    Args:
        html_path (str): Path to the HTML file to render
        css_code (str, optional): Additional CSS code to apply. If None, only the CSS in the HTML file is used.
        element_ids (list): List of element IDs to measure
        width (int, optional): The width to render the content at. Defaults to 800px.

    Returns:
        dict: Dictionary mapping element IDs to their heights in pixels
    """
    abs_html_path = os.path.abspath(html_path)

    try:
        driver = _get_driver(width)

        # Load the HTML file directly using its file:// URL
        driver.get(f"file://{abs_html_path}")

        # If additional CSS is provided, inject it. Navigating to the next
        # report discards it, so nothing leaks between reports.
        if css_code:
            driver.execute_script(
                """
                var style = document.createElement('style');
                style.type = 'text/css';
                style.textContent = arguments[0];
                document.head.appendChild(style);
                """,
                css_code,
            )

        # Wait for the page to render and images to load
        time.sleep(0.5)

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
        # A crashed browser would poison every later call, so drop it and let
        # the next call start a fresh one.
        close_driver()
        raise Exception(f"Error calculating height: {str(e)}")
