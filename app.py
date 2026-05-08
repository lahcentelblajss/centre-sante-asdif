from flask import Flask, render_template, request, redirect, url_for, send_file, jsonify, session, flash
import sqlite3
from datetime import date
import pandas as pd
from io import BytesIO
from fpdf import FPDF
import logging
import datetime
import json
import os
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "secret"

DB_NAME = "patients.db"

def get_icon(role):
    r = role.lower()

    if "infirmière de santé familiale" in r or "santé familiale" in r:
        return "👩‍⚕️"
    if "infirmière" in r or "ممرضة" in r:
        return "👩‍⚕️"
    if "sage-femme" in r or "قابلة" in r:
        return "🤰"
    if "agent de sécurité" in r or "حارس" in r:
        return "🛡️"
    if "agent de nettoyage" in r or "نظافة" in r:
        return "🧹"
    if "agent de saisie" in r:
        return "💻"
    if "chauffeur" in r or "سائق" in r:
        return "🚗"
    if "médecin" in r or "طبيب" in r:
        return "🩺"
    if "administratif" in r or "إداري" in r:
        return "🗂️"
     # 🆕 Jardinier (مهم)
    if "jardinier" in r or "gardener" in r:
        return "🌿"

    # 🆕 Pharmacien (مهم)
    if "pharmacien" in r or "pharmacy" in r:
        return "💊"

        return "👤"

# 📁 مهم جداً: نخلي الصور داخل static باش تظهر في الموقع
app.config["UPLOAD_FOLDER"] = "static/uploads"

# 📌 إنشاء المجلد تلقائياً إذا لم يكن موجود
if not os.path.exists(app.config["UPLOAD_FOLDER"]):
    os.makedirs(app.config["UPLOAD_FOLDER"])
    
# ===================== EXCEL PROCESS =====================
def process_excel(file_path):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    df = pd.read_excel(file_path)

    df.columns = df.columns.str.strip()

    df = df.rename(columns={
        "N°": "num",
        "NOM ET PRENOM": "nom",
        "AGE": "age",
        "SEXE": "sexe",
        "ADRESSE": "adresse",
        "G, De Consultation": "gde_consultation",
        "DATE": "date",
        "CAS": "cas"
    })

    df = df.fillna("")

    for index, row in df.iterrows():
        cursor.execute("""
        INSERT INTO patients
        (num, nom, sexe, age, adresse, gde_consultation, date, cas, excel_order)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(row.get("num", "")),
            str(row.get("nom", "")),
            str(row.get("sexe", "")),
            str(row.get("age", "")),
            str(row.get("adresse", "")),
            str(row.get("gde_consultation", "")),
            str(row.get("date", "")),
            str(row.get("cas", "")),
            index
        ))

    conn.commit()
    conn.close()
    
# ================== TRANSLATIONS ==================
def load_translations(lang):
    path = f"translations/{lang}.json"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

@app.context_processor
def inject_i18n():
    lang = session.get("lang", "fr")
    return {"lang": lang, "t": load_translations(lang)}

app.secret_key = "csr2asdif_secret_key"

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

DB_NAME = 'patients.db'

# ================== INIT DB ==================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # STAFF TABLE
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS staff (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            role TEXT,
            icon TEXT
        )
    ''')

    # PATIENTS TABLE
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            num TEXT,
            nom TEXT,
            sexe TEXT,
            age TEXT,
            adresse TEXT,
            gde_consultation TEXT,
            date TEXT,
            cas TEXT,
            excel_order INTEGER
        )
    ''')

    # USERS TABLE
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            role TEXT,
            last_login TEXT
        )
    ''')

    # LOGIN HISTORY TABLE
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS login_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            login_time TEXT,
            logout_time TEXT,
            ip TEXT,
            is_online INTEGER DEFAULT 0
        )
    ''')

    # 🔥 إضافة العمود فقط إذا ماكانش موجود
    try:
        cursor.execute("ALTER TABLE login_history ADD COLUMN is_online INTEGER DEFAULT 0")
    except:
        pass

    # FACILITIES TABLE
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS facilities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            icon TEXT,
            name_fr TEXT,
            name_ar TEXT
        )
    ''')

    # RENDEZVOUS TABLE
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rendezvous (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT,
            nom TEXT,
            date TEXT,
            heure TEXT,
            motif TEXT,
            notification_sent INTEGER DEFAULT 0
        )
    """)

    # 🔥 INIT DEFAULT DATA
    cursor.execute("SELECT COUNT(*) FROM facilities")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("""
        INSERT INTO facilities (icon, name_fr, name_ar)
        VALUES (?, ?, ?)
        """, [
            ("🕒", "Mise en service 2020", "تم الافتتاح سنة 2020"),
            ("🩺", "Consultations médicales", "الاستشارات الطبية"),
            ("🤱", "Salles d'accouchement", "قاعات الولادة"),
            ("🎉", "Salle événements", "قاعة المناسبات"),
            ("🧪", "Laboratoire", "مختبر"),
            ("🚑", "Urgences", "المستعجلات"),
            ("👶", "Santé mère-enfant", "صحة الأم والطفل"),
            ("💉", "Vaccination", "التلقيح"),
            ("🧼", "Buanderie", "مصبنة"),
            ("♻️", "Déchets", "النفايات"),
            ("💊", "Pharmacie", "صيدلية"),
            ("📋", "Réunions", "اجتماعات"),
            ("🗂️", "Admin", "التدبير الإداري"),
            ("👼", "Nouveau-nés", "حديثي الولادة"),
            ("🍳", "Cuisines", "مطبخ"),
            ("👮", "Garde", "الحراسة"),
            ("🏠", "Logements", "سكن وظيفي")
        ])

    conn.commit()
    conn.close()
    
def fix_rdv_table():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("PRAGMA table_info(rendezvous)")
    columns = [c[1] for c in cur.fetchall()]

    if "notification_sent" not in columns:
        cur.execute("""
            ALTER TABLE rendezvous
            ADD COLUMN notification_sent INTEGER DEFAULT 0
        """)

    conn.commit()
    conn.close()

def get_notifications():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
        SELECT id, nom, date, heure, type, notification_sent
        FROM rendezvous
    """)

    rows = cur.fetchall()
    conn.close()

    notifications = []
    now = datetime.now()

    for r in rows:
        try:
            rdv_time = datetime.strptime(f"{r[2]} {r[3]}", "%Y-%m-%d %H:%M")

            # ⏰ إشعار قبل أو في نفس الوقت
            if rdv_time >= now and rdv_time <= now + timedelta(days=1):

                notifications.append({
                    "id": r[0],
                    "nom": r[1],
                    "type": r[4]
                })

        except:
            continue

    return notifications

def fix_campaigns_table():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS campaigns(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            image TEXT
        )
    """)

    cursor.execute("PRAGMA table_info(campaigns)")
    columns = [col[1] for col in cursor.fetchall()]

    if "title" not in columns:
        cursor.execute("ALTER TABLE campaigns ADD COLUMN title TEXT")

    if "category" not in columns:
        cursor.execute("ALTER TABLE campaigns ADD COLUMN category TEXT")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS contact_info(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT,
            email TEXT,
            hours TEXT
        )
    """)

    cursor.execute("SELECT COUNT(*) FROM contact_info")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
            INSERT INTO contact_info(phone,email,hours)
            VALUES('+212 000000000','centre@email.com','08:30 - 16:30')
        """)

    conn.commit()
    conn.close()


# تشغيل مرة واحدة
init_db()
fix_campaigns_table()
fix_rdv_table()

# إصلاح icon column بدون crash
def fix_staff_table():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    try:
        cur.execute("ALTER TABLE staff ADD COLUMN icon TEXT")
    except:
        pass

    conn.commit()
    conn.close()

# استدعاء
fix_staff_table()

# ================== CONTEXT ==================
@app.context_processor
def inject_user():
    return {"current_user": session.get("user")}

# ================== LOGIN ==================
@app.route("/", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")

        if username == "Csr2Asdif" and password == "Csr22026":

            session["user"] = username
            ip = request.remote_addr

            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()

            # 🔴 نسد غير آخر session مفتوحة (بدقة)
            cursor.execute("""
                UPDATE login_history
                SET logout_time = datetime('now','localtime')
                WHERE id = (
                    SELECT id FROM login_history
                    WHERE username=? AND logout_time IS NULL
                    ORDER BY id DESC
                    LIMIT 1
                )
            """, (username,))

            # 🟢 نسجل login جديد
            cursor.execute("""
                INSERT INTO login_history (username, login_time, ip, logout_time)
                VALUES (?, datetime('now','localtime'), ?, NULL)
            """, (username, ip))

            session["login_id"] = cursor.lastrowid

            conn.commit()
            conn.close()

            return redirect("/dashboard")

        return "Login failed"

    return render_template("login.html")
    
@app.route("/facilities", methods=["GET"])
def facilities():
    if "user" not in session:
        return redirect("/login")

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT * FROM facilities")
    data = cur.fetchall()
    conn.close()

    return jsonify(data)

@app.route("/add_facility", methods=["POST"])
def add_facility():
    data = request.get_json()
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO facilities (icon, name_fr, name_ar)
        VALUES (?, ?, ?)
    """, (data["icon"], data["name_fr"], data["name_ar"]))

    conn.commit()
    conn.close()

    return jsonify({"success": True})

@app.route("/update_facility", methods=["POST"])
def update_facility():
    data = request.get_json()

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        UPDATE facilities
        SET icon=?, name_fr=?, name_ar=?
        WHERE id=?
    """, (data["icon"], data["name_fr"], data["name_ar"], data["id"]))

    conn.commit()
    conn.close()

    return jsonify({"success": True})

@app.route("/delete_facility", methods=["POST"])
def delete_facility():
    data = request.get_json()

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("DELETE FROM facilities WHERE id=?", (data["id"],))

    conn.commit()
    conn.close()

    return jsonify({"success": True})
# ================== DASHBOARD ==================
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/login")
    return render_template("dashboard.html")

@app.route("/about")
def about():
    if "user" not in session:
        return redirect("/login")

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT * FROM facilities")
    facilities = cur.fetchall()
    conn.close()

    return render_template("about.html", facilities=facilities)
@app.route("/patients", methods=["GET","POST"])
def patients():
    if request.method == "POST":
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        # 🔥 نجيب أكبر ترتيب موجود
        cursor.execute("SELECT MAX(excel_order) FROM patients")
        max_order = cursor.fetchone()[0] or 0

        new_order = max_order + 1

        cursor.execute("""
        INSERT INTO patients
        (num,nom,sexe,age,adresse,gde_consultation,date,cas,excel_order)
        VALUES (?,?,?,?,?,?,?,?,?)
        """,(
            request.form["num"],
            request.form["nom"],
            request.form["sexe"],
            request.form["age"],
            request.form["adresse"],
            request.form["gde_consultation"],
            request.form.get("date") or date.today().isoformat(),
            request.form["cas"],
            new_order   # ✅ هنا الحل
        ))

        conn.commit()
        conn.close()
        return redirect("/patients")
    return render_template("patients.html")

@app.route('/patients_list', methods=['GET','POST'])
def patients_list():
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    if request.method == 'POST':
        file = request.files.get('excel_file')
        if file:
            path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(path)
            process_excel(path)

    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    sort = request.args.get("sort", "desc")

    per_page = 10

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # ================= COUNT =================
    if search:
        cursor.execute("""
            SELECT COUNT(*) FROM patients
            WHERE nom LIKE ? OR num LIKE ? OR sexe LIKE ? OR adresse LIKE ?
        """, (f"%{search}%", f"%{search}%", f"%{search}%", f"%{search}%"))
    else:
        cursor.execute("SELECT COUNT(*) FROM patients")

    total = cursor.fetchone()[0]

    offset = (page - 1) * per_page

    # ================= DATA =================
    if search:
        cursor.execute("""
            SELECT * FROM patients
            WHERE nom LIKE ? OR num LIKE ? OR sexe LIKE ? OR adresse LIKE ?
            ORDER BY rowid ASC
            LIMIT ? OFFSET ?
        """, (f"%{search}%", f"%{search}%", f"%{search}%", f"%{search}%", per_page, offset))
    else:
        cursor.execute("""
            SELECT * FROM patients
            ORDER BY excel_order ASC
            LIMIT ? OFFSET ?
        """, (per_page, offset))

    patients = cursor.fetchall()

    conn.close()

    total_pages = max(1, (total + per_page - 1) // per_page)

    return render_template(
        "patients_list.html",
        patients=patients,
        page=page,
        total_pages=total_pages,
        search=search,
        sort=sort
    )
    
@app.route('/search_patients_global')
def search_patients_global():
    import sqlite3
    from flask import request, jsonify

    conn = sqlite3.connect('patients.db')
    conn.row_factory = sqlite3.Row

    term = request.args.get('term', '')
    sort = request.args.get('sort', 'asc')
    page = int(request.args.get('page', 1))

    term_like = f"%{term}%"

    query = """
    SELECT * FROM patients
    WHERE 
        nom LIKE ? OR
        num LIKE ? OR
        adresse LIKE ? OR
        gde_consultation LIKE ?
    """

    params = [term_like] * 4

    # 🔥 الترتيب الصحيح
    if sort == "desc":
        query += " ORDER BY date DESC, id DESC"
    else:
        query += " ORDER BY date ASC, id ASC"

    offset = (page - 1) * 10
    query += " LIMIT 10 OFFSET ?"
    params.append(offset)

    data = conn.execute(query, params).fetchall()

    total = conn.execute("""
        SELECT COUNT(*) FROM patients
        WHERE 
            nom LIKE ? OR
            num LIKE ? OR
            adresse LIKE ? OR
            gde_consultation LIKE ?
    """, [term_like]*4).fetchone()[0]

    conn.close()

    return jsonify({
        "data": [dict(row) for row in data],
        "total": total
    })

@app.route("/search_patients")
def search_patients():
    term = request.args.get("term","")

    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT nom,sexe,age,adresse 
        FROM patients
        WHERE nom LIKE ?
        LIMIT 10
    """, ('%' + term + '%',))

    rows = cursor.fetchall()
    conn.close()

    patients = []
    for row in rows:
        patients.append({
            "nom": row["nom"],
            "sexe": row["sexe"],
            "age": row["age"],
            "adresse": row["adresse"]
        })

    return jsonify(patients)

@app.route('/update_cell', methods=['POST'])
def update_cell():
    import sqlite3
    from flask import request, jsonify

    data = request.get_json()

    columns = {
        0: 'num',
        1: 'nom',
        2: 'sexe',
        3: 'age',
        4: 'adresse',
        5: 'gde_consultation',
        6: 'date',
        7: 'cas'
    }

    col = columns.get(data['column'])

    if not col:
        return jsonify({'error': 'invalid column'}), 400

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute(f"UPDATE patients SET {col}=? WHERE id=?",
                   (data['value'], data['id']))

    conn.commit()
    conn.close()

    return jsonify({'success': True})
    
@app.route('/delete_patient', methods=['POST'])
def delete_patient():
    data = request.get_json()

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("DELETE FROM patients WHERE id=?", (data['id'],))

    conn.commit()
    conn.close()

    return jsonify({'success': True})

@app.route("/change_password", methods=["GET", "POST"])
def change_password():
    if "user" not in session:
        return redirect("/login")

    return render_template("change_password.html")
@app.route("/statistiques")
def statistiques():

    if "user" not in session:
        return redirect("/login")

    date = request.args.get("date","")
    sexe = request.args.get("sexe","")
    adresse = request.args.get("adresse","")
    age = request.args.get("age","")
    gdc = request.args.get("gdc","")
    mois = request.args.get("mois","")
    annee = request.args.get("annee","")

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    query = """
    SELECT 
        gde_consultation,
        COUNT(*) as total,
        SUM(CASE WHEN sexe='M' THEN 1 ELSE 0 END) as homme,
        SUM(CASE WHEN sexe='F' THEN 1 ELSE 0 END) as femme
    FROM patients
    WHERE (date LIKE ? OR ?='')
    AND (sexe LIKE ? OR ?='')
    AND (adresse LIKE ? OR ?='')
    AND (age LIKE ? OR ?='')
    AND (gde_consultation LIKE ? OR ?='')
    AND (strftime('%m', date)=? OR ?='')
    AND (strftime('%Y', date)=? OR ?='')
    GROUP BY gde_consultation
    """

    params = [
        f"%{date}%", date,
        f"%{sexe}%", sexe,
        f"%{adresse}%", adresse,
        f"%{age}%", age,
        f"%{gdc}%", gdc,
        mois.zfill(2) if mois else "", mois,
        annee, annee
    ]

    cursor.execute(query, params)
    rows = cursor.fetchall()

    stats = []
    max_total = 0
    total_homme = 0
    total_femme = 0

    for r in rows:
        stats.append({
            "gdc": r[0],
            "total": r[1],
            "homme": r[2],
            "femme": r[3]
        })
        max_total = max(max_total, r[1])
        total_homme += r[2]
        total_femme += r[3]

    cursor.execute("SELECT DISTINCT gde_consultation FROM patients")
    gdc_list = [x[0] for x in cursor.fetchall()]

    conn.close()

    return render_template(
        "statistiques.html",
        stats=stats,
        max_total=max_total,
        total_homme=total_homme,
        total_femme=total_femme,
        gdc_list=gdc_list
    )

@app.route("/logout")
def logout():

    if "login_id" in session:

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE login_history
            SET logout_time = datetime('now','localtime')
            WHERE id = ?
        """, (session["login_id"],))

        conn.commit()
        conn.close()

    session.clear()
    return redirect("/login")
# ================== USERS ==================
@app.route("/users", methods=["GET", "POST"])
def users():

    if "user" not in session:
        return redirect("/login")

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # ADD USER
    if request.method == "POST":
        cursor.execute("""
            INSERT INTO users (username, password, role)
            VALUES (?, ?, ?)
        """, (
            request.form["username"],
            request.form["password"],
            request.form.get("role", "user")
        ))
        conn.commit()

    users = cursor.execute("SELECT * FROM users").fetchall()

    # 🟢 ONLINE USERS (آخر session فقط لكل مستخدم)
    online_users = cursor.execute("""
        SELECT lh.username, lh.login_time, lh.ip
        FROM login_history lh
        INNER JOIN (
            SELECT username, MAX(id) AS max_id
            FROM login_history
            GROUP BY username
        ) last
        ON lh.id = last.max_id
        WHERE lh.logout_time IS NULL
    """).fetchall()

    # 📌 HISTORY (آخر 5)
    history = cursor.execute("""
        SELECT username, login_time, logout_time, ip
        FROM login_history
        ORDER BY login_time DESC
        LIMIT 5
    """).fetchall()

    conn.close()

    return render_template(
        "users.html",
        users=users,
        history=history,
        online_users=online_users
    )
# ================== ONLINE USERS API ==================
@app.route("/online_users")
def get_online_users():

    if "user" not in session:
        return jsonify([])

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    users = cursor.execute("""
        SELECT username, login_time, ip
        FROM login_history
        WHERE logout_time IS NULL
        ORDER BY login_time DESC
    """).fetchall()

    conn.close()

    return jsonify([
        {
            "username": u[0],
            "login_time": u[1],
            "ip": u[2]
        }
        for u in users
    ])

@app.route("/delete_user/<int:id>")
def delete_user(id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("DELETE FROM users WHERE id=?", (id,))
    conn.commit()
    conn.close()

    return ("ok", 200)

# ---------------- STAFF PAGE ----------------
# 🟢 ADD STAFF (AJAX)
@app.route("/staff")
def staff():
    if "user" not in session:
        return redirect("/login")

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT * FROM staff")
    staff = cur.fetchall()
    conn.close()

    return render_template("staff.html", staff=staff)


@app.route("/add_staff", methods=["POST"])
def add_staff():
    name = request.form.get("name")
    role = request.form.get("role")

    icon = get_icon(role)

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("INSERT INTO staff(name, role, icon) VALUES (?,?,?)", (name, role, icon))
    conn.commit()
    conn.close()

    return jsonify({"name": name, "role": role, "icon": icon})


@app.route("/update_staff", methods=["POST"])
def update_staff():
    staff_id = request.form.get("id")
    name = request.form.get("name")
    role = request.form.get("role")

    icon = get_icon(role)

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        UPDATE staff
        SET name=?, role=?, icon=?
        WHERE id=?
    """, (name, role, icon, staff_id))

    conn.commit()
    conn.close()

    return jsonify({"ok": True, "icon": icon})


@app.route("/delete_staff/<int:id>")
def delete_staff(id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("DELETE FROM staff WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})
    
@app.route("/rapports")
def rapports():

    if "user" not in session:
        return redirect("/login")

    mois = request.args.get("mois", "")
    annee = request.args.get("annee", "")
    sexe = request.args.get("sexe", "")
    numero = request.args.get("numero", "")
    adresse = request.args.get("adresse", "")

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    query = """
    SELECT num, nom, sexe, age, adresse, gde_consultation, date, cas
    FROM patients
    WHERE 1=1
    """

    params = []

    if numero:
        query += " AND (num LIKE ? OR gde_consultation LIKE ?)"
        params += [f"%{numero}%", f"%{numero}%"]

    if sexe:
        query += " AND sexe = ?"
        params.append(sexe)

    if adresse:
        query += " AND adresse LIKE ?"
        params.append(f"%{adresse}%")

    if mois:
        query += " AND strftime('%m', date) = ?"
        params.append(mois.zfill(2))

    if annee:
        query += " AND strftime('%Y', date) = ?"
        params.append(annee)

    cursor.execute(query, params)
    patients = cursor.fetchall()

    total = len(patients)
    hommes = len([p for p in patients if p[2] == "M"])
    femmes = len([p for p in patients if p[2] == "F"])

    cursor.execute("SELECT DISTINCT strftime('%Y', date) FROM patients ORDER BY 1 DESC")
    annees = sorted(set(int(a[0]) for a in cursor.fetchall() if a[0]))

    conn.close()

    # 🔥 حفظ الفلاتر لاستعمالها في PDF
    session["last_filters"] = {
        "mois": mois,
        "annee": annee,
        "sexe": sexe,
        "numero": numero,
        "adresse": adresse
    }

    return render_template(
        "rapports.html",
        patients=patients,
        mois=mois,
        annee=annee,
        sexe=sexe,
        numero=numero,
        adresse=adresse,
        total=total,
        hommes=hommes,
        femmes=femmes,
        annees=annees
    )
@app.route("/export_pdf")
def export_pdf():

    import datetime
    from fpdf import FPDF
    from flask import send_file, request
    import sqlite3
    from io import BytesIO

    mois = request.args.get("mois", "")
    annee = request.args.get("annee", "")
    sexe = request.args.get("sexe", "")
    numero = request.args.get("numero", "")
    adresse = request.args.get("adresse", "")

    # 🔥 إذا ماوصلاتش الفلاتر من الرابط ناخذوها من الصفحة
    if not (mois or annee or sexe or numero or adresse):
        saved = session.get("last_filters", {})
        mois = saved.get("mois", "")
        annee = saved.get("annee", "")
        sexe = saved.get("sexe", "")
        numero = saved.get("numero", "")
        adresse = saved.get("adresse", "")

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    query = """
    SELECT num, nom, sexe, age, adresse, gde_consultation, date, cas
    FROM patients
    WHERE 1=1
    """

    params = []

    if numero:
        query += " AND (num LIKE ? OR gde_consultation LIKE ?)"
        params += [f"%{numero}%", f"%{numero}%"]

    if sexe:
        query += " AND sexe = ?"
        params.append(sexe)

    if adresse:
        query += " AND adresse LIKE ?"
        params.append(f"%{adresse}%")

    if mois:
        query += " AND strftime('%m', date) = ?"
        params.append(mois.zfill(2))

    if annee:
        query += " AND strftime('%Y', date) = ?"
        params.append(annee)

    cursor.execute(query, params)
    data = cursor.fetchall()
    conn.close()

    class PDF(FPDF):

        def header(self):
            try:
                self.image("static/logo.png", x=58, y=3, w=180)
            except:
                pass

            self.ln(35)

            self.set_font("Helvetica", "B", 14)
            self.cell(0, 10, "RAPPORT DES PATIENTS", 0, 1, "C")
            self.ln(5)

        def footer(self):
            self.set_y(-20)
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

            self.set_font("Helvetica", "", 8)
            self.cell(0, 5, f"Page {self.page_no()} / {{nb}}", align="L")
            self.ln(4)

            self.cell(
                0,
                5,
                f"ETABLI PAR : Agent de Saisie --- Lahcen ID-HAMMAME ---   {now}",
                align="C"
            )

    pdf = PDF(orientation='L', unit='mm', format='A4')
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=25)
    pdf.add_page()

    headers = ["N°", "Nom", "Sexe", "Age", "Adresse", "Gent de Consultation", "Date", "Cas"]
    col_widths = [18, 40, 18, 15, 60, 45, 35, 35]

    pdf.set_font("Helvetica", "B", 8)

    for i, h in enumerate(headers):
        pdf.cell(col_widths[i], 8, h, border=1, align="C")
    pdf.ln()

    pdf.set_font("Helvetica", "", 7)

    if not data:
        pdf.cell(0, 10, "Aucune donnée trouvée", border=1, ln=True, align="C")
    else:
        for row in data:
            for i, item in enumerate(row):
                if i == 6 and item:
                    item = str(item)[:10]
                pdf.cell(col_widths[i], 7, str(item), border=1, align="C")
            pdf.ln()

    pdf_bytes = pdf.output()
    buffer = BytesIO(pdf_bytes)
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="rapport_patients.pdf",
        mimetype="application/pdf"
    )

@app.route("/appointments", methods=["GET","POST"])
def appointments():

    if "user" not in session:
        return redirect("/login")

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS rendezvous(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT,
    nom TEXT,
    date TEXT,
    heure TEXT,
    motif TEXT
    )
    """)

    if request.method == "POST":
        type_rdv = request.form["type"]
        nom = request.form["nom"]
        date = request.form["date"]
        heure = request.form["heure"]
        motif = request.form["motif"]

        cursor.execute(
        "INSERT INTO rendezvous(type,nom,date,heure,motif) VALUES (?,?,?,?,?)",
        (type_rdv,nom,date,heure,motif)
        )
        conn.commit()

    cursor.execute("SELECT * FROM rendezvous ORDER BY date,heure")
    rendezvous = cursor.fetchall()
    conn.close()

    return render_template("appointments.html", rendezvous=rendezvous)

@app.route("/delete_rdv/<int:id>")
def delete_rdv(id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("DELETE FROM rendezvous WHERE id=?", (id,))
    
    conn.commit()
    conn.close()

    return redirect("/appointments")

  # ================== PHARMACY ==================
@app.route("/pharmacy", methods=["GET","POST"])
def pharmacy():
    if "user" not in session:
        return redirect("/login")

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pharmacie(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT,
        quantite INTEGER,
        expiration TEXT
    )
    """)

    if request.method == "POST":
        nom = request.form["nom"]
        quantite = request.form["quantite"]
        expiration = request.form["expiration"]

        cursor.execute(
            "INSERT INTO pharmacie(nom,quantite,expiration) VALUES (?,?,?)",
            (nom, quantite, expiration)
        )
        conn.commit()

    cursor.execute("SELECT * FROM pharmacie")
    medicaments = cursor.fetchall()
    conn.close()

    return render_template(
        "pharmacy.html",
        medicaments=medicaments,
        today=str(date.today())
    )


# ================== DELETE MED ==================
@app.route("/delete_med/<int:id>")
def delete_med(id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM pharmacie WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect("/pharmacy")


# ================== INFO ==================
@app.route("/info", methods=["GET","POST"])
def info():

    if "user" not in session:
        return redirect("/login")

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # جدول المعلومات
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS infos(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        titre TEXT,
        message TEXT,
        date TEXT
    )
    """)

    # جدول معلومات الاتصال
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS contact_info(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phone TEXT,
        email TEXT,
        hours TEXT
    )
    """)

    # إدخال افتراضي إذا فارغ
    cursor.execute("SELECT COUNT(*) FROM contact_info")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
        INSERT INTO contact_info(phone,email,hours)
        VALUES('+212 000000000','centre@email.com','08:30 - 16:30')
        """)
        conn.commit()

    # إضافة معلومة
    if request.method == "POST":
        titre = request.form["titre"]
        message = request.form["message"]
        date_info = datetime.now().strftime("%d-%m-%Y")

        cursor.execute(
            "INSERT INTO infos(titre,message,date) VALUES (?,?,?)",
            (titre, message, date_info)
        )
        conn.commit()

    # جلب infos
    cursor.execute("SELECT * FROM infos ORDER BY id DESC")
    infos = cursor.fetchall()

    # جلب contact
    cursor.execute("SELECT phone,email,hours FROM contact_info WHERE id=1")
    contact = cursor.fetchone()

    conn.close()

    return render_template(
        "info.html",
        infos=infos,
        contact=contact
    )

# ================== DELETE INFO ==================
@app.route("/delete_info/<int:id>")
def delete_info(id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM infos WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect("/info")

# ================== UPDATE CONTACT ==================
@app.route("/update_contact_info", methods=["POST"])
def update_contact_info():

    phone = request.form["phone"]
    email = request.form["email"]
    hours = request.form["hours"]

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE contact_info
    SET phone=?, email=?, hours=?
    WHERE id=1
    """, (phone, email, hours))

    conn.commit()
    conn.close()

    return redirect("/info")

# ================== UPLOAD CAMPAIGN ==================
@app.route("/upload_campaign", methods=["POST"])
def upload_campaign():

    if "user" not in session:
        return redirect("/login")

    file = request.files.get("image")
    title = request.form.get("title")
    category = request.form.get("category")

    if not file or file.filename == "":
        return redirect("/campaigns")

    filename = secure_filename(file.filename)
    file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO campaigns(image, title, category)
    VALUES (?, ?, ?)
    """, (filename, title, category))

    conn.commit()
    conn.close()

    return redirect("/campaigns")

# ================== CAMPAIGNS ==================
@app.route("/campaigns")
def campaigns():

    if "user" not in session:
        return redirect("/login")

    page = request.args.get("page", 1, type=int)
    per_page = 8
    category = request.args.get("category", "all")

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # ================= CREATE TABLE =================
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS campaigns(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        image TEXT,
        title TEXT,
        category TEXT
    )
    """)

    # ================= FILTER DATA FIRST =================
    if category == "all":
        cursor.execute("""
        SELECT id, image, title, category
        FROM campaigns
        ORDER BY id DESC
        """)
        all_data = cursor.fetchall()

    else:
        cursor.execute("""
        SELECT id, image, title, category
        FROM campaigns
        WHERE category=?
        ORDER BY id DESC
        """, (category,))
        all_data = cursor.fetchall()

    conn.close()

    # ================= PYTHON PAGINATION (SAFE) =================
    total = len(all_data)
    total_pages = max(1, (total + per_page - 1) // per_page)

    if page < 1:
        page = 1
    if page > total_pages:
        page = total_pages

    start = (page - 1) * per_page
    end = start + per_page

    images = all_data[start:end]

    return render_template(
        "campaigns.html",
        images=images,
        page=page,
        total_pages=total_pages,
        category=category
    )


# ================= DELETE CAMPAIGN (FIXED) =================
@app.route("/delete_campaign/<int:id>")
def delete_campaign(id):

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("SELECT image FROM campaigns WHERE id=?", (id,))
    row = cursor.fetchone()

    if row:
        path = os.path.join(app.config["UPLOAD_FOLDER"], row[0])
        if os.path.exists(path):
            os.remove(path)

    cursor.execute("DELETE FROM campaigns WHERE id=?", (id,))
    conn.commit()
    conn.close()

    return jsonify({"success": True})

@app.route("/notifications")
def notifications():
    data = get_notifications()
    return jsonify(data)
@app.route("/mark_notification/<int:id>")
def mark_notification(id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
        UPDATE rendezvous
        SET notification_sent = 1
        WHERE id=?
    """, (id,))

    conn.commit()
    conn.close()

    return jsonify({"ok": True})
@app.route('/delete_all_patients')
def delete_all_patients():
    import sqlite3
    conn = sqlite3.connect('patients.db')
    conn.execute("DELETE FROM patients")
    conn.commit()
    conn.close()
    return "تم حذف جميع المرضى"
    
# ================== RUN ==================
if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)