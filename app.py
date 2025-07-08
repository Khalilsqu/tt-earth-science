import streamlit as st
# Render schedule with custom HTML and JavaScript
from streamlit_gsheets import GSheetsConnection
import streamlit.components.v1 as components
import pandas as pd

# Configure page for wide layout
st.set_page_config(page_title="Earth Sciencs", layout="wide")

# Title for the app
st.markdown("<h1 style='font-size:32px;'>Earth Sciencs TimeTable</h1>", unsafe_allow_html=True)

# Term selector
# term_files = {'Fall 2024': 'fall2024_split_slot.xlsx', 'Fall 2025': 'fall2025_split_slot.xlsx'}
# selected_term = st.sidebar.selectbox('Select Term', list(term_files.keys()))
# file_to_load = term_files[selected_term]

# Load the processed schedule data
# @st.cache_data
# def load_data(file_path):
#     return pd.read_excel(file_path)

# df = load_data(file_to_load)

conn = st.connection("gsheets", type=GSheetsConnection)

df = conn.read(
    ttl="30m",
)

data_source = sorted(df['Data Source'].astype(str).unique())
# Single select Term with default 'Fall 2025'
# default_idx = data_source.index('fall 2025') if 'fall 2025' in data_source else 0
# find uniques and choose the last one as default
default_idx = 1
selected_source = st.sidebar.selectbox('Data Source', data_source, index=default_idx,
                                       help="Select either the Original course schedule or the updated done by Khalil Al Hooti"
                                      )
# Apply term filter
df = df[df['Data Source'] == selected_source]

# Sidebar for filtering
st.sidebar.header("Filters")

# Level filter
if 'Level' in df.columns:
    selected_level = st.sidebar.radio('Level', ['UG', 'PG', 'Both'], index=2,
                                      help="Filter by course level: UG, PG, or Both")
    if selected_level != 'Both':
        df = df[df['Level'] == selected_level].copy()


staff_names = sorted([name for name in df['Staff Name'].astype(str).unique() if name != 'nan'])
selected_staff = st.sidebar.multiselect('Select Instructor(s)', staff_names,
                                        help="Select one or more instructors to filter the schedule",
                                        )

# Filter data based on selection
if selected_staff:
    df_filtered = df[df['Staff Name'].isin(selected_staff)].copy()
else:
    df_filtered = df.copy()



# Schedule type selector
schedule_type = st.sidebar.selectbox('Schedule Type', ['Lecture', 'Exam'],
                                     help="Select 'Lecture' for regular classes or 'Exam' for final exam schedule"
                                     )

# Time slot filter based on schedule type

help_time_slot="Select one or more time slots to filter the schedule"
if schedule_type == 'Lecture':
    time_options = sorted(df_filtered['Time'].dropna().unique())
    selected_times = st.sidebar.multiselect('Select Time Slots', time_options,
                                            help=help_time_slot,
                                            )
    if selected_times:
        df_filtered = df_filtered[df_filtered['Time'].isin(selected_times)].copy()
else:  # Exam
    exam_times = sorted(df_filtered['Exam Time'].dropna().unique())
    selected_times = st.sidebar.multiselect('Select Exam Time Slots', exam_times,
                                            help=help_time_slot,
                                            )
    if selected_times:
        df_filtered = df_filtered[df_filtered['Exam Time'].isin(selected_times)].copy()

# View mode selector
display_mode = st.sidebar.selectbox('View Mode', ['Schedule View', 'Table View'],
                                    help="Choose 'Schedule View' for a visual timetable or 'Table View' for a detailed list"
                                    )
if display_mode == 'Table View':
    # Show full DataFrame in table mode
    if schedule_type == 'Exam':
        # Drop duplicate rows based on Course Code only
        exam_df = df_filtered.dropna(subset=['Course Code']).drop_duplicates(subset=['Course Code'])
        # Reindex starting from 1
        exam_df.index = range(1, len(exam_df) + 1)
        # Remove Data Source column
        exam_df = exam_df.drop(columns=['Data Source'], errors='ignore')
        st.dataframe(exam_df)
    else:
        # Reindex starting from 1
        df_filtered.index = range(1, len(df_filtered) + 1)
        # Remove Data Source column
        df_filtered = df_filtered.drop(columns=['Data Source'], errors='ignore')
        st.dataframe(df_filtered, height=600)
    st.stop()

# Build cell content including Course Code, Section, Staff Name, and Location
df_filtered['Cell'] = df_filtered.apply(
    lambda r: f"{r['Course Code']} ({r['Section']})\n{r['Staff Name']}\n{r['Hall']}",
    axis=1
)

if display_mode == 'Schedule View':
    if schedule_type == 'Lecture':
        # Define days and order
        days_order = ["SUN", "MON", "TUE", "WED", "THU"]

        # Prepare pivot table: index=Time slots, columns=Days, values=Cell
        schedule = df_filtered[['Day', 'Time', 'Cell']].dropna()
        pivot = schedule.pivot_table(
            index='Time',
            columns='Day',
            values='Cell',
            aggfunc=lambda cells: "\n---\n".join(cells)
        )

        # Reorder columns and fill missing cells
        pivot = pivot.reindex(columns=days_order).fillna("")
        # Prepare JSON data
        schedule_data = pivot.reset_index().fillna("").to_dict(orient="records")
        columns = ["Time"] + days_order
    else:
        # Exam schedule view: pivot by exam time and date, using only course and instructor, removing duplicates
        exam_df = df_filtered[['Exam Date', 'Exam Time', 'Course Code', 'Staff Name']].dropna()
        # Keep one entry per course
        exam_df = exam_df.drop_duplicates(subset=['Course Code'])
        exam_df['Exam Date'] = pd.to_datetime(exam_df['Exam Date']).dt.date
        # Build cell with course and instructor only
        exam_df['Cell'] = exam_df.apply(lambda r: f"{r['Course Code']}\n{r['Staff Name']}", axis=1)
        pivot = exam_df.pivot_table(
            index='Exam Time',
            columns='Exam Date',
            values='Cell',
            aggfunc=lambda cells: "\n---\n".join(cells)
        )
        # Sort Exam Time slots by start time
        # Sort Exam Time slots by start time, placing unparsable entries at the end
        times = list(pivot.index)
        # Parse start times, default to max for invalid
        parsed = []
        for t in times:
            try:
                start = pd.to_datetime(t.split(" - ")[0].strip(), format="%I:%M%p")
            except Exception:
                start = pd.Timestamp.max
            parsed.append(start)
        # Order by parsed times
        ordered = [time for _, time in sorted(zip(parsed, times))]
        pivot = pivot.reindex(index=ordered)
        # Reorder columns and fill missing cells
        pivot = pivot.reindex(columns=sorted(pivot.columns)).fillna("")
        # Prepare JSON data
        date_cols = [d.strftime('%Y-%m-%d') for d in pivot.columns]
        pivot.columns = date_cols
        schedule_data = pivot.reset_index().to_dict(orient="records")
        columns = ["Exam Time"] + date_cols


# Build table headers and rows
headers = ''.join(f'<th>{col}</th>' for col in columns)
rows_html = ''
for row in schedule_data:
    row_cells = ''
    for col in columns:
        cell = row.get(col, "")
        # split parts by the text separator and join with HTML horizontal rule
        parts = str(cell).split("\n---\n")
        cell_html = '<hr style="border-top:1px dashed #666; width:100%; margin:4px 0;">'.join(parts)
        row_cells += f'<td>{cell_html}</td>'
    rows_html += f'<tr>{row_cells}</tr>'

# HTML template
html = f"""
<!DOCTYPE html>
<html>
<head>
<style>
  table {{ width:100%; border-collapse: collapse; min-height: 100vh; }}
  th, td {{ border: 1px solid #ddd; padding: 8px; vertical-align: top; white-space: pre-line; text-align: center; }}
  th {{ background-color: #333; color: #fff; }}
  td {{ background-color: #f9f9f9; color: #333; }}
  hr {{ border: 0; border-top: 1px dashed #666; width: 100%; margin: 4px 0; }}
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

# Display the HTML component with adaptive height
components.html(html, height=700, scrolling=True)

# When showing exam schedule view, list courses without final exams
if schedule_type == 'Exam' and display_mode == 'Schedule View':
    # Identify courses without exam entries
    exam_courses = set(
        df_filtered[['Exam Date','Course Code']]
        .dropna()
        .drop_duplicates(subset=['Course Code'])['Course Code']
    )
    all_courses = set(df_filtered['Course Code'].dropna().unique())
    no_exam = sorted(all_courses - exam_courses)
    if no_exam:
        st.markdown("**Courses without Final Exam:**")
        for course in no_exam:
            st.markdown(f"- {course}")
