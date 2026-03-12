import sqlite3
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Font

DB_PATH = "db/users.db"  # replace with your actual DB path

def increment_user_usage(user_id):
    """Increment the files_generated counter and update last_used for a given user."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    today = datetime.now().date()
    
    # Increment total files generated and update last_used
    cursor.execute("""
        UPDATE users
        SET files_generated = files_generated + 1,
            last_used = ?
        WHERE user_id = ?
    """, (today, user_id))
    
    conn.commit()
    conn.close()

def get_statistics():
    """
    Return a tuple of high-level statistics:
    (
        total_users,
        total_files,
        active_today,
        total_payments,
        payments_today,
        payments_this_month
    )
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1️⃣ Total users
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]

    # 2️⃣ Total files generated
    cursor.execute("SELECT SUM(files_generated) FROM users")
    total_files = cursor.fetchone()[0] or 0

    # 3️⃣ Users active today
    today = datetime.now().strftime("%Y-%m-%d")
    cursor.execute(
        "SELECT COUNT(*) FROM users WHERE last_used = ?",
        (today,)
    )
    active_today = cursor.fetchone()[0]

    # 4️⃣ Total payments
    cursor.execute("SELECT SUM(amount) FROM payments")
    total_payments = cursor.fetchone()[0] or 0

    # 5️⃣ Today's payments
    cursor.execute(
        "SELECT SUM(amount) FROM payments WHERE date = ?",
        (today,)
    )
    payments_today = cursor.fetchone()[0] or 0

    # 6️⃣ This month's income (1st → last day)
    first_day_of_month = datetime.now().replace(day=1).strftime("%Y-%m-%d")

    # First day of next month (safe way)
    if datetime.now().month == 12:
        first_day_next_month = datetime.now().replace(
            year=datetime.now().year + 1, month=1, day=1
        )
    else:
        first_day_next_month = datetime.now().replace(
            month=datetime.now().month + 1, day=1
        )

    first_day_next_month = first_day_next_month.strftime("%Y-%m-%d")

    cursor.execute(
        """
        SELECT SUM(amount)
        FROM payments
        WHERE date >= ? AND date < ?
        """,
        (first_day_of_month, first_day_next_month)
    )
    payments_this_month = cursor.fetchone()[0] or 0

    conn.close()

    return (
        total_users,
        total_files,
        active_today,
        total_payments,
        payments_today,
        payments_this_month
    )
def export_monthly_income_to_excel(output_path="monthly_income.xlsx"):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get monthly income grouped by year-month
    cursor.execute("""
        SELECT 
            strftime('%Y', date) AS year,
            strftime('%m', date) AS month,
            SUM(amount) as total_income
        FROM payments
        GROUP BY year, month
        ORDER BY year, month
    """)

    results = cursor.fetchall()
    conn.close()

    # Create Excel workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Monthly Income"

    # Header
    headers = ["Year", "Month", "Total Income"]
    ws.append(headers)

    # Make header bold
    for cell in ws[1]:
        cell.font = Font(bold=True)

    # Add data
    for row in results:
        year, month, total_income = row
        ws.append([year, month, total_income or 0])

    # Auto column width
    for column in ws.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        ws.column_dimensions[column_letter].width = max_length + 2

    wb.save(output_path)

    return output_path

# def get_total_payments():
#     conn = sqlite3.connect(DB_PATH)
#     cursor = conn.cursor()
    
#     cursor.execute("SELECT SUM(amount) FROM payments")
#     total = cursor.fetchone()[0] or 0
    
#     conn.close()
#     return total

# def get_today_payments():
#     from datetime import datetime
#     today = datetime.now().strftime("%Y-%m-%d")
    
#     conn = sqlite3.connect(DB_PATH)
#     cursor = conn.cursor()
    
#     cursor.execute("SELECT SUM(amount) FROM payments WHERE date = ?", (today,))
#     total_today = cursor.fetchone()[0] or 0
    
#     conn.close()
#     return total_today

