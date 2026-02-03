# Online Auction Platform

A Flask-based auction system demonstrating functional bidding, session management, and data integrity.

## Features

### 1. User Sessions (Security)
- **Secure Login/Logout**: Uses Flask sessions with password hashing (Werkzeug)
- **Session Timeout**: 30-minute inactivity timeout for security
- **Password Hashing**: Passwords stored using `generate_password_hash`

### 2. Real-Time Bidding Logic (Data Integrity)
- **Bid Validation**: Ensures new bids are higher than current bid
- **Self-Bid Prevention**: Users cannot bid on their own items
- **Atomic Updates**: Database transactions ensure data consistency
- **Bid History**: Complete audit trail of all bids

### 3. Winner Selection
- **Automatic Selection**: Winners determined when auction end time passes
- **Background Check**: `check_and_finalize_auctions()` runs on page loads
- **Fair Process**: Highest bidder at end time wins

### 4. Security Measures
- **Authentication Required**: Protected routes use `@login_required` decorator
- **Authorization Checks**: Prevents unauthorized actions (self-bidding)
- **CSRF Protection**: Forms use POST method with session validation
- **SQL Injection Prevention**: Uses SQLAlchemy ORM with parameterized queries

## Project Structure

```
flask_auction/
├── app.py                 # Main application (all routes & models)
├── requirements.txt       # Python dependencies
├── README.md             # This file
└── templates/            # HTML templates
    ├── base.html         # Base layout with Bootstrap
    ├── index.html        # Homepage with auction listings
    ├── login.html        # Login form
    ├── register.html     # Registration form
    ├── item_detail.html  # Single item view & bidding
    ├── create_item.html  # Create new auction
    ├── my_auctions.html  # User dashboard
    └── error.html        # Error pages
```

## Installation & Running

```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the application
python app.py

# 4. Open browser to http://localhost:5000
```

## Demo Credentials

After starting the app, sample users are created:

| Username | Password     |
|----------|-------------|
| alice    | password123 |
| bob      | password123 |
| charlie  | password123 |

## Database Models

### User
```python
- id: Integer (Primary Key)
- username: String (Unique)
- password: String (Hashed)
- created_at: DateTime
```

### Item (Auction)
```python
- id: Integer (Primary Key)
- name: String
- description: Text
- starting_bid: Float
- current_bid: Float
- seller_id: Foreign Key → User
- winner_id: Foreign Key → User (nullable)
- current_bidder_id: Foreign Key → User (nullable)
- end_time: DateTime
- created_at: DateTime
```

### Bid (Audit Trail)
```python
- id: Integer (Primary Key)
- amount: Float
- item_id: Foreign Key → Item
- user_id: Foreign Key → User
- created_at: DateTime
```

## Testing Scenarios

### Functional Testing
1. Register new user
2. Create auction item
3. Place bid on item
4. Verify bid history updates

### Security Testing
1. Try bidding without login → Redirects to login
2. Try bidding on own item → Error message
3. Wait 30 minutes → Session expires

### Data Integrity Testing
1. Place bid lower than current → Error message
2. Place valid bid → Updates current_bid
3. Auction ends → Winner automatically selected

## Key Code Explanations

### Session Timeout (app.py)
```python
# Check if session expired (30 minutes)
if datetime.utcnow() - last_activity > timedelta(minutes=30):
    session.clear()
    return redirect(url_for('login'))
```

### Bid Validation (app.py)
```python
# Ensure bid is higher than current
if bid_amount <= item.current_bid:
    flash('Bid must be higher than current bid')
    return redirect(...)
```

### Winner Selection (app.py)
```python
# Find ended auctions without winners
ended = Item.query.filter(
    Item.end_time <= now,
    Item.winner_id.is_(None)
).all()

for item in ended:
    item.winner_id = item.current_bidder_id
```

## Production Considerations

For deployment, consider:
1. Use PostgreSQL/MySQL instead of SQLite
2. Use environment variables for SECRET_KEY
3. Deploy with Gunicorn/uWSGI
4. Add HTTPS with proper certificates
5. Implement rate limiting
6. Add WebSockets for real-time updates
