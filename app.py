from flask import Flask, render_template, request
import requests
from bs4 import BeautifulSoup
from datetime import datetime
# Removed dateutil since we are not calculating dates automatically anymore

app = Flask(__name__)

# --- Helper Function for Text Extraction (No Change) ---
def extract_between(text, start, end):
    """Extracts text between two specific delimiters."""
    try:
        start_index = text.find(start)
        if start_index == -1: return ""
        text_after_start = text[start_index + len(start):]
        end_index = text_after_start.find(end)
        return text_after_start[:end_index].strip() if end_index != -1 else ""
    except: return ""

# --- Main Bill Fetching Function (MODIFIED to accept dates) ---
def get_latest_bill(user_id, password, from_date, to_date):
    # Base URL where all POST requests (Login and Search) go
    wasa_url = "http://app.dwasa.org.bd/index.php?type_name=member&page_name=acc_index&panel_index=1"

    # Headers and Session Management
    headers = {"User-Agent": "Mozilla/5.0"}
    session = requests.Session() 

    # --- STEP 1: LOGIN ---
    login_payload = {
        "userId": user_id, 
        "password": password,
        "tab_val": "3" 
    }
    
    try:
        r_login = session.post(wasa_url, data=login_payload, headers=headers, timeout=10)
        print(f"DEBUG: Login Status Code: {r_login.status_code}") 
    except requests.exceptions.RequestException as e:
        print(f"DEBUG: Login request failed: {e}")
        return None

    if "Account No" not in r_login.text:
        print("DEBUG: Login failed or 'Account No' text not found.")
        return None
    
    print("DEBUG: Login successful. Session established.")

    # --- STEP 2: POST REQUEST with User-provided Date Parameters to Fetch Bills ---
    search_payload = {
        "date1": from_date,     # User-provided 'From' date
        "date2": to_date,       # User-provided 'To' date
        "btn": "Search",        
        "tab_val": "3",         
    }
    
    try:
        r_bill = session.post(wasa_url, data=search_payload, headers=headers, timeout=10)
        print(f"DEBUG: Bill Search Status Code: {r_bill.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"DEBUG: Bill search request failed: {e}")
        return None

    soup = BeautifulSoup(r_bill.text, "html.parser")
    text = soup.get_text(separator=" ", strip=True)

    # --- Account Info Extraction ---
    info = {
        "Account No": extract_between(text, "Account No :", "Opening Balance"),
        "Name": extract_between(text, "Name:", "Address:"),
        "Meter No": extract_between(text, "Meter No.:", "Meter Installation Date:"),
        "Cell No": extract_between(text, "Cell No:", "Email:"),
        "Address": extract_between(text, "Address:", "Water Status:"),
    }
    
    if not info.get("Account No"):
         print("DEBUG: Critical account information extraction failed after search.")
         return None
         
    # --- Bill Table Extraction (The first valid bill row found will be displayed) ---
    bill_table = None
    all_tables = soup.find_all("table")
    
    for table in all_tables:
        if "Bill No" in table.get_text() and "Issue Date" in table.get_text():
            bill_table = table
            print("DEBUG: Found bill table using header keywords.")
            break

    bill = None
    if bill_table:
        rows = bill_table.find_all("tr")

        for row in rows: 
            cols = [c.get_text(strip=True).replace('\xa0', ' ').strip() for c in row.find_all("td")]
            
            # Check for a valid bill row (13 columns, numeric Bill No, and not the 'Total' row)
            if len(cols) >= 13 and cols[0] and cols[0].isdigit():
                # Extracting the simplified bill details (Total Bill and Status)
                bill = {
                    "Bill Month": cols[2],     # Column 3
                    "Total Bill": cols[8],     # Column 9
                    "Status": cols[11],        # Column 12
                }
                print(f"DEBUG: Found bill: {bill['Bill Month']} ({bill['Status']})")
                break # Show only the first bill found in the range

    if not bill:
        print("DEBUG: No bill data found in the parsed tables for the date range.")

    return {"info": info, "bill": bill}


@app.route("/", methods=["GET", "POST"])
def home():
    data = None
    error = None
    # No need for dateutil import check anymore
    if request.method == "POST":
        user_id = request.form["userid"]
        password = request.form["password"]
        
        # Get the manually entered dates
        from_date = request.form["from_date"]
        to_date = request.form["to_date"]
        
        # Basic date format validation (WASA uses dd-mm-yyyy or dd/mm/yyyy)
        if not (len(from_date) == 10 and len(to_date) == 10):
             error = "Please enter dates in the correct DD/MM/YYYY format."
             return render_template("index.html", data=data, error=error)
        
        # Pass dates to the fetching function
        data = get_latest_bill(user_id, password, from_date, to_date)
        
        if not data or not data.get('info', {}).get('Account No'):
            error = "Invalid account, login failed, or bill data not found for the given dates. Please check your credentials and ensure dates are in DD/MM/YYYY format (e.g., 01/01/2024 to 31/01/2024)."
            
    return render_template("index.html", data=data, error=error)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
