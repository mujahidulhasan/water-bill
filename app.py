from flask import Flask, render_template, request
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from dateutil.relativedelta import relativedelta # For calculating previous month's date

# NOTE: Ensure 'python-dateutil' is in your requirements.txt

app = Flask(__name__)

# --- Helper Function to calculate Previous Month's Date Range ---
def get_previous_month_dates():
    """Calculates the start and end date of the previous month in dd/mm/yyyy format."""
    try:
        # Find the first day of the current month
        today = datetime.now().date()
        first_day_of_current_month = today.replace(day=1)
        
        # Calculate the last day of the previous month
        last_day_of_previous_month = first_day_of_current_month - relativedelta(days=1)
        
        # Calculate the first day of the previous month
        first_day_of_previous_month = last_day_of_previous_month.replace(day=1)
        
        # Format the dates as dd/mm/yyyy (WASA input field format)
        from_date = first_day_of_previous_month.strftime('%d/%m/%Y') 
        to_date = last_day_of_previous_month.strftime('%d/%m/%Y')
        
        print(f"DEBUG: Auto-calculated dates: From={from_date}, To={to_date}")
        return from_date, to_date
    except Exception as e:
        print(f"DEBUG: Date calculation failed: {e}")
        return "", ""

# --- Helper Function for Text Extraction ---
def extract_between(text, start, end):
    """Extracts text between two specific delimiters."""
    try:
        start_index = text.find(start)
        if start_index == -1: return ""
        text_after_start = text[start_index + len(start):]
        end_index = text_after_start.find(end)
        return text_after_start[:end_index].strip() if end_index != -1 else ""
    except: return ""

# --- Main Bill Fetching Function ---
def get_latest_bill(user_id, password):
    # Base URL where all POST requests (Login and Search) go
    wasa_url = "http://app.dwasa.org.bd/index.php?type_name=member&page_name=acc_index&panel_index=1"

    # Calculate dates for the previous month
    from_date, to_date = get_previous_month_dates()

    # Headers and Session Management
    headers = {"User-Agent": "Mozilla/5.0"}
    session = requests.Session() # Essential for maintaining the logged-in state (cookies)

    # --- STEP 1: LOGIN with hidden parameters ---
    # Added 'tab_val' as it might be a required hidden field for the POST request
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

    # Check for login success
    if "Account No" not in r_login.text:
        print("DEBUG: Login failed or 'Account No' text not found.")
        return None
    
    print("DEBUG: Login successful. Session established.")

    # --- STEP 2: POST REQUEST with CORRECT Date Parameters to Fetch Bills ---
    # We use the confirmed parameter names from the HTML: date1, date2, and btn=Search
    search_payload = {
        "date1": from_date,     # Confirmed From date parameter
        "date2": to_date,       # Confirmed To date parameter
        "btn": "Search",        # The search button's name and value
        "tab_val": "3",         # Hidden field confirmed from HTML
    }
    
    try:
        # POSTing to the same URL, but with the search parameters
        r_bill = session.post(wasa_url, data=search_payload, headers=headers, timeout=10)
        print(f"DEBUG: Bill Search Status Code: {r_bill.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"DEBUG: Bill search request failed: {e}")
        return None

    # Use the HTML content from the bill search request
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
         
    # --- Bill Table Extraction ---
    bill_table = None
    all_tables = soup.find_all("table")
    
    # Look for the table with the specific header row (class="tr_title")
    for table in all_tables:
        # Looking for the table with the header row that contains 'Bill No'
        if "Bill No" in table.get_text() and "Issue Date" in table.get_text():
            bill_table = table
            print("DEBUG: Found bill table using header keywords.")
            break

    bill = None
    if bill_table:
        rows = bill_table.find_all("tr")

        # Iterate through rows to find the valid bill data
        for row in rows: 
            # Get all <td> elements and clean the text
            cols = [c.get_text(strip=True).replace('\xa0', ' ').strip() for c in row.find_all("td")]
            
            # Check for a valid bill row (at least 13 columns, numeric Bill No, and not the 'Total' row)
            if len(cols) >= 13 and cols[0] and cols[0].isdigit():
                # Extracting the simplified bill details as requested
                bill = {
                    "Bill Month": cols[2],     # Column 3
                    "Total Bill": cols[8],     # Column 9
                    "Status": cols[11],        # Column 12
                }
                print(f"DEBUG: Found previous month's bill: {bill['Bill Month']}")
                break # Use the first valid row found

    if not bill:
        print("DEBUG: No bill data found in the parsed tables for the date range.")

    return {"info": info, "bill": bill}


@app.route("/", methods=["GET", "POST"])
def home():
    data = None
    error = None
    if request.method == "POST":
        # Check for the required 'python-dateutil' package
        try:
            # This line ensures the dependency is available, preventing a crash
            from dateutil.relativedelta import relativedelta 
        except ImportError:
            error = "Dependency error: 'python-dateutil' is not installed. Please add it to requirements.txt and run pip install."
            return render_template("index.html", data=data, error=error)
            
        user_id = request.form["userid"]
        password = request.form["password"]
        data = get_latest_bill(user_id, password)
        
        if not data or not data.get('info', {}).get('Account No'):
            # The error message remains helpful for debugging
            error = "Invalid account, login failed, or bill data not found for the previous month. Check your credentials and Render logs for more details."
    return render_template("index.html", data=data, error=error)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
