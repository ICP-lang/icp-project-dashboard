import os
import pandas as pd
import streamlit as st
from supabase import create_client

# NOTE: Do NOT commit secrets into source control. Use `.streamlit/secrets.toml` or environment variables.

# 1. Page config
st.set_page_config(page_title="ICP Project Dashboard", page_icon="🏊", layout="wide")

# 2. Credentials via Streamlit secrets or environment variables
SUPABASE_URL = (st.secrets.get("SUPABASE_URL") if hasattr(st, "secrets") else None) or os.getenv("SUPABASE_URL")
SUPABASE_KEY = (st.secrets.get("SUPABASE_KEY") if hasattr(st, "secrets") else None) or os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("Supabase credentials not found. Add them to Streamlit secrets or environment variables.")
    st.stop()

# 3. Cached supabase client
@st.cache_resource
def get_supabase(url: str, key: str):
    return create_client(url, key)

supabase = get_supabase(SUPABASE_URL, SUPABASE_KEY)

# 4. Sidebar branding & controls
with st.sidebar:
    st.title("🏗️ ICP Admin")
    st.markdown("---")
    st.info("Managing project data for **Innovative Custom Pools**")
    st.write("**Current Project:** P-0001 (Connie Morgan)")
    st.markdown("---")
    st.header("Filters")
    min_price = st.number_input("Min unit price", value=0.0, step=1.0, format="%.2f")
    max_price = st.number_input("Max unit price (0 = unlimited)", value=0.0, step=1.0, format="%.2f")
    if st.button("🔄 Refresh data"):
        st.cache_data.clear()
        st.experimental_rerun()

# 5. Fetch & cache data
@st.cache_data(ttl=300)
def fetch_lineitems():
    resp = supabase.table("lineitems").select("*").execute()
    # Handle response shapes from different client versions
    data = None
    if hasattr(resp, "data"):
        data = resp.data
    elif isinstance(resp, dict):
        data = resp.get("data")
    elif isinstance(resp, list) and resp and isinstance(resp[0], dict):
        data = resp
    else:
        data = []

    if getattr(resp, "error", None):
        raise RuntimeError(getattr(resp.error, "message", str(resp.error)))

    return data or []

# 6. Main UI
st.title("🏊 Innovative Custom Pools Dashboard")
st.markdown("---")

try:
    with st.spinner("Loading data..."):
        data = fetch_lineitems()

    df = pd.DataFrame(data)
    if df.empty:
        st.warning("No line items found in the database. Please re-run the PDF importer.")
        st.stop()

    # Normalize columns and types
    df['itemdescription'] = df.get('itemdescription', "").fillna("").astype(str)
    df['unitprice'] = pd.to_numeric(df.get('unitprice', 0), errors='coerce').fillna(0.0)
    df['quantity'] = pd.to_numeric(df.get('quantity', 1), errors='coerce').fillna(1)
    df['total'] = df['unitprice'] * df['quantity']
    df['material'] = df.get('material', "").fillna("").astype(str)

    # KPIs
    total_items = len(df)
    total_value = df['total'].sum()
    avg_price = df['unitprice'].mean() if total_items else 0.0

    c1, c2, c3 = st.columns(3)
    c1.metric("Project Items", f"{total_items:,}")
    c2.metric("Total Project Value", f"${total_value:,.2f}")
    c3.metric("Avg Unit Price", f"${avg_price:,.2f}")

    # Filters + search
    st.markdown("### 🔍 Search & Filter Line Items")
    search_query = st.text_input("Search item or material...", placeholder="e.g. Travertine, Fencing, Pebble")
    material_options = ["All"] + sorted([m for m in df['material'].unique() if m])
    selected_material = st.selectbox("Material", material_options)

    # Apply filters
    filtered = df.copy()
    if search_query:
        q = search_query.lower()
        filtered = filtered[filtered['itemdescription'].str.lower().str.contains(q) | filtered['material'].str.lower().str.contains(q)]
    if selected_material != "All":
        filtered = filtered[filtered['material'] == selected_material]
    if max_price > 0:
        filtered = filtered[(filtered['unitprice'] >= min_price) & (filtered['unitprice'] <= max_price)]
    else:
        filtered = filtered[filtered['unitprice'] >= min_price]

    st.dataframe(filtered.sort_values('total', ascending=False), use_container_width=True, hide_index=True)

    # Charts & extras
    st.markdown("### 🔢 Summary")
    top_by_value = filtered.groupby('itemdescription')['total'].sum().sort_values(ascending=False).head(10)
    st.bar_chart(top_by_value)

    csv = filtered.to_csv(index=False)
    st.download_button("Download filtered CSV", csv, file_name="lineitems.csv", mime="text/csv")

except Exception as e:
    st.error("Connection Error: unable to fetch line items.")
    st.exception(e)
