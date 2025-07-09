import streamlit as st
from streamlit_gsheets import GSheetsConnection
import streamlit.components.v1 as components
import pandas as pd
from html import escape  # makes sure quotes & special chars are safe

# ——— Read any existing query‐params —————————————————————————————
params = st.query_params
DEFAULT_LEVEL = "Both"
DEFAULT_TYPE  = "Lecture"
DEFAULT_VIEW  = "Schedule View"

# ——— Page setup ——————————————————————————————————————————————
st.set_page_config(page_title="Earth Sciences", layout="wide")
st.markdown("<h1 style='font-size:32px;'>Earth Sciences TimeTable</h1>", unsafe_allow_html=True)

# ——— Load the sheet ————————————————————————————————————————————
conn = st.connection("gsheets", type=GSheetsConnection)
df = conn.read(ttl="30m")

# ——— Data Source selector ——————————————————————————————————————
data_sources = sorted(df['Data Source'].dropna().unique().astype(str))
DEFAULT_SOURCE = data_sources[-1]
src = params.get("source", DEFAULT_SOURCE)
if src not in data_sources:
    src = DEFAULT_SOURCE
selected_source = st.sidebar.selectbox(
    "Data Source",
    data_sources,
    index=data_sources.index(src),
    help="Original vs updated schedule"
)

# ——— Level selector —————————————————————————————————————————
levels = ["UG", "PG", "Both"]
lvl = params.get("level", DEFAULT_LEVEL)
if lvl not in levels:
    lvl = DEFAULT_LEVEL
selected_level = st.sidebar.radio(
    "Level",
    levels,
    index=levels.index(lvl),
    help="UG, PG, or Both"
)

# ——— Apply Data Source + Level so Staff list is accurate ——————————————
df = df[df['Data Source'] == selected_source]
if selected_level != "Both" and 'Level' in df.columns:
    df = df[df['Level'] == selected_level]

# ——— Schedule Type selector ——————————————————————————————————
types = ["Lecture", "Exam"]
typ = params.get("type", DEFAULT_TYPE)
if typ not in types:
    typ = DEFAULT_TYPE
schedule_type = st.sidebar.selectbox(
    "Schedule Type",
    types,
    index=types.index(typ),
    help="Lecture vs Exam"
)

# ——— Course filter ———————————————————————————————————————
courses = sorted(df['Course Code'].dropna().unique().astype(str))
selected_courses = st.sidebar.multiselect(
    "Select Course(s)",
    courses,
    help="Filter by one or more courses"
)
if selected_courses:
    df = df[df['Course Code'].isin(selected_courses)]

# ——— Staff filter ———————————————————————————————————————
staff_names = sorted(df['Staff Name'].dropna().unique().astype(str))
selected_staff = st.sidebar.multiselect(
    "Select Instructor(s)",
    staff_names,
    help="Filter by one or more instructors"
)
if selected_staff:
    df = df[df['Staff Name'].isin(selected_staff)]

# ——— Time‐slot filter ———————————————————————————————————————
time_help = "Select one or more time slots"
if schedule_type == "Lecture":
    time_options = sorted(df['Time'].dropna().unique().astype(str))
    selected_times = st.sidebar.multiselect("Select Time Slots", time_options, help=time_help)
    if selected_times:
        df = df[df['Time'].isin(selected_times)]
else:
    exam_options = sorted(df['Exam Time'].dropna().unique().astype(str))
    selected_times = st.sidebar.multiselect("Select Exam Time Slots", exam_options, help=time_help)
    if selected_times:
        df = df[df['Exam Time'].isin(selected_times)]

# ——— View Mode selector —————————————————————————————————————
views = ["Schedule View", "Table View"]
vw = params.get("view", DEFAULT_VIEW)
if vw not in views:
    vw = DEFAULT_VIEW
display_mode = st.sidebar.selectbox(
    "View Mode",
    views,
    index=views.index(vw),
    help="Schedule vs Table"
)

# ——— Write all four back into the URL ————————————————————————
st.query_params.from_dict({
    "source": selected_source,
    "level":  selected_level,
    "type":   schedule_type,
    "view":   display_mode
})

# ——— Render Table View ——————————————————————————————————————
if display_mode == "Table View":
    if schedule_type == "Exam":
        exam_df = (
            df.dropna(subset=['Course Code'])
              .drop_duplicates(subset=['Course Code'])
              .drop(columns=['Data Source'], errors='ignore')
        )
        exam_df.index = range(1, len(exam_df) + 1)
        st.dataframe(exam_df)
    else:
        df2 = df.drop(columns=['Data Source'], errors='ignore')
        df2.index = range(1, len(df2) + 1)
        st.dataframe(df2, height=600)
    st.stop()

# ——— Build Cell content with CSS tooltip —————————————————————————————
INFO_ICON = "ⓘ"
df['Cell'] = df.apply(
    lambda r: (
        f"{r['Course Code']} ({r['Section']}) "
        f"<span class='tooltip' data-tooltip='{escape(str(r['Course Name']))}'"
        f" style='font-weight:bold; margin-left:4px;'>{INFO_ICON}</span><br>"
        f"{r['Staff Name']}<br>"
        f"{r['Hall']}"
    ),
    axis=1,
)

# ——— Build Schedule Data —————————————————————————————————————
if schedule_type == "Lecture":
    days_order = ["SUN", "MON", "TUE", "WED", "THU"]
    sched = df[['Day','Time','Cell']].dropna()
    pivot = sched.pivot_table(
        index='Time',
        columns='Day',
        values='Cell',
        aggfunc=lambda cells: "<hr style='border-top:1px dotted #a86032; margin:2px 0;'></hr>".join(cells)
    ).reindex(columns=days_order).fillna("")
    schedule_data = pivot.reset_index().to_dict(orient="records")
    columns = ["Time"] + days_order

else:
    exam_df = (
        df[['Exam Date','Exam Time','Course Code','Staff Name']]
        .dropna()
        .drop_duplicates(subset=['Course Code'])
    )
    exam_df['Exam Date'] = pd.to_datetime(exam_df['Exam Date']).dt.date
    exam_df['Cell'] = exam_df.apply(lambda r: f"{r['Course Code']}\n{r['Staff Name']}", axis=1)
    pivot = exam_df.pivot_table(
        index='Exam Time',
        columns='Exam Date',
        values='Cell',
        aggfunc=lambda cs: "\n---\n".join(cs)
    )
    # sort by parsed start times
    times = list(pivot.index)
    parsed = []
    for t in times:
        try:
            parsed.append(pd.to_datetime(t.split(" - ")[0].strip(), format="%I:%M%p"))
        except:
            parsed.append(pd.Timestamp.max)
    ordered = [t for _, t in sorted(zip(parsed, times))]
    pivot = pivot.reindex(index=ordered).fillna("")
    date_cols = [d.strftime('%Y-%m-%d') for d in pivot.columns]
    pivot.columns = date_cols
    schedule_data = pivot.reset_index().to_dict(orient="records")
    columns = ["Exam Time"] + date_cols

# ——— Render HTML Schedule + CSS Tooltip Styles —————————————————————
headers = "".join(f"<th>{c}</th>" for c in columns)
rows_html = ""
for row in schedule_data:
    cells = ""
    for c in columns:
        parts = str(row.get(c, "")).split("\n---\n")
        cells += "<td>" + "<hr style='border-top:1px dashed #666; margin:4px 0;'>".join(parts) + "</td>"
    rows_html += f"<tr>{cells}</tr>"

html = f"""
<!DOCTYPE html>
<html>
<head>
  <style>
    /* table styling */
    table {{ width:100%; border-collapse: collapse; }}
    th, td {{ border:1px solid #ddd; padding:8px; white-space:pre-line; text-align:center; }}
    th {{ background:#333; color:#fff; }}
    td {{ background:#f9f9f9; }}
    hr {{ border:0; border-top:1px dashed #666; }}

    /* CSS Tooltip */
    .tooltip {{ position: relative; display: inline-block; cursor: help;
      font-family: "Segoe UI Symbol", "Arial Unicode MS", sans-serif;
      font-size: 16px;
      line-height: 1; }}
    .tooltip::after {{
      content: attr(data-tooltip);
      position: absolute;
      bottom: 100%;
      left: 50%;
      transform: translateX(-50%);
      padding: 4px 8px;
      white-space: nowrap;
      background: rgba(0,0,0,0.75);
      color: #fff;
      border-radius: 4px;
      pointer-events: none;
      opacity: 0;
      transition: opacity 0.1s ease-out;
      z-index: 10;
    }}
    .tooltip:hover::after {{
      opacity: 1;
    }}
  </style>
</head>
<body>
  <table>
    <thead><tr>{headers}</tr></thead>
    <tbody>{rows_html}</tbody>
  </table>
</body>
</html>
"""

components.html(html, height=700, scrolling=True)

# ——— List courses without final exam ————————————————————————————
if schedule_type == "Exam":
    exam_courses = set(df[['Exam Date','Course Code']].dropna()['Course Code'])
    all_courses  = set(df['Course Code'].dropna())
    no_exam = sorted(all_courses - exam_courses)
    if no_exam:
        st.markdown("**Courses without Final Exam:**")
        for c in no_exam:
            st.markdown(f"- {c}")
