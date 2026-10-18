import math
import os
import sqlite3
from pathlib import Path

from flask import Flask, abort, flash, g, redirect, render_template, request, url_for


CATEGORIES = ("Book", "Lab Coat", "Calculator", "Other")
LISTING_TYPES = ("Sell", "Rent")

app = Flask(__name__)
app.config.update(
    DATABASE=str(Path(app.instance_path) / "campusswap.sqlite3"),
    SECRET_KEY=os.environ.get("SECRET_KEY", "change-this-development-secret"),
)


@app.template_filter("money")
def format_money(value):
    return f"{float(value):,.2f}".rstrip("0").rstrip(".")


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    db = get_db()
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS Users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            hostel_room TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS Listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES Users(id),
            title TEXT NOT NULL,
            category TEXT NOT NULL CHECK (category IN ('Book', 'Lab Coat', 'Calculator', 'Other')),
            listing_type TEXT NOT NULL CHECK (listing_type IN ('Sell', 'Rent')),
            price REAL NOT NULL CHECK (price >= 0),
            description TEXT NOT NULL DEFAULT '',
            contact_info TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive'))
        );

        CREATE INDEX IF NOT EXISTS idx_listings_active_created
            ON Listings(status, created_at DESC);
        """
    )
    db.commit()


@app.cli.command("init-db")
def init_db_command():
    """Create the SQLite tables used by CampusSwap."""
    init_db()
    print(f"Initialized database at {app.config['DATABASE']}")


@app.get("/")
def index():
    query = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    listing_type = request.args.get("listing_type", "").strip()

    sql = """
        SELECT Listings.*, Users.name AS seller_name, Users.hostel_room
        FROM Listings
        JOIN Users ON Users.id = Listings.user_id
        WHERE Listings.status = 'active'
    """
    params = []
    if query:
        sql += """
            AND (Listings.title LIKE ? OR Listings.description LIKE ?
                 OR Users.name LIKE ? OR Users.hostel_room LIKE ?)
        """
        term = f"%{query}%"
        params.extend((term, term, term, term))
    if category in CATEGORIES:
        sql += " AND Listings.category = ?"
        params.append(category)
    if listing_type in LISTING_TYPES:
        sql += " AND Listings.listing_type = ?"
        params.append(listing_type)
    sql += " ORDER BY Listings.created_at DESC, Listings.id DESC"

    listings = get_db().execute(sql, params).fetchall()
    return render_template(
        "index.html",
        listings=listings,
        categories=CATEGORIES,
        query=query,
        selected_category=category,
        selected_type=listing_type,
    )


@app.route("/listings/new", methods=("GET", "POST"))
def add_listing():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        hostel_room = request.form.get("hostel_room", "").strip()
        title = request.form.get("title", "").strip()
        category = request.form.get("category", "").strip()
        listing_type = request.form.get("listing_type", "").strip()
        description = request.form.get("description", "").strip()
        contact_info = request.form.get("contact_info", "").strip()
        price_text = request.form.get("price", "").strip()

        errors = []
        if not all((name, email, hostel_room, title, contact_info, price_text)):
            errors.append("Please complete all required fields.")
        if "@" not in email or email.startswith("@") or email.endswith("@"):
            errors.append("Enter a valid email address.")
        if category not in CATEGORIES:
            errors.append("Choose one of the listed categories.")
        if listing_type not in LISTING_TYPES:
            errors.append("Choose Sell or Rent.")
        try:
            price = float(price_text)
            if not math.isfinite(price):
                errors.append("Enter a finite price.")
            elif price < 0:
                errors.append("Price cannot be negative.")
        except ValueError:
            price = 0
            errors.append("Enter a valid price.")

        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("add_listing.html", categories=CATEGORIES, form=request.form), 400

        db = get_db()
        with db:
            db.execute(
                """
                INSERT INTO Users (name, email, hostel_room)
                VALUES (?, ?, ?)
                ON CONFLICT(email) DO UPDATE SET
                    name = excluded.name,
                    hostel_room = excluded.hostel_room
                """,
                (name, email, hostel_room),
            )
            user = db.execute("SELECT id FROM Users WHERE email = ?", (email,)).fetchone()
            cursor = db.execute(
                """
                INSERT INTO Listings
                    (user_id, title, category, listing_type, price, description, contact_info)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (user["id"], title, category, listing_type, price, description, contact_info),
            )
            listing_id = cursor.lastrowid

        flash("Your listing is live. Thanks for sharing with your campus!", "success")
        return redirect(url_for("listing_detail", listing_id=listing_id))

    return render_template("add_listing.html", categories=CATEGORIES, form={})


@app.get("/listings/<int:listing_id>")
def listing_detail(listing_id):
    listing = get_db().execute(
        """
        SELECT Listings.*, Users.name AS seller_name, Users.email AS seller_email,
               Users.hostel_room
        FROM Listings
        JOIN Users ON Users.id = Listings.user_id
        WHERE Listings.id = ? AND Listings.status = 'active'
        """,
        (listing_id,),
    ).fetchone()
    if listing is None:
        abort(404)
    return render_template("listing_detail.html", listing=listing)


with app.app_context():
    init_db()


if __name__ == "__main__":
    app.run(debug=True)
