"""Seed mock email data for demos. All rows are tagged is_demo=1.

Categories: scan_design / eship / invoice_inquiry / payment / other

Wipe with:  python -m core.db wipe-demo
"""
import argparse
import json
from datetime import datetime, timedelta
from .db import get_conn, init_db, wipe_demo
from .classifier import classify_keyword

MOCK_ACCOUNT = "sunweijie0915@outlook.com"

DEMO_EMAILS = [
    # ---- Scan & Design Files ----
    {
        "from_addr": "info@smile-dental.ca",
        "from_name": "Smile Dental Clinic",
        "subject": "Patient #1042 - Upper arch STL scan",
        "body": "Hi, please find attached the upper arch STL scan for patient #1042 (John Doe). Two files: upper.stl and bite.stl. Please proceed with the design. Thank you.",
        "summary": "Smile Dental 发来患者 #1042 上颌 STL 扫描文件，需出设计",
        "summary_en": "Smile Dental sent upper arch STL scan for patient #1042, design requested",
        "key_fields": {"clinic_name": "Smile Dental Clinic", "patient_id": "#1042", "design_type": "上颌修复", "file_count": "2"},
        "todo_zh": "处理 Smile Dental 患者 #1042 的 STL 设计件",
        "todo_en": "Process STL design for Smile Dental patient #1042",
        "attachments": ["upper.stl", "bite.stl"],
    },
    {
        "from_addr": "lab@brightsmile.ca",
        "from_name": "BrightSmile Lab",
        "subject": "STL files - implant case P-2089",
        "body": "Please find attached 3 STL files for implant case P-2089. Patient: Mary Smith. Design needed: implant crown x2, upper right. Rush order please.",
        "summary": "BrightSmile 发来种植案例 P-2089 的3个STL文件，急单",
        "summary_en": "BrightSmile sent 3 STL files for implant case P-2089, rush order",
        "key_fields": {"clinic_name": "BrightSmile Lab", "patient_id": "P-2089", "design_type": "种植冠", "file_count": "3"},
        "todo_zh": "急：处理 BrightSmile P-2089 种植冠设计",
        "todo_en": "Rush: process BrightSmile P-2089 implant crown design",
        "attachments": ["P-2089_upper.stl", "P-2089_lower.stl", "P-2089_bite.stl"],
    },
    {
        "from_addr": "reception@greentree-dental.com",
        "from_name": "Green Tree Dental",
        "subject": "Scan design request - Patient Li Wei #3301",
        "body": "Hello, attached is the scan for patient Li Wei (#3301). Full arch scan, design required for veneers x4 upper front. Let me know if you need anything else.",
        "summary": "Green Tree Dental 发来患者 Li Wei #3301 全弓扫描，需要4颗上前牙贴面设计",
        "summary_en": "Green Tree Dental sent full arch scan for patient Li Wei #3301, 4 upper veneer design needed",
        "key_fields": {"clinic_name": "Green Tree Dental", "patient_id": "#3301", "design_type": "贴面", "file_count": "1"},
        "todo_zh": "处理 Green Tree Dental #3301 贴面设计",
        "todo_en": "Process Green Tree Dental #3301 veneer design",
        "attachments": ["LiWei_3301_fullarch.stl"],
    },
    {
        "from_addr": "dr.wong@cityortho.ca",
        "from_name": "City Orthodontics",
        "subject": "Aligner scan - case #ORT-558",
        "body": "Hi team, attached scans for aligner case ORT-558. Patient needs 18-step aligner plan. Please provide STL outputs for each step. Timeline: 2 weeks.",
        "summary": "City Orthodontics 发来矫正案例 ORT-558，需要18步隐形牙套设计，2周内完成",
        "summary_en": "City Orthodontics aligner case ORT-558, 18-step plan needed, 2-week timeline",
        "key_fields": {"clinic_name": "City Orthodontics", "patient_id": "#ORT-558", "design_type": "隐形矫正", "file_count": "2"},
        "todo_zh": "处理 City Orthodontics ORT-558 矫正方案设计",
        "todo_en": "Process City Orthodontics ORT-558 aligner plan",
        "attachments": ["ORT558_upper.stl", "ORT558_lower.stl"],
    },

    # ---- Shipping & Logistics ----
    {
        "from_addr": "noreply@eship.ca",
        "from_name": "eShip Canada",
        "subject": "Your shipment has been picked up - Tracking #1Z9999W99999999999",
        "body": "Your shipment has been picked up by UPS. Tracking number: 1Z9999W99999999999. Estimated delivery: May 7, 2026. Sender: DentalSupply Co. Destination: your address.",
        "summary": "eShip 通知 UPS 快递已取件，追踪号 1Z9999W99999999999，预计5月7日到达",
        "summary_en": "eShip: UPS shipment picked up, tracking 1Z9999W99999999999, est. delivery May 7",
        "key_fields": {"carrier": "UPS", "tracking_no": "1Z9999W99999999999", "sender": "DentalSupply Co", "expected_delivery": "May 7, 2026"},
        "todo_zh": "追踪 UPS 包裹 1Z9999W99999999999",
        "todo_en": "Track UPS parcel 1Z9999W99999999999",
        "attachments": [],
    },
    {
        "from_addr": "tracking@fedex.com",
        "from_name": "FedEx",
        "subject": "FedEx Shipment Delivered - #7489234892",
        "body": "Your FedEx package (tracking #7489234892) was delivered on May 3, 2026 at 2:14 PM. Signed by: RECEPTION. Sender: Lab Materials Inc.",
        "summary": "FedEx 包裹 #7489234892 已于5月3日签收，寄件人 Lab Materials Inc",
        "summary_en": "FedEx package #7489234892 delivered May 3, signed by RECEPTION",
        "key_fields": {"carrier": "FedEx", "tracking_no": "7489234892", "sender": "Lab Materials Inc", "expected_delivery": "已签收 May 3"},
        "todo_zh": "确认 FedEx 包裹 #7489234892 已收货",
        "todo_en": "Confirm FedEx package #7489234892 received",
        "attachments": [],
    },
    {
        "from_addr": "orders@dentalwarehouse.com",
        "from_name": "Dental Warehouse",
        "subject": "Order #DW-8821 shipped via Purolator",
        "body": "Your order #DW-8821 has been dispatched via Purolator. Tracking: 329876543210. Expected delivery: May 8-9, 2026. Items: zirconia discs x10, scanning spray x5.",
        "summary": "Dental Warehouse 订单 #DW-8821 已通过 Purolator 发货，预计5月8-9日到",
        "summary_en": "Dental Warehouse order #DW-8821 shipped via Purolator, tracking 329876543210",
        "key_fields": {"carrier": "Purolator", "tracking_no": "329876543210", "sender": "Dental Warehouse", "expected_delivery": "May 8-9, 2026"},
        "todo_zh": "追踪 Dental Warehouse 订单 #DW-8821",
        "todo_en": "Track Dental Warehouse order #DW-8821",
        "attachments": [],
    },

    # ---- Invoice Inquiry ----
    {
        "from_addr": "accounting@clinic-a.ca",
        "from_name": "Clinic A Accounting",
        "subject": "Invoice request for March services",
        "body": "Hi, could you please send us the invoice for all services rendered in March 2026? We need it for our accounting by end of this week. Total should be around $3,200. Thanks.",
        "summary": "Clinic A 要求提供3月份服务发票，总金额约 $3,200，本周内需要",
        "summary_en": "Clinic A requesting March 2026 invoice (~$3,200), needed by end of week",
        "key_fields": {"requester": "Clinic A Accounting", "invoice_ref": "March 2026", "amount": "~$3,200", "inquiry_type": "请求开票"},
        "todo_zh": "给 Clinic A 开3月份发票",
        "todo_en": "Issue March invoice to Clinic A",
        "attachments": [],
    },
    {
        "from_addr": "finance@brightsmile.ca",
        "from_name": "BrightSmile Finance",
        "subject": "Missing invoice INV-2026-031",
        "body": "Hello, we have not received invoice INV-2026-031 for the implant cases in April. Could you resend it? Amount should be $1,850. Our records show it was due April 30.",
        "summary": "BrightSmile 未收到发票 INV-2026-031，金额 $1,850，请重新发送",
        "summary_en": "BrightSmile missing invoice INV-2026-031 ($1,850), please resend",
        "key_fields": {"requester": "BrightSmile Finance", "invoice_ref": "INV-2026-031", "amount": "$1,850", "inquiry_type": "发票丢失"},
        "todo_zh": "重发发票 INV-2026-031 给 BrightSmile",
        "todo_en": "Resend invoice INV-2026-031 to BrightSmile",
        "attachments": [],
    },
    {
        "from_addr": "admin@greentree-dental.com",
        "from_name": "Green Tree Dental Admin",
        "subject": "Question about invoice INV-0089 amount",
        "body": "Hi, we received invoice INV-0089 for $2,400 but we expected $1,900 based on our quote. Could you please clarify the difference? Happy to discuss.",
        "summary": "Green Tree Dental 对发票 INV-0089 金额有异议，实收 $2,400 vs 报价 $1,900",
        "summary_en": "Green Tree Dental disputes invoice INV-0089 amount: billed $2,400 vs quoted $1,900",
        "key_fields": {"requester": "Green Tree Dental Admin", "invoice_ref": "INV-0089", "amount": "$2,400 (disputed)", "inquiry_type": "金额异议"},
        "todo_zh": "核实 INV-0089 金额差异，回复 Green Tree Dental",
        "todo_en": "Verify INV-0089 amount discrepancy, reply to Green Tree Dental",
        "attachments": [],
    },

    # ---- Payments ----
    {
        "from_addr": "payments@interac.ca",
        "from_name": "Interac e-Transfer",
        "subject": "You have received an Interac e-Transfer of $850.00",
        "body": "Dr. Sarah Wong has sent you an Interac e-Transfer of $850.00. Message: 'Payment for April cases - BrightSmile'. To deposit, log in to your bank. Reference: ETR-20260503-4421.",
        "summary": "收到 Dr. Sarah Wong 的 Interac e-Transfer $850，4月案例付款",
        "summary_en": "Received $850 Interac e-Transfer from Dr. Sarah Wong for April cases",
        "key_fields": {"payment_type": "Interac e-Transfer", "amount": "$850.00", "payer": "Dr. Sarah Wong", "due_date": "即时", "reference": "ETR-20260503-4421"},
        "todo_zh": "存入 Dr. Sarah Wong 的 $850 e-Transfer",
        "todo_en": "Deposit $850 e-Transfer from Dr. Sarah Wong",
        "attachments": [],
    },
    {
        "from_addr": "ar@dentalgroup.ca",
        "from_name": "Dental Group AR",
        "subject": "Invoice overdue - $1,200 - Please remit",
        "body": "This is a reminder that invoice INV-DG-2026-018 for $1,200 was due on April 25, 2026. Payment is now 8 days overdue. Please remit by wire transfer or cheque at your earliest convenience.",
        "summary": "Dental Group 催款：发票 INV-DG-2026-018 $1,200 已逾期8天",
        "summary_en": "Dental Group overdue payment reminder: INV-DG-2026-018 $1,200, 8 days past due",
        "key_fields": {"payment_type": "应付账款", "amount": "$1,200", "payer": "我方", "due_date": "April 25 (逾期)", "reference": "INV-DG-2026-018"},
        "todo_zh": "紧急：支付 Dental Group 逾期账款 $1,200",
        "todo_en": "Urgent: pay Dental Group overdue $1,200",
        "attachments": [],
    },
    {
        "from_addr": "billing@labsupplier.com",
        "from_name": "Lab Supplier Billing",
        "subject": "Monthly statement - April 2026 - $4,750 due",
        "body": "Please find your April 2026 statement attached. Total due: $4,750.00. Due date: May 15, 2026. Payment methods: cheque payable to Lab Supplier Inc., or wire transfer (details on statement).",
        "summary": "Lab Supplier 4月账单 $4,750，5月15日到期",
        "summary_en": "Lab Supplier April statement $4,750 due May 15, 2026",
        "key_fields": {"payment_type": "月度账单", "amount": "$4,750.00", "payer": "我方", "due_date": "May 15, 2026", "reference": "APR-2026-STMT"},
        "todo_zh": "5月15日前支付 Lab Supplier $4,750",
        "todo_en": "Pay Lab Supplier $4,750 by May 15",
        "attachments": ["April_2026_Statement.pdf"],
    },
    {
        "from_addr": "noreply@chequedeposit.ca",
        "from_name": "City Ortho Admin",
        "subject": "Cheque mailed - $2,100 for March invoices",
        "body": "Hi, we have mailed a cheque for $2,100.00 to cover March invoices INV-031, INV-033, INV-035. Cheque #4421. Please confirm once received.",
        "summary": "City Ortho 已邮寄 $2,100 支票支付3月份发票",
        "summary_en": "City Ortho mailed $2,100 cheque #4421 for March invoices",
        "key_fields": {"payment_type": "支票", "amount": "$2,100.00", "payer": "City Ortho Admin", "due_date": "邮寄中", "reference": "Cheque #4421"},
        "todo_zh": "等待收到 City Ortho 支票 #4421 $2,100",
        "todo_en": "Awaiting City Ortho cheque #4421 for $2,100",
        "attachments": [],
    },

    # ---- Other ----
    {
        "from_addr": "noreply@microsoft.com",
        "from_name": "Microsoft Account Team",
        "subject": "New sign-in detected for your account",
        "body": "We detected a new sign-in to your Microsoft account from Windows. If this was you, no action needed.",
        "summary": "微软账号新登录通知",
        "summary_en": "Microsoft account new sign-in notification",
        "key_fields": {},
        "todo_zh": None,
        "todo_en": None,
        "attachments": [],
    },
    {
        "from_addr": "newsletter@dentaltech.com",
        "from_name": "Dental Tech Weekly",
        "subject": "This week: new CAD/CAM systems review",
        "body": "In this week's issue: top 5 CAD/CAM systems for 2026, new zirconia materials, and an interview with Dr. Chen on digital dentistry workflows.",
        "summary": "牙科技术周刊：CAD/CAM系统评测",
        "summary_en": "Dental Tech Weekly: CAD/CAM systems review and zirconia materials",
        "key_fields": {},
        "todo_zh": None,
        "todo_en": None,
        "attachments": [],
    },
]


def seed():
    init_db()
    conn = get_conn()
    now = datetime.now()
    inserted = 0
    for i, e in enumerate(DEMO_EMAILS):
        cat_id, conf = classify_keyword(e["subject"], e["body"])
        received = (now - timedelta(hours=i * 1.5)).isoformat(timespec="seconds")

        cur = conn.execute(
            """
            INSERT OR IGNORE INTO emails
            (message_id, account_id, from_addr, from_name, subject, body, category,
             category_confidence, summary, summary_en, key_fields, status, received_at, is_demo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', ?, 1)
            """,
            (
                f"demo-{i:03d}",
                MOCK_ACCOUNT,
                e["from_addr"],
                e["from_name"],
                e["subject"],
                e["body"],
                cat_id,
                conf,
                e["summary"],
                e["summary_en"],
                json.dumps(e["key_fields"], ensure_ascii=False),
                received,
            ),
        )
        if cur.rowcount == 0:
            continue
        email_id = cur.lastrowid
        inserted += 1

        for fname in e.get("attachments", []):
            ext = fname.rsplit(".", 1)[-1].lower() if "." in fname else ""
            conn.execute(
                """
                INSERT INTO attachments (email_id, filename, local_path, size_bytes, is_demo)
                VALUES (?, ?, ?, ?, 1)
                """,
                (email_id, fname, f"data/attachments/demo/{fname}", 512000 if ext == "stl" else 102400),
            )

        if e.get("todo_zh"):
            conn.execute(
                """
                INSERT INTO todos (email_id, description, description_en, status, created_at, is_demo)
                VALUES (?, ?, ?, 'pending', ?, 1)
                """,
                (email_id, e["todo_zh"], e["todo_en"], received),
            )

    conn.commit()
    conn.close()
    print(f"Seeded {inserted} demo emails (skipped duplicates).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--wipe", action="store_true", help="Wipe demo data instead of seeding")
    args = parser.parse_args()
    if args.wipe:
        wipe_demo()
    else:
        seed()
