from flask import Flask, render_template, request
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

def get_latest_bill(user_id, password):
    # WASA Login/Account Status URL
    url = "http://app.dwasa.org.bd/index.php?type_name=member&page_name=acc_index&panel_index=1"
    
    # POST Payload for Login
    payload = {"userId": user_id, "password": password}
    
    # Standard User-Agent to mimic a regular browser
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.60 Safari/537.36"}

    try:
        # 1. Attempt the POST request
        r = requests.post(url, data=payload, headers=headers, timeout=15) # Added timeout
        print(f"DEBUG: Response Status Code from WASA: {r.status_code}") 

    except requests.exceptions.RequestException as e:
        # Handle network/connection errors
        print(f"DEBUG: Request failed: {e}")
        return None

    # Check for login failure (The 'Account No' check is still a key indicator)
    if "Account No" not in r.text:
        # You should see this in the logs if login fails or the login page structure changed
        print("DEBUG: Login failed or page structure changed. 'Account No' text not found on the page.")
        return None
        
    print("DEBUG: Login successful. Starting data extraction.")

    soup = BeautifulSoup(r.text, "html.parser")
    # Using get_text with a better separator for easier parsing
    text = soup.get_text(separator=" ", strip=True) 

    # --- Account Info Extraction (Made more robust) ---
    def extract_between(text, start, end):
        try:
            start_index = text.find(start)
            if start_index == -1:
                return ""
            
            text_after_start = text[start_index + len(start):]
            end_index = text_after_start.find(end)
            
            if end_index == -1:
                # If end marker not found, take a sensible chunk or the rest
                return text_after_start.split(" ")[0].strip() or text_after_start.strip()
            
            return text_after_start[:end_index].strip()
        except Exception as e:
            print(f"DEBUG: Error in extract_between: {e}. Check the delimiters.")
            return ""

    # Re-using the successful keys, check the delimiter spaces carefully
    info = {
        "Account No": extract_between(text, "Account No :", "Opening Balance"),
        "Name": extract_between(text, "Name:", "Address:"),
        "Meter No": extract_between(text, "Meter No.:", "Meter Installation Date:"),
        "Cell No": extract_between(text, "Cell No:", "Email:"),
        "Address": extract_between(text, "Address:", "Water Status:"),
    }
    
    # Verify if account info extraction worked
    if not info.get("Account No") or not info.get("Name"):
         print("DEBUG: Critical account information extraction failed.")
         # Even if logged in, if we can't parse the info, treat it as failure
         return None
         
    # --- Bill Table Extraction (More robust search logic) ---
    bill_table = None
    all_tables = soup.find_all("table")
    
    # 1. Look for a table that contains the typical Bill Header names
    for table in all_tables:
        if "Bill No" in table.get_text() and "Bill Month" in table.get_text():
            bill_table = table
            print("DEBUG: Found bill table using header keywords.")
            break
            
    # 2. Fallback to the original logic (last table)
    if not bill_table and all_tables:
        bill_table = all_tables[-1]
        print("DEBUG: Falling back to the last table.")

    bill = None
    if bill_table:
        rows = bill_table.find_all("tr")

        # Start from the second row to skip the header (if present)
        for row in rows[1:]: 
            # Get text from table data cells, clean up non-breaking spaces
            cols = [c.get_text(strip=True).replace('\xa0', ' ').strip() for c in row.find_all("td")]
            
            # Check if it's a valid bill row (must have at least 13 columns and a numeric Bill No)
            if len(cols) >= 13 and cols[0] and cols[0].isdigit():
                # Extracting the latest/first valid bill row
                bill = {
                    "Bill No": cols[0],
                    "Issue Date": cols[1],
                    "Bill Month": cols[2],
                    "Water Bill": cols[3],
                    "Sewer Bill": cols[4],
                    "VAT": cols[5],
                    "Bill Amt": cols[6],
                    "Sur Charge": cols[7],
                    "Total Bill": cols[8],
                    "Paid Date": cols[9],
                    "Paid Amt": cols[10],
                    "Status": cols[11],
                    "Balance": cols[12],
                }
                print(f"DEBUG: Successfully extracted bill for month: {bill['Bill Month']}")
                break # Found the first valid bill, stop and use it

    if not bill:
        print("DEBUG: No bill data found in the parsed tables.")

    return {"info": info, "bill": bill}


@app.route("/", methods=["GET", "POST"])
def home():
    data = None
    error = None
    if request.method == "POST":
        user_id = request.form["userid"]
        password = request.form["password"]
        data = get_latest_bill(user_id, password)
        # Check for both a successful data object AND if key account info exists
        if not data or not data.get('info', {}).get('Account No'):
            error = "Invalid account, login failed, or no bill data found. Please verify your Account No and Password."
    return render_template("index.html", data=data, error=error)


if __name__ == "__main__":
    # Running on an accessible port for local testing
    app.run(debug=True, port=5000)
