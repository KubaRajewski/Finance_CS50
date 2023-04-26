import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, jsonify
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
import datetime
from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

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
    """Show portfolio of stocks"""
    user_id = session["user_id"]
    cash_db = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
    if not cash_db:
        return apology("User not found")
    cash = float(round(cash_db[0]["cash"], 2))
    transactions_db = db.execute("SELECT symbol, SUM(shares) AS shares, ROUND(price, 2) as price, ROUND((SUM(shares) * price), 2) AS total FROM Transactions WHERE user_id = ? Group by symbol", user_id)
    cash_db = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
    #round the variable to 2 decimal point
    cash = float(round(cash_db[0]["cash"],2))

    for i in transactions_db:
        name = lookup(i["symbol"])
        i["name"] = name["name"]

    total = round(cash + sum([float(round(i["total"],2)) for i in transactions_db]),2)
    #if no shares, delete the row
    transactions_db = [i for i in transactions_db if i["shares"] > 0]

    return render_template("index.html", database = transactions_db, cash = cash , total = total)


#function to deposit money
@app.route("/deposit", methods=["GET", "POST"])
@login_required
def deposit():
    """Deposit money"""
    if request.method == "GET":
        return render_template("deposit.html")
    else:
        deposit = request.form.get("deposit")
        print("Deposit:", deposit)  # Add this line
        if deposit is None or deposit == "":
            return apology("Deposit amount is required")
        deposit = float(deposit)
        user_id = session["user_id"]
        user_cash_db = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
        user_cash = user_cash_db[0]["cash"]
        uptd_cash = user_cash + deposit
        db.execute("UPDATE users SET cash = ? WHERE id = ?", uptd_cash, user_id)
        flash("Deposited!")
        return redirect("/")

#function to withdraw money
@app.route("/withdraw", methods=["GET", "POST"])
@login_required
def withdraw():
    """Withdraw money"""
    if request.method == "GET":
        return render_template("withdraw.html")
    else:
        withdraw = request.form.get("withdraw")
        print("Withdraw:", withdraw)
        if withdraw is None or withdraw == "":
            return apology("Withdraw amount is required")
        if float(withdraw) < 0:
            return apology("Withdraw amount must be positive")
        withdraw = float(withdraw)
        user_id = session["user_id"]
        user_cash_db = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
        user_cash = user_cash_db[0]["cash"]
        if user_cash < withdraw:
            return apology("not enough money")
        uptd_cash = user_cash - withdraw
        db.execute("UPDATE users SET cash = ? WHERE id = ?", uptd_cash, user_id)
        flash("Withdrawn!")
        return redirect("/")

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "GET":
        return render_template("buy.html")
    else:
        symbol = request.form.get("symbol")
        shares = int(request.form.get("shares"))


        if not symbol:
            return apology("Symbol needed")
        if not shares.isdigit():
            return apology("You cannot purchase partial shares.")

        stock = lookup(symbol.upper())

        if stock == None:
            return apology("symbol does not exist")
        if shares < 0:
            return apology("share not allowed")

        transaction_value = shares * stock["price"]

        user_id = session["user_id"]
        user_cash_db = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
        user_cash = user_cash_db[0]["cash"]

        if user_cash < transaction_value:
            return apology("not enough money")

        uptd_cash = user_cash - transaction_value
        db.execute("UPDATE users SET cash = ? WHERE id = ?", uptd_cash, user_id)

        date = datetime.datetime.now()
        db.execute("INSERT INTO transactions (user_id, symbol, shares, price, date) VALUES (?, ?, ?, ?, ?)", user_id, stock["symbol"], shares, stock["price"], date)
        flash("Bought!")
        return redirect("/")

@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    user_id = session["user_id"]
    transactions_db = db.execute("SELECT symbol, shares, price, date FROM Transactions WHERE user_id = ?", user_id)

    for i in transactions_db:
        name = lookup(i["symbol"])
        i["name"] = name["name"]

    return render_template("history.html", database = transactions_db)

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
    """Get stock quote."""
    if request.method == "GET":
        return render_template("quote.html")
    else:
        symbol = request.form.get("symbol")

        if not symbol:
            return apology("Symbol needed")

        stock = lookup(symbol.upper())

        if stock == None:
            return apology("symbol does not exist")
        return render_template("quoted.html", name = stock["name"], price = stock["price"], symbol = stock["symbol"])

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (submitting the register form)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # ensure passwords match
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("passwords do not match", 400)

        # save username and password hash in variables
        username = request.form.get("username")
        hash = generate_password_hash(request.form.get("password"))

        # Query database to ensure username isn't already taken
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=username)
        if len(rows) != 0:
            return apology("username is already taken", 400)

        # insert username and hash into database
        db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)",
                   username=username, hash=hash)

        # redirect to login page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "GET":
        user_id = session["user_id"]
        stocks = db.execute("SELECT symbol, SUM(shares) AS total_shares FROM transactions WHERE user_id = ? GROUP BY symbol HAVING total_shares > 0", user_id)
        return render_template("sell.html", stocks=stocks)
    else:
        symbol = request.form.get("symbol").upper()
        shares = int(request.form.get("shares"))

        if not symbol:
            return apology("Symbol needed")

        stock = lookup(symbol.upper())

        if stock == None:
            return apology("Symbol does not exist")
        if shares < 0:
            return apology("Share not allowed")

        user_id = session["user_id"]
        user_cash_db = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
        user_cash = user_cash_db[0]["cash"]

        transaction_value = shares * stock["price"]

        # Check if user owns enough shares to sell
        user_shares_db = db.execute("SELECT SUM(shares) AS total_shares FROM transactions WHERE user_id = ? AND symbol = ? GROUP BY symbol", user_id, symbol)
        if len(user_shares_db) == 0:
            return apology("You do not own any shares of this stock")
        user_shares = user_shares_db[0]["total_shares"]

        if user_shares < shares:
            return apology("Not enough shares to sell")

        uptd_cash = user_cash + transaction_value
        db.execute("UPDATE users SET cash = ? WHERE id = ?", uptd_cash, user_id)

        date = datetime.datetime.now()
        db.execute("INSERT INTO transactions (user_id, symbol, shares, price, date) VALUES (?, ?, ?, ?, ?)", user_id, stock["symbol"], -shares, stock["price"], date)
        flash("Sold!")
        return redirect("/")

