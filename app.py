from flask import Flask, render_template, request
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

def get_latest_bill(user_id, password):
    url = "http://app.dwasa.org.bd/index.php?type_name=member&page_name=acc_index&panel_index=1"
    payload = {"userId": user_id, "password": password}
    headers = {"User-Agent": "Mozilla/5.0"}

    r = requests.post(url, data=payload, headers=headers)

    # If login fails or page doesn’t have account info
    if "Account No" not in r.text:
        return None

    soup = BeautifulSoup(r.text, "html.parser")
    text = soup.get_text(separator=" ")

    def extract_between(text, start, end):
        try:
            return text.split(start)[1].split(end)[0].strip()
        except:
            return ""

    # Extracting account info
    info = {
        "Account No": extract_between(text, "Account No :", "Opening Balance"),
        "Name": extract_between(text, "Name:", "Address:"),
        "Meter No": extract_between(text, "Meter No.:", "Meter Installation Date:"),
        "Cell No": extract_between(text, "Cell No:", "Email:"),
        "Address": extract_between(text, "Address:", "Water Status:"),
    }

    # Extract latest bill table
    bill_table = soup.find_all("table")[-1]  # the last table usually contains the bill
    rows = bill_table.find_all("tr")

    bill = None
    for row in rows:
        cols = [c.get_text(strip=True) for c in row.find_all("td")]
        if len(cols) >= 13 and cols[0] and cols[0].isdigit():
            # This is a bill row
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

    return {"info": info, "bill": bill}


@app.route("/", methods=["GET", "POST"])
def home():
    data = None
    error = None
    if request.method == "POST":
        user_id = request.form["userid"]
        password = request.form["password"]
        data = get_latest_bill(user_id, password)
        if not data:
            error = "Invalid account or no bill data found."
    return render_template("index.html", data=data, error=error)


if __name__ == "__main__":
    app.run(debug=True)
