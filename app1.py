from flask import Flask, render_template, request, redirect, session, url_for, flash
from flask_mail import Mail, Message
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import text
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
app.config['ADMIN_RESET_TOKEN_EXPIRY'] = 3600  # seconds

mail = Mail(app)

# ---------------- DATABASE CONFIG ----------------
database_url = os.environ.get('DATABASE_URL', 'sqlite:///database.db')

# Render PostgreSQL fix
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

class AdminUser(db.Model):
    __tablename__ = 'admin_users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(300), nullable=False)
    reset_token = db.Column(db.String(100))
    reset_token_expiry = db.Column(db.BigInteger)

# ---------------- INIT DATABASE ----------------
def init_db():
    with app.app_context():
        db.create_all()

        # Insert default skills if empty
        if not Skill.query.first():
            default_skills = [
                Skill(category="Data Analytics", items="Python (Pandas, NumPy, Matplotlib), SQL, PostgreSQL, MySQL, Statistical analysis and forecasting"),
                Skill(category="Business Intelligence", items="Power BI and interactive dashboards, Data storytelling for stakeholders, Performance tracking and KPI design"),
                Skill(category="Automation & Tools", items="ETL pipeline automation, Excel, VBA, and reporting tools, Git, Jupyter, and collaboration workflows"),
            ]
            db.session.bulk_save_objects(default_skills)

        # Insert default experience if empty
        if not Experience.query.first():
            default_exp = [
                Experience(title="Data Analyst", company="Company Name", period="2022 to present",
                           desc="Developed dashboards and automated reports for business units, improving decision-making speed and accuracy."),
                Experience(title="Junior Analyst", company="Company Name", period="2020 to 2022",
                           desc="Delivered SQL-based insights, supported data migrations, and built models for forecasting."),
            ]
            db.session.bulk_save_objects(default_exp)

        # Insert default contact info if empty
        if not ContactInfo.query.first():
            default_contact = ContactInfo(
                email="manish@example.com",
                phone="+91 12345 67890",
                location="India",
                linkedin="https://www.linkedin.com/in/manish"
            )
            db.session.add(default_contact)

        # Insert default admin user if empty
        if not AdminUser.query.first():
            default_admin = AdminUser(
                username="admin",
                password=generate_password_hash("1234")
            )
            db.session.add(default_admin)

        db.session.commit()

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
        name = request.form.get("name", "Visitor")
        email = request.form.get("email")
        msg_body = request.form.get("message")

        if not email or not msg_body:
            flash("Please provide both an email and a message.")
            return render_template("contact.html", contact=contact_data)

        recipients = [app.config.get("MAIL_USERNAME")]

        msg = Message(
            subject=f"New message from {name}",
            sender=app.config.get("MAIL_DEFAULT_SENDER"),
            recipients=recipients,
            body=f"From: {name} <{email}>\n\n{msg_body}"
        )
        msg.reply_to = email

        try:
            mail.send(msg)
            flash("Your message was sent successfully. I will respond soon.")
        except Exception as e:
            print("Mail send error:", e)
            flash("There was an error sending your message. Please try again later.")

    return render_template("contact.html", contact=contact_data)

# ---------------- RESUME ----------------
@app.route("/resume")
def resume():
    experience = Experience.query.order_by(Experience.id.desc()).all()
    return render_template("resume.html", experience=experience)

# ================= ADMIN =================

# LOGIN
@app.route("/admin", methods=["GET", "POST"])
def admin():
    error = None
    if request.method == "POST":
        user = request.form["username"].strip()
        pwd = request.form["password"].strip()

        admin_user = AdminUser.query.filter_by(username=user).first()

        if admin_user and check_password_hash(admin_user.password, pwd):
            session["admin"] = True
            return redirect("/dashboard")

        error = "Invalid username or password."

    return render_template("admin_login.html", error=error)

# DASHBOARD
@app.route("/dashboard")
def dashboard():
    if "admin" not in session:
        return redirect("/admin")

    projects = Project.query.order_by(Project.id.desc()).all()
    skills = Skill.query.order_by(Skill.id).all()
    experience = Experience.query.order_by(Experience.id.desc()).all()
    contact = ContactInfo.query.first()

    return render_template("admin_dashboard.html", projects=projects, skills=skills, experience=experience, contact=contact)

# CHANGE PASSWORD
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
        elif new_password != confirm_password:
            error = "New passwords do not match."
        else:
            admin_user = AdminUser.query.filter_by(username="admin").first()
            if not admin_user or not check_password_hash(admin_user.password, current_password):
                error = "Current password is incorrect."
            else:
                admin_user.password = generate_password_hash(new_password)
                db.session.commit()
                flash("Password updated successfully.")
                return redirect("/dashboard")

    return render_template("change_password.html", error=error)

# FORGOT PASSWORD
@app.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    message = None
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        if not email:
            message = "Please enter your email address."
        else:
            token = secrets.token_urlsafe(16)
            expiry = int(time.time()) + app.config['ADMIN_RESET_TOKEN_EXPIRY']

            if email == app.config.get("MAIL_USERNAME"):
                admin_user = AdminUser.query.filter_by(username="admin").first()
                if admin_user:
                    admin_user.reset_token = token
                    admin_user.reset_token_expiry = expiry
                    db.session.commit()

                    reset_url = url_for("reset_password", token=token, _external=True)
                    msg = Message(
                        subject="Admin Password Reset",
                        sender=app.config.get("MAIL_DEFAULT_SENDER"),
                        recipients=[email],
                        body=f"Use this link to reset your admin password:\n\n{reset_url}\n\nIf you did not request this, ignore this message."
                    )
                    try:
                        mail.send(msg)
                        message = "If the email exists, a reset link has been sent."
                    except Exception as e:
                        print("Forgot password mail error:", e)
                        message = "Unable to send reset email. Please try again later."
            else:
                message = "If the email exists, a reset link has been sent."

    return render_template("forgot_password.html", message=message)

# RESET PASSWORD
@app.route("/reset_password/<token>", methods=["GET", "POST"])
def reset_password(token):
    error = None
    current_time = int(time.time())

    admin_user = AdminUser.query.filter(
        AdminUser.reset_token == token,
        AdminUser.reset_token_expiry > current_time
    ).first()

    if not admin_user:
        return render_template("reset_password.html", error="Invalid or expired reset link.", token=None)

    if request.method == "POST":
        new_password = request.form.get("new_password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()
        if not new_password or not confirm_password:
            error = "Please fill in all fields."
        elif new_password != confirm_password:
            error = "Passwords do not match."
        else:
            admin_user.password = generate_password_hash(new_password)
            admin_user.reset_token = None
            admin_user.reset_token_expiry = None
            db.session.commit()
            flash("Your password has been reset successfully.")
            return redirect("/admin")

    return render_template("reset_password.html", error=error, token=token)

# ADD PROJECT
@app.route("/add_project", methods=["GET", "POST"])
def add_project():
    if "admin" not in session:
        return redirect("/admin")

    error = None
    if request.method == "POST":
        title = request.form["title"].strip()
        desc = request.form["desc"].strip()

        if not title or not desc:
            error = "Please provide both title and description."
        else:
            new_project = Project(title=title, desc=desc)
            db.session.add(new_project)
            db.session.commit()
            flash("Project added successfully.")
            return redirect("/dashboard")

    return render_template("add_project.html", error=error)

# EDIT SKILLS
@app.route("/edit_skills", methods=["GET", "POST"])
def edit_skills():
    if "admin" not in session:
        return redirect("/admin")

    if request.method == "POST":
        Skill.query.delete()
        categories = request.form.getlist("category")
        items_list = request.form.getlist("items")
        for cat, it in zip(categories, items_list):
            if cat.strip() and it.strip():
                db.session.add(Skill(category=cat.strip(), items=it.strip()))
        db.session.commit()
        flash("Skills updated successfully.")
        return redirect("/dashboard")

    skills = Skill.query.order_by(Skill.id).all()
    return render_template("edit_skills.html", skills=skills)

# EDIT EXPERIENCE
@app.route("/edit_experience", methods=["GET", "POST"])
def edit_experience():
    if "admin" not in session:
        return redirect("/admin")

    if request.method == "POST":
        Experience.query.delete()
        titles = request.form.getlist("title")
        companies = request.form.getlist("company")
        periods = request.form.getlist("period")
        descs = request.form.getlist("desc")
        for t, c, p, d in zip(titles, companies, periods, descs):
            if t.strip() and c.strip():
                db.session.add(Experience(
                    title=t.strip(),
                    company=c.strip(),
                    period=p.strip(),
                    desc=d.strip()
                ))
        db.session.commit()
        flash("Experience updated successfully.")
        return redirect("/dashboard")

    experience = Experience.query.order_by(Experience.id.desc()).all()
    return render_template("edit_experience.html", experience=experience)

# EDIT CONTACT
@app.route("/edit_contact", methods=["GET", "POST"])
def edit_contact():
    if "admin" not in session:
        return redirect("/admin")

    if request.method == "POST":
        email = request.form["email"].strip()
        phone = request.form["phone"].strip()
        location = request.form["location"].strip()
        linkedin = request.form["linkedin"].strip()

        ContactInfo.query.delete()
        new_contact = ContactInfo(
            email=email,
            phone=phone,
            location=location,
            linkedin=linkedin
        )
        db.session.add(new_contact)
        db.session.commit()
        flash("Contact info updated successfully.")
        return redirect("/dashboard")

    contact = ContactInfo.query.first()
    return render_template("edit_contact.html", contact=contact)

# LOGOUT
@app.route("/logout")
def logout():
    session.pop("admin", None)
    return redirect("/")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)