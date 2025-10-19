from flask import Flask, render_template, request
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

def get_latest_bill(user_id, password):
    url = "http://app.dwasa.org.bd/index.php?type_name=member&page_name=acc_index&panel_index=1"
    payload = {"userId": user_id, "password": password}
    headers = {"User-Agent": "Mozilla/5.0"}

    r = requests.post(url, data=payload, headers=headers)

    if "Account No" not in r.text:
        return None

    soup = BeautifulSoup(r.text, "html.parser")
    info_text = soup.get_text()

    # Helper to extract text between two points
    def extract_between(text, start, end):
        try:
            return text.split(start)[1].split(end)[0].strip()
        except:
            return ""

    # Account info
    info = {
        "Account No": extract_between(info_text, "Account No :", "Opening Balance"),
        "Name": extract_between(info_text, "Name:", "Address:"),
        "Meter No": extract_between(info_text, "Meter No.:", "Meter Installation Date:"),
        "Cell No": extract_between(info_text, "Cell No:", "Email:"),
        "Address": extract_between(info_text, "Address:", "Water Status:")
    }

    # Find bill table
    table = soup.find("table")
    if not table:
        return {"info": info, "bill": None}

    rows = table.find_all("tr")[1:]
    if not rows:
        return {"info": info, "bill": None}

    # Take last (latest) bill row
    last_row = rows[-1]
    cols = [c.get_text(strip=True) for c in last_row.find_all("td")]

    bill = {
        "Bill No": cols[0],
        "Issue Date": cols[1],
        "Bill Month": cols[2],
        "Water Bill": cols[3],
        "VAT": cols[5],
        "Total Bill": cols[8],
        "Paid Date": cols[9],
        "Status": cols[11] if len(cols) > 11 else "Unknown"
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
            error = "Invalid account or no bill found."

    return render_template("index.html", data=data, error=error)


if __name__ == "__main__":
    app.run(debug=True)
