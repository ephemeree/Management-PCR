from app import app
# Trigger reload 2
import os
from app.models.connection import get_db_connection
try:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE tbl_draft_targets dt
        JOIN tbl_master_indicators mi ON dt.indicator_id = mi.indicator_id
        JOIN tbl_target_categories tc ON mi.category_id = tc.category_id
        JOIN tbl_ipcr_ret_review rr ON rr.emp_id = dt.emp_id AND rr.term_id = mi.term_id
        SET dt.review_status = 'Approved'
        WHERE tc.category_name IN ('A. Research', 'B. Extension Services / Training / Advisory')
          AND rr.overall_status = 'Approved'
    """)
    conn.commit()
    cursor.close()
    conn.close()
    print("[DB REPAIR] Successfully restored approved RET targets status.")
except Exception as e:
    print(f"[DB REPAIR ERROR] {e}")
if __name__ == '__main__':
    debug_mode = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(debug=debug_mode, port=5000)
