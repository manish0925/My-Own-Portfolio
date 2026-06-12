from flask import Flask, render_template, request, redirect, session, url_for, flash
from flask_mail import Mail, Message
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
import os
import secrets
import time

load_dotenv()
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "secret123")

# ---------------- MAIL CONFIG ----------------
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_USERNAME')
app.config['ADMIN_RESET_TOKEN_EXPIRY'] = 3600

mail = Mail(app)

# ---------------- DATABASE CONFIG ----------------
database_url = os.environ.get('DATABASE_URL', 'sqlite:///database.db')

if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ---------------- MODELS ----------------
class Project(db.Model):
    __tablename__ = 'projects'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    desc = db.Column(db.Text, nullable=False)

class Skill(db.Model):
    __tablename__ = 'skills'
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(200), nullable=False)
    items = db.Column(db.Text, nullable=False)

class Experience(db.Model):
    __tablename__ = 'experience'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    company = db.Column(db.String(200), nullable=False)
    period = db.Column(db.String(100), nullable=False)
    desc = db.Column(db.Text, nullable=False)

class ContactInfo(db.Model):
    __tablename__ = 'contact_info'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(200))
    phone = db.Column(db.String(50))
    location = db.Column(db.String(200))
    linkedin = db.Column(db.String(300))

# ✅ Email column included
class AdminUser(db.Model):
    __tablename__ = 'admin_users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(200), nullable=True)
    password = db.Column(db.String(300), nullable=False)
    reset_token = db.Column(db.String(100))
    reset_token_expiry = db.Column(db.BigInteger)

# ---------------- INIT DATABASE ----------------
def init_db():
    with app.app_context():

        # ✅ MIGRATION: Pehle missing columns add karo
        try:
            with db.engine.connect() as conn:
                result = conn.execute(db.text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name='admin_users' 
                    AND column_name='email'
                """))
                if not result.fetchone():
                    conn.execute(db.text(
                        "ALTER TABLE admin_users ADD COLUMN email VARCHAR(200)"
                    ))
                    conn.commit()
                    print("[MIGRATION] email column added to admin_users table")
                else:
                    print("[MIGRATION] email column already exists - OK")
        except Exception as e:
            print(f"[MIGRATION ERROR] {e}")

        # Tables banao
        db.create_all()

        # Default skills
        if not Skill.query.first():
            default_skills = [
                Skill(
                    category="Data Analytics",
                    items="Python (Pandas, NumPy, Matplotlib), SQL, PostgreSQL, MySQL, Statistical analysis and forecasting"
                ),
                Skill(
                    category="Business Intelligence",
                    items="Power BI and interactive dashboards, Data storytelling for stakeholders, Performance tracking and KPI design"
                ),
                Skill(
                    category="Automation & Tools",
                    items="ETL pipeline automation, Excel, VBA, and reporting tools, Git, Jupyter, and collaboration workflows"
                ),
            ]
            db.session.bulk_save_objects(default_skills)

        # Default experience
        if not Experience.query.first():
            default_exp = [
                Experience(
                    title="Data Analyst",
                    company="Company Name",
                    period="2022 to present",
                    desc="Developed dashboards and automated reports for business units."
                ),
                Experience(
                    title="Junior Analyst",
                    company="Company Name",
                    period="2020 to 2022",
                    desc="Delivered SQL-based insights and forecasting models."
                ),
            ]
            db.session.bulk_save_objects(default_exp)

        # Default contact
        if not ContactInfo.query.first():
            default_contact = ContactInfo(
                email="manishkumar96963172@gmail.com",
                phone="+91 9696317234",
                location="India",
                linkedin="https://www.linkedin.com/in/manish-kumar-568a392a8/"
            )
            db.session.add(default_contact)

        # Default admin
        if not AdminUser.query.first():
            default_admin = AdminUser(
                username="admin",
                email=os.getenv('MAIL_USERNAME'),
                password=generate_password_hash("1234")
            )
            db.session.add(default_admin)
        else:
            # Existing admin ka email update karo agar missing hai
            existing_admin = AdminUser.query.filter_by(username="admin").first()
            if existing_admin and not existing_admin.email:
                existing_admin.email = os.getenv('MAIL_USERNAME')
                print(f"[UPDATE] Admin email updated: {existing_admin.email}")

        db.session.commit()
        print("[DB] Database ready!")

init_db()

# ---------------- HOME ----------------
@app.route("/")
def home():
    project_count = Project.query.count()
    stats = {"projects": project_count}
    return render_template("home.html", stats=stats)

# ---------------- SKILLS ----------------
@app.route("/skills")
def skills():
    skills_data = Skill.query.order_by(Skill.id).all()
    return render_template("skills.html", skills=skills_data)

# ---------------- PROJECTS ----------------
@app.route("/projects")
def projects():
    data = Project.query.order_by(Project.id.desc()).all()
    return render_template("projects.html", projects=data)

# ---------------- CONTACT ----------------
@app.route("/contact", methods=["GET", "POST"])
def contact():
    contact_data = ContactInfo.query.first()

    if request.method == "POST":
        name = request.form.get("name", "Visitor").strip()
        email = request.form.get("email", "").strip()
        msg_body = request.form.get("message", "").strip()

        if not email or not msg_body:
            flash("Please provide both an email and a message.", "error")
            return render_template("contact.html", contact=contact_data)

        admin_email = app.config.get("MAIL_USERNAME")
        if not admin_email:
            flash("Mail configuration error. Please try again later.", "error")
            return render_template("contact.html", contact=contact_data)

        try:
            msg = Message(
                subject=f"Portfolio Contact: Message from {name}",
                sender=app.config.get("MAIL_DEFAULT_SENDER"),
                recipients=[admin_email],
                body=f"Name: {name}\nEmail: {email}\n\nMessage:\n{msg_body}"
            )
            msg.reply_to = email
            mail.send(msg)
            flash("Your message was sent successfully!", "success")
        except Exception as e:
            print(f"[MAIL ERROR - Contact]: {e}")
            flash("Error sending message. Please try again later.", "error")

    return render_template("contact.html", contact=contact_data)

# ---------------- RESUME ----------------
@app.route("/resume")
def resume():
    experience = Experience.query.order_by(Experience.id.desc()).all()
    return render_template("resume.html", experience=experience)

# ================= ADMIN =================

@app.route("/admin", methods=["GET", "POST"])
def admin():
    if "admin" in session:
        return redirect("/dashboard")

    error = None
    if request.method == "POST":
        user = request.form.get("username", "").strip()
        pwd = request.form.get("password", "").strip()

        if not user or not pwd:
            error = "Please enter both username and password."
        else:
            admin_user = AdminUser.query.filter_by(username=user).first()
            if admin_user and check_password_hash(admin_user.password, pwd):
                session["admin"] = True
                session["admin_username"] = admin_user.username
                return redirect("/dashboard")
            error = "Invalid username or password."

    return render_template("admin_login.html", error=error)

@app.route("/dashboard")
def dashboard():
    if "admin" not in session:
        return redirect("/admin")

    all_projects = Project.query.order_by(Project.id.desc()).all()
    all_skills = Skill.query.order_by(Skill.id).all()
    all_experience = Experience.query.order_by(Experience.id.desc()).all()
    contact = ContactInfo.query.first()
    admin_user = AdminUser.query.filter_by(username="admin").first()

    return render_template(
        "admin_dashboard.html",
        projects=all_projects,
        skills=all_skills,
        experience=all_experience,
        contact=contact,
        admin_email=admin_user.email if admin_user else ""
    )

@app.route("/change_password", methods=["GET", "POST"])
def change_password():
    if "admin" not in session:
        return redirect("/admin")

    error = None
    if request.method == "POST":
        current_password = request.form.get("current_password", "").strip()
        new_password = request.form.get("new_password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()

        if not current_password or not new_password or not confirm_password:
            error = "Please fill in all fields."
        elif len(new_password) < 6:
            error = "New password must be at least 6 characters."
        elif new_password != confirm_password:
            error = "New passwords do not match."
        else:
            admin_user = AdminUser.query.filter_by(username="admin").first()
            if not admin_user or not check_password_hash(admin_user.password, current_password):
                error = "Current password is incorrect."
            else:
                admin_user.password = generate_password_hash(new_password)
                db.session.commit()
                flash("Password updated successfully.", "success")
                return redirect("/dashboard")

    return render_template("change_password.html", error=error)

@app.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    message = None
    message_type = "info"

    if request.method == "POST":
        email = request.form.get("email", "").strip()

        if not email:
            message = "Please enter your email address."
            message_type = "error"
        else:
            # ✅ Database mein email se dhundo
            admin_user = AdminUser.query.filter_by(email=email).first()
            message = "If the email exists, a reset link has been sent."
            message_type = "success"

            if admin_user:
                token = secrets.token_urlsafe(32)
                expiry = int(time.time()) + app.config['ADMIN_RESET_TOKEN_EXPIRY']

                admin_user.reset_token = token
                admin_user.reset_token_expiry = expiry
                db.session.commit()

                reset_url = url_for("reset_password", token=token, _external=True)

                try:
                    msg = Message(
                        subject="Admin Password Reset - Portfolio",
                        sender=app.config.get("MAIL_DEFAULT_SENDER"),
                        recipients=[email],
                        body=(
                            f"Hello,\n\n"
                            f"Password reset link:\n{reset_url}\n\n"
                            f"This link expires in 1 hour.\n\n"
                            f"If you did not request this, ignore this email."
                        )
                    )
                    mail.send(msg)
                    print(f"[INFO] Reset email sent to: {email}")
                except Exception as e:
                    print(f"[MAIL ERROR - Forgot Password]: {e}")
                    message = "Unable to send reset email. Check mail configuration."
                    message_type = "error"
                    admin_user.reset_token = None
                    admin_user.reset_token_expiry = None
                    db.session.commit()

    return render_template("forgot_password.html",
                           message=message,
                           message_type=message_type)

@app.route("/reset_password/<token>", methods=["GET", "POST"])
def reset_password(token):
    error = None
    current_time = int(time.time())

    admin_user = AdminUser.query.filter(
        AdminUser.reset_token == token,
        AdminUser.reset_token_expiry > current_time
    ).first()

    if not admin_user:
        return render_template(
            "reset_password.html",
            error="Invalid or expired reset link. Please request a new one.",
            token=None
        )

    if request.method == "POST":
        new_password = request.form.get("new_password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()

        if not new_password or not confirm_password:
            error = "Please fill in all fields."
        elif len(new_password) < 6:
            error = "Password must be at least 6 characters."
        elif new_password != confirm_password:
            error = "Passwords do not match."
        else:
            admin_user.password = generate_password_hash(new_password)
            admin_user.reset_token = None
            admin_user.reset_token_expiry = None
            db.session.commit()
            flash("Password reset successful. Please login.", "success")
            return redirect("/admin")

    return render_template("reset_password.html", error=error, token=token)

@app.route("/add_project", methods=["GET", "POST"])
def add_project():
    if "admin" not in session:
        return redirect("/admin")

    error = None
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        desc = request.form.get("desc", "").strip()

        if not title or not desc:
            error = "Please provide both title and description."
        else:
            db.session.add(Project(title=title, desc=desc))
            db.session.commit()
            flash("Project added successfully.", "success")
            return redirect("/dashboard")

    return render_template("add_project.html", error=error)

@app.route("/delete_project/<int:project_id>", methods=["POST"])
def delete_project(project_id):
    if "admin" not in session:
        return redirect("/admin")
    project = Project.query.get_or_404(project_id)
    db.session.delete(project)
    db.session.commit()
    flash("Project deleted.", "success")
    return redirect("/dashboard")

@app.route("/edit_project/<int:project_id>", methods=["GET", "POST"])
def edit_project(project_id):
    if "admin" not in session:
        return redirect("/admin")

    project = Project.query.get_or_404(project_id)
    error = None

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        desc = request.form.get("desc", "").strip()
        if not title or not desc:
            error = "Please provide both title and description."
        else:
            project.title = title
            project.desc = desc
            db.session.commit()
            flash("Project updated.", "success")
            return redirect("/dashboard")

    return render_template("edit_project.html", project=project, error=error)

@app.route("/edit_skills", methods=["GET", "POST"])
def edit_skills():
    if "admin" not in session:
        return redirect("/admin")

    if request.method == "POST":
        categories = request.form.getlist("category")
        items_list = request.form.getlist("items")
        Skill.query.delete()
        for cat, it in zip(categories, items_list):
            if cat.strip() and it.strip():
                db.session.add(Skill(category=cat.strip(), items=it.strip()))
        db.session.commit()
        flash("Skills updated.", "success")
        return redirect("/dashboard")

    all_skills = Skill.query.order_by(Skill.id).all()
    return render_template("edit_skills.html", skills=all_skills)

@app.route("/edit_experience", methods=["GET", "POST"])
def edit_experience():
    if "admin" not in session:
        return redirect("/admin")

    if request.method == "POST":
        titles = request.form.getlist("title")
        companies = request.form.getlist("company")
        periods = request.form.getlist("period")
        descs = request.form.getlist("desc")
        Experience.query.delete()
        for t, c, p, d in zip(titles, companies, periods, descs):
            if t.strip() and c.strip():
                db.session.add(Experience(
                    title=t.strip(),
                    company=c.strip(),
                    period=p.strip(),
                    desc=d.strip()
                ))
        db.session.commit()
        flash("Experience updated.", "success")
        return redirect("/dashboard")

    all_experience = Experience.query.order_by(Experience.id.desc()).all()
    return render_template("edit_experience.html", experience=all_experience)

@app.route("/edit_contact", methods=["GET", "POST"])
def edit_contact():
    if "admin" not in session:
        return redirect("/admin")

    if request.method == "POST":
        ContactInfo.query.delete()
        db.session.add(ContactInfo(
            email=request.form.get("email", "").strip(),
            phone=request.form.get("phone", "").strip(),
            location=request.form.get("location", "").strip(),
            linkedin=request.form.get("linkedin", "").strip()
        ))
        db.session.commit()
        flash("Contact info updated.", "success")
        return redirect("/dashboard")

    contact = ContactInfo.query.first()
    return render_template("edit_contact.html", contact=contact)

@app.route("/update_admin_email", methods=["GET", "POST"])
def update_admin_email():
    if "admin" not in session:
        return redirect("/admin")

    error = None
    admin_user = AdminUser.query.filter_by(username="admin").first()

    if request.method == "POST":
        new_email = request.form.get("email", "").strip()
        if not new_email:
            error = "Please enter an email address."
        else:
            admin_user.email = new_email
            db.session.commit()
            flash("Admin email updated successfully.", "success")
            return redirect("/dashboard")

    return render_template("update_admin_email.html",
                           current_email=admin_user.email if admin_user else "",
                           error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)
