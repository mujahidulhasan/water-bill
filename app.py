from flask import Flask, render_template, request
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from dateutil.relativedelta import relativedelta # You might need to add this to requirements.txt

# NOTE: If dateutil is not installed, you'll need to run:
# pip install python-dateutil
# and update your requirements.txt: python-dateutil

app = Flask(__name__)

# --- Helper Function to calculate Previous Month's Date Range ---
def get_previous_month_dates():
    """Calculates the start and end date of the previous month in dd/mm/yyyy format."""
    # Find the first day of the current month
    today = datetime.now().date()
    first_day_of_current_month = today.replace(day=1)
    
    # Calculate the last day of the previous month
    last_day_of_previous_month = first_day_of_current_month - relativedelta(days=1)
    
    # Calculate the first day of the previous month
    first_day_of_previous_month = last_day_of_previous_month.replace(day=1)
    
    # Format the dates as dd/mm/yyyy
    from_date = first_day_of_previous_month.strftime('%d/%m/%Y')
    to_date = last_day_of_previous_month.strftime('%d/%m/%Y')
    
    print(f"DEBUG: Auto-calculated dates: From={from_date}, To={to_date}")
    return from_date, to_date

# --- Main Bill Fetching Function ---
def get_latest_bill(user_id, password):
    # Base URL for WASA Account/Login
    base_url = "http://app.dwasa.org.bd/index.php?type_name=member&page_name=acc_index&panel_index="
    login_url = base_url + "1" # Login Panel
    search_url = base_url + "2" # Bill Search Panel (Assuming panel_index=2 is the search)

    # Calculate dates for the previous month
    from_date, to_date = get_previous_month_dates()

    # Headers and Session Management
    headers = {"User-Agent": "Mozilla/5.0"}
    session = requests.Session() # Use a session to maintain login state (cookies)

    # --- STEP 1: LOGIN ---
    login_payload = {"userId": user_id, "password": password}
    r_login = session.post(login_url, data=login_payload, headers=headers)
    print(f"DEBUG: Login Status Code: {r_login.status_code}") 

    if "Account No" not in r_login.text:
        print("DEBUG: Login failed or page structure changed.")
        return None

    # --- STEP 2: POST REQUEST with Date Filter to Fetch Bills ---
    # This is the crucial new step based on your observation (Assuming the date search is also a POST)
    
    # Payload for bill search, using the automatically generated dates
    search_payload = {
        "start_date": from_date, 
        "end_date": to_date,
        "search": "Search" # Assuming the button name is 'search'
    }
    
    # We send the search request to the same URL or the search panel URL
    # We will try the login URL first as it often handles all POSTs on the same page
    r_bill = session.post(login_url, data=search_payload, headers=headers)
    print(f"DEBUG: Bill Search Status Code: {r_bill.status_code}")

    # Use the HTML content from the bill search request
    soup = BeautifulSoup(r_bill.text, "html.parser")
    text = soup.get_text(separator=" ", strip=True)

    # --- Account Info Extraction (Reusing your original logic) ---
    def extract_between(text, start, end):
        try:
            start_index = text.find(start)
            if start_index == -1: return ""
            text_after_start = text[start_index + len(start):]
            end_index = text_after_start.find(end)
            return text_after_start[:end_index].strip() if end_index != -1 else ""
        except: return ""

    info = {
        "Account No": extract_between(text, "Account No :", "Opening Balance"),
        "Name": extract_between(text, "Name:", "Address:"),
        "Meter No": extract_between(text, "Meter No.:", "Meter Installation Date:"),
        "Cell No": extract_between(text, "Cell No:", "Email:"),
        "Address": extract_between(text, "Address:", "Water Status:"),
    }
    
    # --- Bill Table Extraction (Focusing on the table) ---
    bill_table = None
    all_tables = soup.find_all("table")
    
    # Find the table that contains "Bill No"
    for table in all_tables:
        if "Bill No" in table.get_text() and "Bill Month" in table.get_text():
            bill_table = table
            break
            
    # Fallback to the last table if specific search fails
    if not bill_table and all_tables:
        bill_table = all_tables[-1]

    bill = None
    if bill_table:
        rows = bill_table.find_all("tr")

        # Skip the header row (rows[0])
        for row in rows[1:]: 
            cols = [c.get_text(strip=True).replace('\xa0', ' ').strip() for c in row.find_all("td")]
            
            # Check for a valid bill row (13 columns, numeric Bill No, and not the 'Total' row)
            if len(cols) >= 13 and cols[0] and cols[0].isdigit():
                # This is a bill row, we only want the previous month's bill
                # Since we filtered by date, the first valid row *should* be the one we want.
                bill = {
                    "Bill Month": cols[2],     # Column 3
                    "Total Bill": cols[8],     # Column 9
                    "Status": cols[11],        # Column 12
                }
                print(f"DEBUG: Found previous month's bill: {bill['Bill Month']}")
                break 

    return {"info": info, "bill": bill}


@app.route("/", methods=["GET", "POST"])
def home():
    data = None
    error = None
    if request.method == "POST":
        # Check for the required 'python-dateutil' package
        try:
            from dateutil.relativedelta import relativedelta
        except ImportError:
            error = "Dependency error: 'python-dateutil' is not installed. Please add it to requirements.txt and run pip install."
            return render_template("index.html", data=data, error=error)
            
        user_id = request.form["userid"]
        password = request.form["password"]
        data = get_latest_bill(user_id, password)
        
        if not data or not data.get('info', {}).get('Account No'):
            error = "Invalid account, login failed, or bill data not found for the previous month."
    return render_template("index.html", data=data, error=error)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
