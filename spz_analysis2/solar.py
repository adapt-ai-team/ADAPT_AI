import requests
import os
import json
import traceback

# Define file paths (UPDATE THESE AS NEEDED)
GEOMETRY_PATH = r"D:\spz_analysis2\newyork.glb"
EPW_FILE_PATH = r"D:\spz_analysis2\newyork.epw"
GRASSHOPPER_FILE = r"D:\spz_analysis2\solar.ghx"

# Rhino Compute URL (running on localhost:5000)
RHINO_COMPUTE_URL = "http://localhost:5000/grasshopper"

# Function to check if files exist
def check_files():
    print("Checking file paths:")
    files_exist = {
        "Geometry file exists": os.path.exists(GEOMETRY_PATH),
        "EPW file exists": os.path.exists(EPW_FILE_PATH),
        "Grasshopper file exists": os.path.exists(GRASSHOPPER_FILE),
    }
    for desc, exists in files_exist.items():
        print(f"{desc}: {exists}")
        if not exists:
            raise FileNotFoundError(f"Error: {desc} is missing!")

# Function to test Rhino Compute connection
def test_rhino_compute():
    try:
        response = requests.get("http://localhost:5000/version")
        print("Rhino Compute Response:", response.text)
        return response.status_code == 200
    except requests.exceptions.RequestException as e:
        print("Error connecting to Rhino Compute:", e)
        return False

# Function to send Grasshopper .ghx file for processing
def run_solar_analysis():
    try:
        print("\n🔹 Running Solar Radiation Analysis via Rhino Compute...")

        # Read the Grasshopper GHX file
        with open(GRASSHOPPER_FILE, "rb") as ghx_file:
            ghx_data = ghx_file.read()

        # Define input parameters for Grasshopper (Modify as needed)
        payload = {
            "algo": ghx_data.decode("latin1"),  # Send GHX file data
            "values": [
                {"ParamName": "Geometry", "InnerTree": {"{0}": [{"data": GEOMETRY_PATH}]}},
                {"ParamName": "EPW_File", "InnerTree": {"{0}": [{"data": EPW_FILE_PATH}]}}
            ]
        }

        # Send request to Rhino Compute
        response = requests.post(RHINO_COMPUTE_URL, json=payload)

        # Process response
        if response.status_code == 200:
            print("✅ Solar Analysis Completed!")
            result = response.json()
            print(json.dumps(result, indent=4))  # Pretty print results
        else:
            print("❌ Error:", response.status_code, response.text)

    except Exception as e:
        print("An error occurred during the analysis:")
        print(traceback.format_exc())

# Run the script
if __name__ == "__main__":
    try:
        print("Requests module imported successfully.")

        # Step 1: Check files
        check_files()

        # Step 2: Test Rhino Compute
        if not test_rhino_compute():
            raise ConnectionError("Rhino Compute is not reachable. Make sure it is running.")

        # Step 3: Run the solar analysis
        run_solar_analysis()

    except Exception as e:
        print("Fatal Error:")
        print(traceback.format_exc())
