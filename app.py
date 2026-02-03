"""
Online Auction Platform - Flask Application
============================================
This application demonstrates:
- Functional bidding with data integrity checks
- User session management with timeouts
- Winner selection logic based on auction end time
- Security measures (authentication, authorization)

Author: Reference Implementation
"""

from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from functools import wraps
import os

# =============================================================================
# APPLICATION CONFIGURATION
# =============================================================================

app = Flask(__name__)

# Secret key for session management (use a secure random key in production)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-change-in-production')

# SQLite database configuration (use PostgreSQL/MySQL in production)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///auction.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Session timeout configuration (30 minutes)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)

# Initialize SQLAlchemy
db = SQLAlchemy(app)

# =============================================================================
# DATABASE MODELS
# =============================================================================

class User(db.Model):
    """
    User Model
    ----------
    Stores user credentials and profile information.
    
    Fields:
    - id: Unique identifier (Primary Key)
    - username: Unique username for login
    - password: Hashed password (never store plain text!)
    - created_at: Account creation timestamp
    """
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)  # Hashed password
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship: Items created by this user
    items = db.relationship('Item', backref='seller', lazy=True, foreign_keys='Item.seller_id')
    
    def set_password(self, password):
        """Hash and set the user's password"""
        self.password = generate_password_hash(password)
    
    def check_password(self, password):
        """Verify password against stored hash"""
        return check_password_hash(self.password, password)
    
    def __repr__(self):
        return f'<User {self.username}>'


class Item(db.Model):
    """
    Item Model (Auction Item)
    -------------------------
    Stores auction items with bidding information.
    
    Fields:
    - id: Unique identifier (Primary Key)
    - name: Item name/title
    - description: Detailed item description
    - starting_bid: Minimum bid amount
    - current_bid: Current highest bid
    - seller_id: User who created the auction (Foreign Key)
    - winner_id: User who won the auction (Foreign Key, nullable)
    - end_time: When the auction ends
    - created_at: When the auction was created
    """
    __tablename__ = 'items'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    starting_bid = db.Column(db.Float, nullable=False)
    current_bid = db.Column(db.Float, nullable=False)
    seller_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    winner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    current_bidder_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    end_time = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    winner = db.relationship('User', foreign_keys=[winner_id], backref='won_items')
    current_bidder = db.relationship('User', foreign_keys=[current_bidder_id])
    
    @property
    def is_active(self):
        """Check if auction is still active (not ended)"""
        return datetime.utcnow() < self.end_time and self.winner_id is None
    
    @property
    def time_remaining(self):
        """Get time remaining until auction ends"""
        if not self.is_active:
            return "Ended"
        delta = self.end_time - datetime.utcnow()
        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours}h {minutes}m {seconds}s"
    
    def __repr__(self):
        return f'<Item {self.name}>'


class Bid(db.Model):
    """
    Bid Model
    ---------
    Records all bids for audit trail and history.
    
    Fields:
    - id: Unique identifier (Primary Key)
    - amount: Bid amount
    - item_id: Item being bid on (Foreign Key)
    - user_id: User placing the bid (Foreign Key)
    - created_at: When the bid was placed
    """
    __tablename__ = 'bids'
    
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    item = db.relationship('Item', backref='bids')
    user = db.relationship('User', backref='bids')
    
    def __repr__(self):
        return f'<Bid ${self.amount} on Item {self.item_id}>'


# =============================================================================
# AUTHENTICATION DECORATORS
# =============================================================================

def login_required(f):
    """
    Decorator: Require Login
    ------------------------
    Protects routes that require authentication.
    Redirects to login page if user is not logged in.
    Also checks for session timeout.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if user is logged in
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        
        # Check for session timeout
        if 'last_activity' in session:
            last_activity = datetime.fromisoformat(session['last_activity'])
            timeout = timedelta(minutes=30)
            
            if datetime.utcnow() - last_activity > timeout:
                # Session expired - clear and redirect
                session.clear()
                flash('Your session has expired. Please log in again.', 'warning')
                return redirect(url_for('login'))
        
        # Update last activity time
        session['last_activity'] = datetime.utcnow().isoformat()
        
        return f(*args, **kwargs)
    return decorated_function


def get_current_user():
    """
    Helper: Get Current User
    ------------------------
    Returns the currently logged-in user object or None.
    """
    if 'user_id' in session:
        return User.query.get(session['user_id'])
    return None


# =============================================================================
# WINNER SELECTION LOGIC
# =============================================================================

def check_and_finalize_auctions():
    """
    Winner Selection Logic
    ----------------------
    Checks all active auctions and marks winners for those that have ended.
    This should be called periodically (e.g., via cron job or before page loads).
    
    Logic:
    1. Find all items where end_time has passed and winner_id is NULL
    2. For each item, set winner_id to current_bidder_id (if any bids exist)
    """
    now = datetime.utcnow()
    
    # Find auctions that have ended but don't have a winner set
    ended_auctions = Item.query.filter(
        Item.end_time <= now,
        Item.winner_id.is_(None),
        Item.current_bidder_id.isnot(None)  # Must have at least one bid
    ).all()
    
    for item in ended_auctions:
        # Set the winner to the current highest bidder
        item.winner_id = item.current_bidder_id
        print(f"[AUCTION ENDED] Item '{item.name}' won by User ID {item.winner_id}")
    
    if ended_auctions:
        db.session.commit()


# =============================================================================
# ROUTES - AUTHENTICATION
# =============================================================================

@app.route('/')
def index():
    """
    Homepage
    --------
    Displays all active auctions and completed auctions.
    Calls winner selection logic to finalize ended auctions.
    """
    # Check and finalize any ended auctions
    check_and_finalize_auctions()
    
    # Get active auctions (not ended)
    active_items = Item.query.filter(
        Item.end_time > datetime.utcnow(),
        Item.winner_id.is_(None)
    ).order_by(Item.end_time.asc()).all()
    
    # Get recently completed auctions
    completed_items = Item.query.filter(
        Item.winner_id.isnot(None)
    ).order_by(Item.end_time.desc()).limit(5).all()
    
    return render_template('index.html', 
                          active_items=active_items, 
                          completed_items=completed_items,
                          current_user=get_current_user())


@app.route('/register', methods=['GET', 'POST'])
def register():
    """
    User Registration
    -----------------
    Creates a new user account with hashed password.
    
    Security:
    - Password is hashed using Werkzeug's generate_password_hash
    - Username uniqueness is enforced at database level
    """
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        # Validation
        errors = []
        
        if len(username) < 3:
            errors.append('Username must be at least 3 characters.')
        
        if len(password) < 6:
            errors.append('Password must be at least 6 characters.')
        
        if password != confirm_password:
            errors.append('Passwords do not match.')
        
        if User.query.filter_by(username=username).first():
            errors.append('Username already exists.')
        
        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('register.html')
        
        # Create new user with hashed password
        new_user = User(username=username)
        new_user.set_password(password)  # Hash the password
        
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    User Login
    ----------
    Authenticates user and creates session.
    
    Security:
    - Password verified against hash
    - Session includes last_activity for timeout
    - Session marked as permanent for proper timeout handling
    """
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        # Find user by username
        user = User.query.filter_by(username=username).first()
        
        # Verify credentials
        if user and user.check_password(password):
            # Create session
            session.permanent = True  # Enable session timeout
            session['user_id'] = user.id
            session['username'] = user.username
            session['last_activity'] = datetime.utcnow().isoformat()
            
            flash(f'Welcome back, {user.username}!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password.', 'danger')
    
    return render_template('login.html')


@app.route('/logout')
def logout():
    """
    User Logout
    -----------
    Clears the session and logs out the user.
    """
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))


# =============================================================================
# ROUTES - AUCTION ITEMS
# =============================================================================

@app.route('/item/<int:item_id>')
def view_item(item_id):
    """
    View Auction Item
    -----------------
    Displays detailed item information and bid history.
    """
    check_and_finalize_auctions()
    
    item = Item.query.get_or_404(item_id)
    bid_history = Bid.query.filter_by(item_id=item_id).order_by(Bid.created_at.desc()).all()
    
    return render_template('item_detail.html', 
                          item=item, 
                          bid_history=bid_history,
                          current_user=get_current_user())


@app.route('/create-item', methods=['GET', 'POST'])
@login_required
def create_item():
    """
    Create Auction Item
    -------------------
    Allows logged-in users to create new auction listings.
    """
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        starting_bid = request.form.get('starting_bid', type=float)
        duration_hours = request.form.get('duration_hours', type=int, default=24)
        
        # Validation
        errors = []
        
        if len(name) < 3:
            errors.append('Item name must be at least 3 characters.')
        
        if len(description) < 10:
            errors.append('Description must be at least 10 characters.')
        
        if not starting_bid or starting_bid < 0.01:
            errors.append('Starting bid must be at least $0.01.')
        
        if not duration_hours or duration_hours < 1:
            errors.append('Duration must be at least 1 hour.')
        
        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('create_item.html', current_user=get_current_user())
        
        # Create new item
        new_item = Item(
            name=name,
            description=description,
            starting_bid=starting_bid,
            current_bid=starting_bid,
            seller_id=session['user_id'],
            end_time=datetime.utcnow() + timedelta(hours=duration_hours)
        )
        
        db.session.add(new_item)
        db.session.commit()
        
        flash('Auction item created successfully!', 'success')
        return redirect(url_for('view_item', item_id=new_item.id))
    
    return render_template('create_item.html', current_user=get_current_user())


# =============================================================================
# ROUTES - BIDDING (Core Functionality)
# =============================================================================

@app.route('/bid/<int:item_id>', methods=['POST'])
@login_required
def place_bid(item_id):
    """
    Place a Bid (Real-Time Bidding Logic)
    -------------------------------------
    Handles bid placement with comprehensive validation.
    
    Data Integrity Checks:
    1. Item must exist
    2. Auction must be active (not ended)
    3. User cannot bid on their own item (Security)
    4. Bid must be higher than current bid (Data Integrity)
    5. User must be logged in (Authentication)
    
    Security Measures:
    - Login required decorator ensures authentication
    - Seller check prevents self-bidding
    - Amount validation prevents negative/zero bids
    """
    # Get the item
    item = Item.query.get_or_404(item_id)
    
    # Get bid amount from form
    bid_amount = request.form.get('bid_amount', type=float)
    
    # SECURITY CHECK 1: Prevent bidding on own items
    if item.seller_id == session['user_id']:
        flash('You cannot bid on your own item!', 'danger')
        return redirect(url_for('view_item', item_id=item_id))
    
    # DATA INTEGRITY CHECK 1: Auction must be active
    if not item.is_active:
        flash('This auction has ended.', 'warning')
        return redirect(url_for('view_item', item_id=item_id))
    
    # DATA INTEGRITY CHECK 2: Bid must be valid number
    if not bid_amount or bid_amount <= 0:
        flash('Please enter a valid bid amount.', 'danger')
        return redirect(url_for('view_item', item_id=item_id))
    
    # DATA INTEGRITY CHECK 3: Bid must be higher than current bid
    minimum_bid = item.current_bid + 0.01  # Minimum increment of $0.01
    
    if bid_amount <= item.current_bid:
        flash(f'Your bid must be higher than the current bid of ${item.current_bid:.2f}', 'danger')
        return redirect(url_for('view_item', item_id=item_id))
    
    # All checks passed - place the bid
    # Update item's current bid and bidder
    item.current_bid = bid_amount
    item.current_bidder_id = session['user_id']
    
    # Create bid record for history/audit
    new_bid = Bid(
        amount=bid_amount,
        item_id=item_id,
        user_id=session['user_id']
    )
    
    db.session.add(new_bid)
    db.session.commit()
    
    flash(f'Bid of ${bid_amount:.2f} placed successfully!', 'success')
    return redirect(url_for('view_item', item_id=item_id))


# =============================================================================
# ROUTES - USER DASHBOARD
# =============================================================================

@app.route('/my-auctions')
@login_required
def my_auctions():
    """
    User Dashboard
    --------------
    Shows user's active listings, bids, and won items.
    """
    user_id = session['user_id']
    
    # Items the user is selling
    my_items = Item.query.filter_by(seller_id=user_id).order_by(Item.created_at.desc()).all()
    
    # Items the user has bid on (unique items)
    my_bids = db.session.query(Item).join(Bid).filter(
        Bid.user_id == user_id,
        Item.seller_id != user_id  # Exclude own items
    ).distinct().all()
    
    # Items the user has won
    won_items = Item.query.filter_by(winner_id=user_id).all()
    
    return render_template('my_auctions.html',
                          my_items=my_items,
                          my_bids=my_bids,
                          won_items=won_items,
                          current_user=get_current_user())


# =============================================================================
# ERROR HANDLERS
# =============================================================================

@app.errorhandler(404)
def not_found_error(error):
    """Handle 404 errors"""
    return render_template('error.html', 
                          error_code=404, 
                          error_message='Page not found',
                          current_user=get_current_user()), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    db.session.rollback()  # Rollback any failed transactions
    return render_template('error.html', 
                          error_code=500, 
                          error_message='Internal server error',
                          current_user=get_current_user()), 500


# =============================================================================
# CONTEXT PROCESSOR
# =============================================================================

@app.context_processor
def inject_now():
    """Make datetime available in all templates"""
    return {'now': datetime.utcnow()}


# =============================================================================
# DATABASE INITIALIZATION & SAMPLE DATA
# =============================================================================

def init_db():
    """
    Initialize Database
    -------------------
    Creates all tables and adds sample data for testing.
    """
    with app.app_context():
        # Create all tables
        db.create_all()
        
        # Check if we already have users (avoid duplicate sample data)
        if User.query.first() is None:
            print("[INIT] Creating sample data...")
            
            # Create sample users
            user1 = User(username='alice')
            user1.set_password('password123')
            
            user2 = User(username='bob')
            user2.set_password('password123')
            
            user3 = User(username='charlie')
            user3.set_password('password123')
            
            db.session.add_all([user1, user2, user3])
            db.session.commit()
            
            # Create sample items
            item1 = Item(
                name='Vintage Watch Collection',
                description='A beautiful collection of 5 vintage watches from the 1960s. All in working condition with original boxes.',
                starting_bid=100.00,
                current_bid=100.00,
                seller_id=user1.id,
                end_time=datetime.utcnow() + timedelta(hours=24)
            )
            
            item2 = Item(
                name='Rare Comic Book',
                description='First edition Spider-Man comic from 1962. Near mint condition, professionally graded.',
                starting_bid=500.00,
                current_bid=500.00,
                seller_id=user2.id,
                end_time=datetime.utcnow() + timedelta(hours=48)
            )
            
            item3 = Item(
                name='Antique Desk Lamp',
                description='Art Deco style desk lamp from the 1930s. Brass base with original glass shade.',
                starting_bid=75.00,
                current_bid=75.00,
                seller_id=user1.id,
                end_time=datetime.utcnow() + timedelta(hours=12)
            )
            
            db.session.add_all([item1, item2, item3])
            db.session.commit()
            
            print("[INIT] Sample data created successfully!")
            print("[INIT] Sample users: alice, bob, charlie (password: password123)")


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == '__main__':
    # Initialize database and create tables
    init_db()
    
    # Run the Flask development server
    # Debug=True for development (shows errors, auto-reloads)
    # Use a production WSGI server (gunicorn, uwsgi) in production
    app.run(debug=True, host='0.0.0.0', port=5000)
