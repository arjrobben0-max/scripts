from flask import (
    render_template,
    request,
    redirect,
    url_for,
    flash,
    current_app,
)
from flask_login import login_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from flask_mail import Message

from . import auth_bp  # Blueprint
from smartscripts.extensions import db, mail
from smartscripts.models.user import User
from smartscripts.app.forms import LoginForm, ForgotPasswordForm, ResetPasswordForm, RegisterForm

# -----------------------------
# Helper: Token Serializer
# -----------------------------
def get_serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"])


# -----------------------------
# LOGIN ROUTE
# -----------------------------
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.strip()
        password = form.password.data.strip()
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user, remember=form.remember.data)
            flash(f"✅ Welcome back, {user.username}!", "success")
            return redirect(url_for("main_bp.dashboard"))  # ✅ corrected blueprint endpoint
        else:
            flash("❌ Invalid email or password.", "danger")
    return render_template("auth/login.html", form=form)


# -----------------------------
# LOGOUT ROUTE
# -----------------------------
@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("✅ You have been logged out.", "info")
    return redirect(url_for("auth_bp.login"))


# -----------------------------
# REGISTER ROUTE
# -----------------------------
@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        hashed_password = generate_password_hash(form.password.data)
        new_user = User(
            username=form.username.data.strip(),
            email=form.email.data.strip(),
            password=hashed_password,
            role=form.role.data
        )
        db.session.add(new_user)
        db.session.commit()
        flash("✅ Registration successful! You can now log in.", "success")
        return redirect(url_for("auth_bp.login"))
    return render_template("auth/register.html", form=form)


# -----------------------------
# FORGOT PASSWORD
# -----------------------------
@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        email = form.email.data.strip()
        user = User.query.filter_by(email=email).first()
        if user:
            token = get_serializer().dumps(email, salt="password-reset-salt")
            reset_url = url_for("auth_bp.reset_password", token=token, _external=True)
            try:
                msg = Message(
                    subject="🔐 Reset Your Password - SmartScripts",
                    recipients=[email],
                    body=(
                        f"Hello {user.username},\n\n"
                        f"You requested to reset your password.\n\n"
                        f"Click the link below (valid for 1 hour):\n{reset_url}\n\n"
                        f"If you did not request this, ignore this email."
                    ),
                )
                mail.send(msg)
                flash("✅ Password reset link sent! Check your email.", "success")
            except Exception as e:
                current_app.logger.error(f"Email send failed: {e}")
                flash("⚠️ Failed to send reset email. Please try again later.", "danger")
        else:
            flash("❌ No account found with that email address.", "danger")
        return redirect(url_for("auth_bp.forgot_password"))
    return render_template("auth/forgot_password.html", form=form)


# -----------------------------
# RESET PASSWORD
# -----------------------------
@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    form = ResetPasswordForm()
    serializer = get_serializer()
    try:
        email = serializer.loads(token, salt="password-reset-salt", max_age=3600)
    except SignatureExpired:
        flash("⚠️ Reset link expired. Request a new one.", "warning")
        return redirect(url_for("auth_bp.forgot_password"))
    except BadSignature:
        flash("❌ Invalid or tampered reset token.", "danger")
        return redirect(url_for("auth_bp.forgot_password"))

    user = User.query.filter_by(email=email).first_or_404()
    if form.validate_on_submit():
        user.password = generate_password_hash(form.password.data)
        db.session.commit()
        flash("✅ Password reset successful. You can now log in.", "success")
        return redirect(url_for("auth_bp.login"))

    return render_template("auth/reset_password.html", form=form, token=token)


# -----------------------------
# Optional index route
# -----------------------------
@auth_bp.route("/")
def index():
    return render_template("main/index.html")
