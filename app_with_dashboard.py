from dotenv import load_dotenv
load_dotenv()
# from paddleocr import PaddleOCR
from groq import Groq
import streamlit as st
import pandas as pd
import json
import os
import base64

from PIL import Image
# from groq import Groq

if "invoice_data" not in st.session_state:
    st.session_state.invoice_data = None

if "items_data" not in st.session_state:
    st.session_state.items_data = None

# Page navigation
if "page" not in st.session_state:
    st.session_state.page = "scanner"   # default page

# ---------------- CONFIG ----------------

MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

INVOICE_FILE = "invoices.csv"
ITEM_FILE = "invoice_items.csv"


client = Groq(api_key=os.getenv("GROQ_API_KEY"))


# ---------------- UTIL ----------------

def encode_image(img_file):

    return base64.b64encode(img_file.read()).decode("utf-8")

import re

def clean_json(text):

    # Remove ```json and ``` blocks safely
    text = re.sub(r"```json", "", text, flags=re.IGNORECASE)
    text = re.sub(r"```", "", text)

    # Extract first JSON object
    match = re.search(r"\{.*\}", text, re.DOTALL)

    if match:
        return match.group(0)

    return text.strip()
def init_csv():

    if not os.path.exists(INVOICE_FILE):

        pd.DataFrame(columns=[
            "invoice_no",
            "invoice_date",
            "total_qty",
            "total_amount",
            "total_amount_inwords"
        ]).to_csv(INVOICE_FILE, index=False)


    if not os.path.exists(ITEM_FILE):

        pd.DataFrame(columns=[
            "invoice_no",
            "serial_number",
            "item_name",
            "Qty",
            "Rate",
            "Amount"
        ]).to_csv(ITEM_FILE, index=False)


def call_groq_vision(base64_img):

    prompt = """
You are an invoice extractor.

Return ONLY a valid JSON object.

Do NOT:
- Use markdown
- Use ```
- Add comments
- Add explanations

Return raw JSON only.

Schema:

{
 "invoice":{
   "invoice_no":"",
   "invoice_date":"",
   "total_qty":"",
   "total_amount":"",
   "total_amount_inwords":""
 },
 "items":[
   {
     "serial_number":"",
     "item_name":"",
     "Qty":"",
     "Rate":"",
     "Amount":""
   }
 ]
}

"""

    response = client.chat.completions.create(

        model=MODEL,

        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_img}"
                        }
                    }
                ]
            }
        ],

        temperature=0

    )

    return response.choices[0].message.content


def save_data(invoice, items):

    inv = pd.read_csv(INVOICE_FILE)
    itm = pd.read_csv(ITEM_FILE)

    inv.loc[len(inv)] = list(invoice.values())

    for i in items:

        itm.loc[len(itm)] = [
            invoice["invoice_no"],
            i["serial_number"],
            i["item_name"],
            i["Qty"],
            i["Rate"],
            i["Amount"]
        ]

    inv.to_csv(INVOICE_FILE, index=False)
    itm.to_csv(ITEM_FILE, index=False)


# ---------------- UI ----------------

st.set_page_config("Invoice Extractor", layout="wide")

st.title("📄 Invoice Scanner")

init_csv()

# ---------------- PAGE STATE ----------------

if "page" not in st.session_state:
    st.session_state.page = "scanner"


# ---------------- TOP NAV ----------------

col_nav1, col_nav2 = st.columns([8, 2])

with col_nav2:

    if st.session_state.page == "scanner":
        if st.button("📊 Dashboard"):
            st.session_state.page = "dashboard"
            st.rerun()

    else:
        if st.button("🔎 Scan Invoice"):
            st.session_state.page = "scanner"
            st.rerun()


# ====================================================
# ================= SCANNER PAGE =====================
# ====================================================

if st.session_state.page == "scanner":

    st.subheader("📄 Scan New Invoice")

    file = st.file_uploader(
        "Upload Invoice",
        ["jpg", "png", "jpeg"]
    )

    if file:
        st.image(file, width=400)


    # ---------- EXTRACT ----------

    if file and st.button("🔍 Extract"):

        with st.spinner("Processing..."):

            base64_img = encode_image(file)
            result = call_groq_vision(base64_img)

        cleaned = clean_json(result)

        try:
            data = json.loads(cleaned)
        except:
            st.error("JSON Parse Failed")
            st.stop()

        st.session_state.invoice_data = data["invoice"]
        st.session_state.items_data = data["items"]


    # ---------- EDIT + SAVE ----------

    if st.session_state.invoice_data:

        invoice = st.session_state.invoice_data
        items = st.session_state.items_data

        st.subheader("✏️ Edit Invoice")

        with st.form("edit_form"):

            c1, c2, c3 = st.columns(3)

            invoice["invoice_no"] = c1.text_input(
                "Invoice No", invoice["invoice_no"]
            )

            invoice["invoice_date"] = c2.text_input(
                "Date", invoice["invoice_date"]
            )

            invoice["total_qty"] = c3.text_input(
                "Total Qty", invoice["total_qty"]
            )

            invoice["total_amount"] = st.text_input(
                "Total Amount", invoice["total_amount"]
            )

            invoice["total_amount_inwords"] = st.text_input(
                "Amount in Words", invoice["total_amount_inwords"]
            )

            st.subheader("Items")

            df = pd.DataFrame(items)

            edited = st.data_editor(
                df,
                num_rows="dynamic",
                use_container_width=True
            )

            save = st.form_submit_button("💾 Save")


        if save:

            st.session_state.items_data = edited.to_dict("records")

            save_data(
                st.session_state.invoice_data,
                st.session_state.items_data
            )

            st.success("Saved Successfully ✅")

            st.session_state.invoice_data = None
            st.session_state.items_data = None


# ====================================================
# ================= DASHBOARD PAGE ===================
# ====================================================

elif st.session_state.page == "dashboard":

    st.subheader("📊 Invoice Dashboard")


    # ---------- LOAD DATA ----------

    if os.path.exists(INVOICE_FILE):
        inv_df = pd.read_csv(INVOICE_FILE)
    else:
        inv_df = pd.DataFrame()


    if os.path.exists(ITEM_FILE):
        item_df = pd.read_csv(ITEM_FILE)
    else:
        item_df = pd.DataFrame()


    # ---------- METRICS ----------

    c1, c2, c3, c4 = st.columns(4)

    total_invoices = len(inv_df)

    total_amount = pd.to_numeric(
        inv_df["total_amount"],
        errors="coerce"
    ).sum()

    total_items = len(item_df)

    avg_invoice = (
        total_amount / total_invoices
        if total_invoices > 0 else 0
    )


    c1.metric("📄 Total Invoices", total_invoices)
    c2.metric("💰 Total Revenue", f"₹ {total_amount:,.2f}")
    c3.metric("📦 Total Items", total_items)
    c4.metric("📊 Avg Invoice", f"₹ {avg_invoice:,.2f}")


    st.divider()


    # ---------- TABLES ----------

    # st.subheader("🧾 All Invoices")
    # st.dataframe(inv_df, use_container_width=True)


    # st.subheader("📦 All Items")
    # st.dataframe(item_df, use_container_width=True)


    st.divider()


    # ---------- CHARTS ----------

    # if not inv_df.empty:

    #     inv_df["total_amount"] = pd.to_numeric(
    #         inv_df["total_amount"],
    #         errors="coerce"
    #     )

    #     st.subheader("📈 Revenue per Invoice")

    #     st.bar_chart(
    #         inv_df.set_index("invoice_no")["total_amount"]
    #     )
    # ---------- CHARTS ----------

    if not inv_df.empty:

        # Convert amount to number
        inv_df["total_amount"] = pd.to_numeric(
            inv_df["total_amount"],
            errors="coerce"
        )


        # Convert date to datetime
        inv_df["parsed_date"] = pd.to_datetime(
            inv_df["invoice_date"],
            format="%d/%b/%Y",
            errors="coerce"
        )


        # Remove invalid dates
        inv_df = inv_df.dropna(subset=["parsed_date"])


        # Sort by date
        inv_df = inv_df.sort_values("parsed_date")


        # ---------- Timeline Trend ----------

        st.subheader("📆 Revenue Timeline Trend")

        timeline_df = inv_df.set_index("parsed_date")["total_amount"]

        st.line_chart(timeline_df)


        st.divider()


        # ---------- Bar Chart ----------

        st.subheader("📈 Revenue per Invoice")

        bar_df = inv_df.set_index("invoice_no")["total_amount"]

        st.bar_chart(bar_df)




        # ---------- Edit Form ----------

        # st.subheader("Invoice")

        # with st.form("edit_form"):

        #     c1, c2, c3 = st.columns(3)

        #     invoice["invoice_no"] = c1.text_input("Invoice No", invoice["invoice_no"])
        #     invoice["invoice_date"] = c2.text_input("Date", invoice["invoice_date"])
        #     invoice["total_qty"] = c3.text_input("Total Qty", invoice["total_qty"])

        #     invoice["total_amount"] = st.text_input("Total Amount", invoice["total_amount"])
        #     invoice["total_amount_inwords"] = st.text_input("Amount in Words", invoice["total_amount_inwords"])


        #     st.subheader("Items")

        #     df = pd.DataFrame(items)

        #     edited = st.data_editor(df, num_rows="dynamic", use_container_width=True)

        #     save = st.form_submit_button("💾 Save")


        # if save:

        #     save_data(invoice, edited.to_dict("records"))

        #     st.success("Saved Successfully ✅")
        # ---------- Edit Form ----------

    if st.session_state.invoice_data:

        invoice = st.session_state.invoice_data
        items = st.session_state.items_data


        st.subheader("Invoice")

        with st.form("edit_form"):

            c1, c2, c3 = st.columns(3)

            invoice["invoice_no"] = c1.text_input(
                "Invoice No",
                invoice["invoice_no"]
            )

            invoice["invoice_date"] = c2.text_input(
                "Date",
                invoice["invoice_date"]
            )

            invoice["total_qty"] = c3.text_input(
                "Total Qty",
                invoice["total_qty"]
            )

            invoice["total_amount"] = st.text_input(
                "Total Amount",
                invoice["total_amount"]
            )

            invoice["total_amount_inwords"] = st.text_input(
                "Amount in Words",
                invoice["total_amount_inwords"]
            )


            st.subheader("Items")

            df = pd.DataFrame(items)

            edited = st.data_editor(
                df,
                num_rows="dynamic",
                use_container_width=True
            )


            save = st.form_submit_button("💾 Save")


        if save:

            st.session_state.items_data = edited.to_dict("records")

            save_data(
                st.session_state.invoice_data,
                st.session_state.items_data
            )

            st.success("Saved Successfully ✅")

            # Optional: Clear after save
            st.session_state.invoice_data = None
            st.session_state.items_data = None


# ---------- VIEW DATA ----------

st.divider()

st.subheader("Stored Invoices")

if os.path.exists(INVOICE_FILE):
    st.dataframe(pd.read_csv(INVOICE_FILE))

st.subheader("Stored Items")

if os.path.exists(ITEM_FILE):
    st.dataframe(pd.read_csv(ITEM_FILE))
