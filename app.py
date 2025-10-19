from flask import Flask, render_template, request
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

def get_dwasa_bill(user_id, password):
    url = "http://app.dwasa.org.bd/index.php?type_name=member&page_name=acc_index&panel_index=1"
    payload = {"userId": user_id, "password": password}
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    response = requests.post(url, data=payload, headers=headers)
    if "Bill No" not in response.text:
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    table = soup.find("table")
    if not table:
        return None

    rows = table.find_all("tr")[1:]
    bills = []

    for row in rows:
        cols = [c.get_text(strip=True) for c in row.find_all("td")]
        if len(cols) >= 10:
            bills.append({
                "Bill No": cols[0],
                "Issue Date": cols[1],
                "Bill Month": cols[2],
                "Water Bill": cols[3],
                "Sewer Bill": cols[4],
                "VAT": cols[5],
                "Bill Amt": cols[6],
                "Surcharge": cols[7],
                "Total Bill": cols[8],
                "Paid Date": cols[9],
                "Paid Amt": cols[10] if len(cols) > 10 else "",
                "Status": cols[11] if len(cols) > 11 else "",
                "Balance": cols[12] if len(cols) > 12 else ""
            })
    return bills


@app.route("/", methods=["GET", "POST"])
def home():
    bills = None
    error = None
    if request.method == "POST":
        user_id = request.form["userid"]
        password = request.form["password"]
        bills = get_dwasa_bill(user_id, password)
        if not bills:
            error = "No bill found or invalid credentials."
    return render_template("index.html", bills=bills, error=error)


if __name__ == "__main__":
    app.run(debug=True)
