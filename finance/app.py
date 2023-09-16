import os

from cs50 import SQL
from datetime import datetime
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd, curr

# Set current time
date = datetime.now()

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Create a new table for transactions
# db.execute("""CREATE TABLE transactions
#             (order_ID INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
#             user_ID INTEGER NOT NULL,
#             transaction_type TEXT NOT NULL,
#             symbol TEXT NOT NULL,
#             shares INTEGER NOT NULL,
#             price INTEGER NOT NULL,
#             transacted TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
#             FOREIGN KEY(user_ID) REFERENCES users(id));""")
# CREATE UNIQUE INDEX order_ID ON transactions(order_ID);

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    # Create a list to compile all dictionaries
    list = []

    # Extract information from transactions table
    rows = db.execute("SELECT symbol, SUM(shares), price FROM transactions GROUP BY symbol HAVING user_id = ?", session["user_id"])
    cash_row = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
    cash = cash_row[0].get("cash")

    # First case scenario
    if len(rows) == 0:
        return render_template("blank.html", cash=cash)

    # Iterate through each row
    total = 0
    for row in rows:

        shares = curr(str(row["symbol"]), session["user_id"])
        # Do not show the row if no more shares
        if shares == 0:
            continue

        # print("SHARES: " + str(shares))
        # print(float(shares))
        # price = 0
        # if str(row["symbol"]).upper() == "ASDF":
        #     print("TEST")
        #     price = 14
        price = lookup(str(row["symbol"]))["price"]
        value = float(shares) * price
        # print(value)
        name = lookup(str(row["symbol"]))["name"]
        dict = {
            "name": name,
            "symbol": row["symbol"],
            "shares": shares,
            "price": price,
            "value": value
        }
        total += value
        # print("TOTAL :" + str(total))
        list.append(dict)

    # Return the HTML page
    total += cash
    # print("TOTAL after :" + str(total))
    return render_template("index.html", list=list, cash=cash, total=total)

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    # POST route by submitting the buy request
    if request.method == "POST":

        # Check for valid input
        # Ensure symbol was submitted
        if not request.form.get("symbol"):
            return apology("must provide stock symbol", 400)

        # Ensure number of shares is non negative
        shares = request.form.get("shares")
        if not shares.isdigit() or int(shares) < 1:
            return apology("invalid input of shares", 400)

        # Ensure symbol is valid stock symbol
        if lookup(str(request.form.get("symbol"))) is None:
            return apology("not a valid stock symbol", 400)

        # Check if user has enough cash to buy stock
        price = lookup(request.form.get("symbol"))["price"]
        user = session["user_id"]
        cash_row = db.execute("SELECT cash FROM users WHERE id = ?", user)
        cash = cash_row[0].get("cash")
        if price > float(cash):
            return apology("insufficient amount of cash", 400)

        # Update the user's cash and transactions to reflect purchase
        shares = int(request.form.get("shares"))
        new_cash = cash - (price * shares)
        symbol = request.form.get("symbol").upper()
        db.execute("UPDATE users SET cash = ? WHERE id = ?", new_cash, user)
        db.execute("INSERT INTO transactions (symbol, shares, price, user_ID, transaction_type, transacted) VALUES (?, ?, ?, ?, ?, ?)", symbol, shares, price, user, 'buy', date)

        # Redirect user to home page
        return redirect("/")

    # GET route by displaying the page
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    # Create a list for select menu
    list = db.execute("SELECT symbol, transaction_type, price, shares, transacted FROM transactions WHERE user_ID = ?", session["user_id"])

    # Render the HTML page
    return render_template("history.html", list=list)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    #Post method called by user searching up request
    if request.method == "POST":
        # Check lookup function
        if lookup(str(request.form.get("symbol"))) is None:
            return apology("stock doesn't exist", 400)

        # Look up information abou the stock
        stock = lookup(request.form.get("symbol"))
        name = stock["name"]
        price = stock["price"]
        symbol = stock["symbol"]

        # Render template to display information
        return render_template("quoted.html", name=name, price=price, symbol=symbol)

    # GET method called by displaying stock request page
    else:
        return render_template("quote.html")



@app.route("/register", methods=["GET", "POST"])
def register():
    # Post method called by user submitting registered data
    if request.method == "POST":

        # Check for errors in registration
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        if not request.form.get("password"):
            return apology("must provide password", 400)

        # Ensure confirmation password was submitted
        if not request.form.get("confirmation"):
            return apology("must confirm password", 400)

        # Ensure passwords must match
        if request.form.get("password") != request.form.get("confirmation"):
            return apology("passwords must match", 400)

        # Ensure username is not already taken
        row = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))
        if len(row) == 1:
            return apology("username already taken", 400)

        # Store user data into the database
        # Generate hash for password
        username = request.form.get("username")
        password = generate_password_hash(request.form.get("password"))

        # Store data into the database & log user in
        session["user_id"] = db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, password)

        # # Log the user in
        # session["user_id"] = username

        # Redirect user to home page
        return redirect("/")


    # GET method called by displaying registration form
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    # Post method
    if request.method == "POST":
        # Check for valid input
        # Ensure symbol was submitted
        symbol = request.form.get("symbol").upper()
        shares = int(request.form.get("shares"))
        if not symbol:
            return apology("must provide stock symbol", 400)

        # Ensure shares was submitted
        if not shares:
            return apology("must provide shares", 400)

        # Ensure number of shares is non negative
        if shares < 1:
            return apology("must sell at least 1 stock", 400)

        # Ensure the user is not selling more than they own
        current = curr(symbol, session["user_id"])
        if shares > current:
            return apology("you do not have that many shares", 400)

        # Record in transactions
        price = lookup(symbol)["price"]
        cash_row = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        cash = cash_row[0].get("cash")
        new_cash = price * float(shares) + float(cash)
        db.execute("UPDATE users SET cash = ? WHERE id = ?", new_cash, session["user_id"])
        db.execute("INSERT INTO transactions (symbol, shares, price, user_ID, transaction_type, transacted) VALUES (?, ?, ?, ?, ?, ?)", symbol, shares, price, session["user_id"], 'sell', date)

        # Redirect user to home page
        return redirect("/")

    # GET method
    else:
        # Create a list for select menu
        list = []
        rows = db.execute("SELECT symbol FROM transactions GROUP BY symbol HAVING user_ID = ? AND transaction_type = 'buy'", session["user_id"])
        for row in rows:
            if curr(row["symbol"], session["user_id"]) == 0:
                continue
            list.append(row["symbol"])

        # Render the display page
        return render_template("sell.html", symbols=list)

