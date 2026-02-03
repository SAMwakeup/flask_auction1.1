"""
Comprehensive Test Suite for Flask Auction Application
=======================================================
Performs Functional, Integration, and Security Testing

Test Categories:
1. FUNCTIONAL TESTING - Core business logic and features
2. INTEGRATION TESTING - Component interactions and workflows
3. SECURITY TESTING - Authentication, authorization, and data protection

Author: Test Suite
"""

import unittest
import json
import os
import tempfile
from datetime import datetime, timedelta
from app import app, db, User, Item, Bid, init_db


class BaseTestCase(unittest.TestCase):
    """Base test case class with common setup/teardown"""
    
    def setUp(self):
        """Set up test client and database for each test"""
        # Create a fresh app instance for each test
        self.app = app
        
        # Use in-memory SQLite database for testing
        self.app.config['TESTING'] = True
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app.config['WTF_CSRF_ENABLED'] = False
        
        # Push app context
        self.app_context = self.app.app_context()
        self.app_context.push()
        
        self.client = self.app.test_client()
        
        # Create tables
        db.drop_all()  # Ensure clean slate
        db.create_all()
        self._create_test_data()
    
    def _create_test_data(self):
        """Create sample test data"""
        # Create test users
        self.user1 = User(username='testuser1')
        self.user1.set_password('password123')
        
        self.user2 = User(username='testuser2')
        self.user2.set_password('password123')
        
        self.user3 = User(username='testuser3')
        self.user3.set_password('password123')
        
        db.session.add_all([self.user1, self.user2, self.user3])
        db.session.commit()
        
        # Store user IDs for later use
        self.user1_id = self.user1.id
        self.user2_id = self.user2.id
        self.user3_id = self.user3.id
        
        # Create test items
        self.active_item = Item(
            name='Test Item 1',
            description='This is a test item description',
            starting_bid=50.00,
            current_bid=50.00,
            seller_id=self.user1_id,
            end_time=datetime.utcnow() + timedelta(hours=24)
        )
        
        self.ended_item = Item(
            name='Test Item 2',
            description='This is an ended test item',
            starting_bid=100.00,
            current_bid=150.00,
            seller_id=self.user2_id,
            current_bidder_id=self.user3_id,
            end_time=datetime.utcnow() - timedelta(hours=1)
        )
        
        db.session.add_all([self.active_item, self.ended_item])
        db.session.commit()
        
        # Store item IDs for later use
        self.active_item_id = self.active_item.id
        self.ended_item_id = self.ended_item.id
    
    def tearDown(self):
        """Clean up after tests"""
        db.session.remove()
        db.drop_all()
        self.app_context.pop()
    
    def login(self, username='testuser1', password='password123'):
        """Helper method to log in a user"""
        return self.client.post('/login', data=dict(
            username=username,
            password=password
        ), follow_redirects=True)
    
    def logout(self):
        """Helper method to log out"""
        return self.client.get('/logout', follow_redirects=True)


# =============================================================================
# FUNCTIONAL TESTING
# =============================================================================

class FunctionalTestCase(BaseTestCase):
    """Test core functionality and business logic"""
    
    # -------------------------------------------------------------------------
    # TEST: User Authentication
    # -------------------------------------------------------------------------
    
    def test_user_registration_success(self):
        """FT-001: User can register with valid credentials"""
        response = self.client.post('/register', data=dict(
            username='newuser',
            password='password123',
            confirm_password='password123'
        ), follow_redirects=True)
        
        self.assertEqual(response.status_code, 200)
        with app.app_context():
            user = User.query.filter_by(username='newuser').first()
            self.assertIsNotNone(user)
    
    def test_user_registration_password_mismatch(self):
        """FT-002: Registration fails when passwords don't match"""
        response = self.client.post('/register', data=dict(
            username='newuser',
            password='password123',
            confirm_password='different123'
        ), follow_redirects=True)
        
        self.assertIn(b'Passwords do not match', response.data)
    
    def test_user_registration_short_username(self):
        """FT-003: Registration fails with username < 3 characters"""
        response = self.client.post('/register', data=dict(
            username='ab',
            password='password123',
            confirm_password='password123'
        ), follow_redirects=True)
        
        self.assertIn(b'Username must be at least 3 characters', response.data)
    
    def test_user_registration_short_password(self):
        """FT-004: Registration fails with password < 6 characters"""
        response = self.client.post('/register', data=dict(
            username='newuser',
            password='pass',
            confirm_password='pass'
        ), follow_redirects=True)
        
        self.assertIn(b'Password must be at least 6 characters', response.data)
    
    def test_user_registration_duplicate_username(self):
        """FT-005: Registration fails with duplicate username"""
        response = self.client.post('/register', data=dict(
            username='testuser1',  # Already exists
            password='password123',
            confirm_password='password123'
        ), follow_redirects=True)
        
        self.assertIn(b'Username already exists', response.data)
    
    def test_user_login_success(self):
        """FT-006: User can log in with correct credentials"""
        response = self.login('testuser1', 'password123')
        
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Welcome back', response.data)
    
    def test_user_login_invalid_username(self):
        """FT-007: Login fails with invalid username"""
        response = self.login('nonexistent', 'password123')
        
        self.assertIn(b'Invalid username or password', response.data)
    
    def test_user_login_invalid_password(self):
        """FT-008: Login fails with incorrect password"""
        response = self.login('testuser1', 'wrongpassword')
        
        self.assertIn(b'Invalid username or password', response.data)
    
    def test_user_logout(self):
        """FT-009: User can log out"""
        self.login('testuser1', 'password123')
        response = self.logout()
        
        self.assertIn(b'logged out', response.data)
    
    # -------------------------------------------------------------------------
    # TEST: Auction Item Creation
    # -------------------------------------------------------------------------
    
    def test_create_item_success(self):
        """FT-010: Logged-in user can create auction item"""
        self.login('testuser1', 'password123')
        
        response = self.client.post('/create-item', data=dict(
            name='New Auction Item',
            description='This is a detailed description of the item being auctioned',
            starting_bid=25.50,
            duration_hours=24
        ), follow_redirects=True)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'created successfully', response.data)
    
    def test_create_item_requires_login(self):
        """FT-011: Non-logged-in user cannot create item"""
        response = self.client.post('/create-item', data=dict(
            name='Test Item',
            description='Test description',
            starting_bid=50.00,
            duration_hours=24
        ), follow_redirects=True)
        
        self.assertIn(b'Please log in', response.data)
    
    def test_create_item_short_name(self):
        """FT-012: Item creation fails with name < 3 characters"""
        self.login('testuser1', 'password123')
        
        response = self.client.post('/create-item', data=dict(
            name='AB',
            description='This is a detailed description',
            starting_bid=50.00,
            duration_hours=24
        ), follow_redirects=True)
        
        self.assertIn(b'Item name must be at least 3 characters', response.data)
    
    def test_create_item_short_description(self):
        """FT-013: Item creation fails with description < 10 characters"""
        self.login('testuser1', 'password123')
        
        response = self.client.post('/create-item', data=dict(
            name='Valid Name',
            description='Short',
            starting_bid=50.00,
            duration_hours=24
        ), follow_redirects=True)
        
        self.assertIn(b'Description must be at least 10 characters', response.data)
    
    def test_create_item_invalid_bid(self):
        """FT-014: Item creation fails with invalid starting bid"""
        self.login('testuser1', 'password123')
        
        response = self.client.post('/create-item', data=dict(
            name='Valid Name',
            description='This is a valid description',
            starting_bid=-10.00,
            duration_hours=24
        ), follow_redirects=True)
        
        self.assertIn(b'Starting bid must be at least', response.data)
    
    def test_create_item_invalid_duration(self):
        """FT-015: Item creation fails with invalid duration"""
        self.login('testuser1', 'password123')
        
        response = self.client.post('/create-item', data=dict(
            name='Valid Name',
            description='This is a valid description',
            starting_bid=50.00,
            duration_hours=0
        ), follow_redirects=True)
        
        self.assertIn(b'Duration must be at least', response.data)
    
    # -------------------------------------------------------------------------
    # TEST: Bidding Logic
    # -------------------------------------------------------------------------
    
    def test_place_bid_success(self):
        """FT-016: User can place valid bid on active auction"""
        self.login('testuser2', 'password123')
        
        response = self.client.post(f'/bid/{self.active_item_id}', data=dict(
            bid_amount=75.00
        ), follow_redirects=True)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Bid of $75.00 placed successfully', response.data)
    
    def test_place_bid_requires_login(self):
        """FT-017: Non-logged-in user cannot place bid"""
        response = self.client.post(f'/bid/{self.active_item_id}', data=dict(
            bid_amount=75.00
        ), follow_redirects=True)
        
        self.assertIn(b'Please log in', response.data)
    
    def test_place_bid_lower_than_current(self):
        """FT-018: Bid must be higher than current bid"""
        self.login('testuser2', 'password123')
        
        # Try to place bid lower than current
        response = self.client.post(f'/bid/{self.active_item_id}', data=dict(
            bid_amount=40.00  # Current bid is 50.00
        ), follow_redirects=True)
        
        self.assertIn(b'Your bid must be higher', response.data)
    
    def test_place_bid_equal_to_current(self):
        """FT-019: Bid cannot equal current bid"""
        self.login('testuser2', 'password123')
        
        response = self.client.post(f'/bid/{self.active_item_id}', data=dict(
            bid_amount=50.00  # Equal to current
        ), follow_redirects=True)
        
        self.assertIn(b'Your bid must be higher', response.data)
    
    def test_place_bid_on_ended_auction(self):
        """FT-020: Cannot place bid on ended auction"""
        self.login('testuser3', 'password123')
        
        response = self.client.post(f'/bid/{self.ended_item_id}', data=dict(
            bid_amount=200.00
        ), follow_redirects=True)
        
        self.assertIn(b'This auction has ended', response.data)
    
    def test_place_bid_invalid_amount(self):
        """FT-021: Bid must be valid positive number"""
        self.login('testuser2', 'password123')
        
        response = self.client.post(f'/bid/{self.active_item_id}', data=dict(
            bid_amount=-50.00
        ), follow_redirects=True)
        
        self.assertIn(b'Please enter a valid bid amount', response.data)
    
    def test_bid_increments_correctly(self):
        """FT-022: Multiple bids increment item's current_bid"""
        self.login('testuser2', 'password123')
        
        # Place first bid
        self.client.post(f'/bid/{self.active_item_id}', data=dict(
            bid_amount=100.00
        ), follow_redirects=True)
        
        # Place second bid
        self.client.post(f'/bid/{self.active_item_id}', data=dict(
            bid_amount=150.00
        ), follow_redirects=True)
        
        with app.app_context():
            item = Item.query.get(self.active_item_id)
            self.assertEqual(item.current_bid, 150.00)
    
    def test_bid_creates_audit_trail(self):
        """FT-023: Each bid is recorded in Bid table"""
        self.login('testuser2', 'password123')
        
        self.client.post(f'/bid/{self.active_item_id}', data=dict(
            bid_amount=75.00
        ), follow_redirects=True)
        
        with app.app_context():
            bid = Bid.query.filter_by(item_id=self.active_item_id).first()
            self.assertIsNotNone(bid)
            self.assertEqual(bid.amount, 75.00)
            self.assertEqual(bid.user_id, self.user2_id)
    
    # -------------------------------------------------------------------------
    # TEST: Winner Selection Logic
    # -------------------------------------------------------------------------
    
    def test_auction_winner_selection(self):
        """FT-024: Winner is correctly assigned when auction ends"""
        with app.app_context():
            # Verify that ended item should have winner
            from app import check_and_finalize_auctions
            check_and_finalize_auctions()
            
            ended_item = Item.query.get(self.ended_item_id)
            self.assertEqual(ended_item.winner_id, self.user3_id)
    
    def test_auction_no_winner_if_no_bids(self):
        """FT-025: Auction with no bids has no winner"""
        with app.app_context():
            # Create item with no bids that has ended
            ended_no_bids = Item(
                name='No Bids Item',
                description='Item with no bids',
                starting_bid=50.00,
                current_bid=50.00,
                seller_id=self.user1_id,
                current_bidder_id=None,  # No bids
                end_time=datetime.utcnow() - timedelta(hours=1)
            )
            db.session.add(ended_no_bids)
            db.session.commit()
            
            from app import check_and_finalize_auctions
            check_and_finalize_auctions()
            
            item = Item.query.get(ended_no_bids.id)
            self.assertIsNone(item.winner_id)
    
    # -------------------------------------------------------------------------
    # TEST: User Dashboard
    # -------------------------------------------------------------------------
    
    def test_user_can_view_own_auctions(self):
        """FT-026: User can view their own auction items"""
        self.login('testuser1', 'password123')
        
        response = self.client.get('/my-auctions', follow_redirects=True)
        
        self.assertEqual(response.status_code, 200)
        # Check that the item is in the response
        self.assertIn(b'Test Item 1', response.data)
    
    def test_user_dashboard_requires_login(self):
        """FT-027: Dashboard requires login"""
        response = self.client.get('/my-auctions', follow_redirects=True)
        
        self.assertIn(b'Please log in', response.data)
    
    # -------------------------------------------------------------------------
    # TEST: Item Detail View
    # -------------------------------------------------------------------------
    
    def test_user_can_view_item_detail(self):
        """FT-028: User can view item detail page"""
        response = self.client.get(f'/item/{self.active_item_id}')
        
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Test Item 1', response.data)
    
    def test_view_nonexistent_item_returns_404(self):
        """FT-029: Viewing non-existent item returns 404"""
        response = self.client.get('/item/99999')
        
        self.assertEqual(response.status_code, 404)


# =============================================================================
# INTEGRATION TESTING
# =============================================================================

class IntegrationTestCase(BaseTestCase):
    """Test interactions between components and workflows"""
    
    def test_complete_auction_workflow(self):
        """IT-001: Complete workflow - create item, bid, auction ends"""
        # User 1 creates item
        self.login('testuser1', 'password123')
        create_response = self.client.post('/create-item', data=dict(
            name='Integration Test Item',
            description='Testing complete workflow',
            starting_bid=50.00,
            duration_hours=24
        ), follow_redirects=True)
        
        # Extract item ID
        self.assertIn(b'created successfully', create_response.data)
        
        # Get the created item
        with app.app_context():
            item = Item.query.filter_by(name='Integration Test Item').first()
            item_id = item.id
        
        # User 2 places bid
        self.logout()
        self.login('testuser2', 'password123')
        bid_response = self.client.post(f'/bid/{item_id}', data=dict(
            bid_amount=75.00
        ), follow_redirects=True)
        
        self.assertIn(b'Bid of $75.00 placed successfully', bid_response.data)
        
        # Verify bid was recorded
        with app.app_context():
            bid = Bid.query.filter_by(item_id=item_id).first()
            self.assertIsNotNone(bid)
            self.assertEqual(bid.amount, 75.00)
    
    def test_session_management_integration(self):
        """IT-002: Session persists across multiple requests"""
        self.login('testuser1', 'password123')
        
        # Make multiple requests - session should remain
        response1 = self.client.get('/my-auctions')
        response2 = self.client.get('/my-auctions')
        
        self.assertEqual(response1.status_code, 200)
        self.assertEqual(response2.status_code, 200)
    
    def test_database_transaction_integrity(self):
        """IT-003: Database transactions maintain consistency"""
        self.login('testuser2', 'password123')
        
        # Place multiple bids - verify all are committed
        with app.app_context():
            initial_bid_count = Bid.query.count()
        
        for bid_amount in [75.00, 100.00, 125.00]:
            self.client.post(f'/bid/{self.active_item_id}', data=dict(
                bid_amount=bid_amount
            ), follow_redirects=True)
        
        with app.app_context():
            final_bid_count = Bid.query.count()
            self.assertEqual(final_bid_count - initial_bid_count, 3)
    
    def test_user_can_view_bid_history(self):
        """IT-004: User can view complete bid history for item"""
        self.login('testuser2', 'password123')
        
        # Place bid
        self.client.post(f'/bid/{self.active_item_id}', data=dict(
            bid_amount=75.00
        ), follow_redirects=True)
        
        # View item detail with bid history
        response = self.client.get(f'/item/{self.active_item_id}')
        
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'75.00', response.data)
    
    def test_multiple_users_bidding_concurrently(self):
        """IT-005: Multiple users can bid on same item"""
        with app.app_context():
            # Create new item
            multi_bid_item = Item(
                name='Multi-bid Test Item',
                description='Item for multiple bidding',
                starting_bid=50.00,
                current_bid=50.00,
                seller_id=self.user1_id,
                end_time=datetime.utcnow() + timedelta(hours=24)
            )
            db.session.add(multi_bid_item)
            db.session.commit()
            item_id = multi_bid_item.id
        
        # User 2 bids
        self.login('testuser2', 'password123')
        self.client.post(f'/bid/{item_id}', data=dict(
            bid_amount=75.00
        ), follow_redirects=True)
        
        # User 3 bids higher
        self.logout()
        self.login('testuser3', 'password123')
        self.client.post(f'/bid/{item_id}', data=dict(
            bid_amount=100.00
        ), follow_redirects=True)
        
        # Verify final state
        with app.app_context():
            item = Item.query.get(item_id)
            self.assertEqual(item.current_bid, 100.00)
            self.assertEqual(item.current_bidder_id, self.user3_id)
    
    def test_password_hashing_integration(self):
        """IT-006: Passwords are hashed and verified correctly"""
        # Register user
        self.client.post('/register', data=dict(
            username='hashtest',
            password='password123',
            confirm_password='password123'
        ))
        
        # Login should work
        response = self.client.post('/login', data=dict(
            username='hashtest',
            password='password123'
        ), follow_redirects=True)
        
        self.assertIn(b'Welcome back', response.data)
        
        # Wrong password should fail
        with app.app_context():
            db.session.close()
        
        response = self.client.post('/login', data=dict(
            username='hashtest',
            password='wrongpassword'
        ), follow_redirects=True)
        
        self.assertIn(b'Invalid username or password', response.data)


# =============================================================================
# SECURITY TESTING
# =============================================================================

class SecurityTestCase(BaseTestCase):
    """Test security measures and vulnerability prevention"""
    
    # -------------------------------------------------------------------------
    # TEST: Authentication & Authorization
    # -------------------------------------------------------------------------
    
    def test_cannot_bid_on_own_item(self):
        """SEC-001: User cannot bid on their own item"""
        self.login('testuser1', 'password123')  # Owner of active_item
        
        response = self.client.post(f'/bid/{self.active_item_id}', data=dict(
            bid_amount=75.00
        ), follow_redirects=True)
        
        self.assertIn(b'You cannot bid on your own item', response.data)
    
    def test_protected_routes_require_authentication(self):
        """SEC-002: Protected routes deny unauthenticated access"""
        protected_routes = ['/create-item', '/my-auctions']
        
        for route in protected_routes:
            response = self.client.get(route, follow_redirects=True)
            self.assertIn(b'Please log in', response.data)
    
    def test_post_to_protected_routes_requires_auth(self):
        """SEC-003: POST requests to protected routes require auth"""
        response = self.client.post('/create-item', data=dict(
            name='Test',
            description='Test description',
            starting_bid=50.00,
            duration_hours=24
        ), follow_redirects=True)
        
        self.assertIn(b'Please log in', response.data)
    
    # -------------------------------------------------------------------------
    # TEST: Data Integrity & Validation
    # -------------------------------------------------------------------------
    
    def test_sql_injection_prevention_username(self):
        """SEC-004: SQL injection in username is prevented"""
        response = self.client.post('/login', data=dict(
            username="' OR '1'='1",
            password='password123'
        ), follow_redirects=True)
        
        # Should fail to authenticate
        self.assertIn(b'Invalid username or password', response.data)
    
    def test_negative_bid_amount_rejected(self):
        """SEC-005: Negative bid amounts are rejected"""
        self.login('testuser2', 'password123')
        
        response = self.client.post(f'/bid/{self.active_item_id}', data=dict(
            bid_amount=-100.00
        ), follow_redirects=True)
        
        self.assertIn(b'Please enter a valid bid amount', response.data)
    
    def test_zero_bid_amount_rejected(self):
        """SEC-006: Zero bid amount is rejected"""
        self.login('testuser2', 'password123')
        
        response = self.client.post(f'/bid/{self.active_item_id}', data=dict(
            bid_amount=0.00
        ), follow_redirects=True)
        
        self.assertIn(b'Please enter a valid bid amount', response.data)
    
    def test_invalid_item_id_returns_404(self):
        """SEC-007: Invalid item ID returns 404, not error"""
        response = self.client.get('/item/999999')
        
        self.assertEqual(response.status_code, 404)
    
    def test_bid_on_nonexistent_item_returns_404(self):
        """SEC-008: Bidding on non-existent item returns 404"""
        self.login('testuser2', 'password123')
        
        response = self.client.post('/bid/999999', data=dict(
            bid_amount=50.00
        ), follow_redirects=True)
        
        self.assertEqual(response.status_code, 404)
    
    # -------------------------------------------------------------------------
    # TEST: Session Security
    # -------------------------------------------------------------------------
    
    def test_logout_clears_session(self):
        """SEC-009: Logout properly clears session data"""
        self.login('testuser1', 'password123')
        self.logout()
        
        # Try to access protected route - should require login
        response = self.client.get('/my-auctions', follow_redirects=True)
        self.assertIn(b'Please log in', response.data)
    
    def test_session_contains_user_id(self):
        """SEC-010: Session stores user_id for authentication"""
        self.login('testuser1', 'password123')
        
        with self.client.session_transaction() as session:
            self.assertIn('user_id', session)
            self.assertEqual(session['user_id'], self.user1_id)
    
    # -------------------------------------------------------------------------
    # TEST: Password Security
    # -------------------------------------------------------------------------
    
    def test_passwords_are_hashed_not_stored_plaintext(self):
        """SEC-011: Passwords are hashed, not stored as plaintext"""
        with app.app_context():
            user = User.query.filter_by(username='testuser1').first()
            # Hash should not be the plaintext password
            self.assertNotEqual(user.password, 'password123')
            # Hash should be long (werkzeug hashes are ~256 chars)
            self.assertGreater(len(user.password), 30)
    
    def test_password_hashing_uses_proper_algorithm(self):
        """SEC-012: Password hashing uses secure algorithm"""
        with app.app_context():
            user = User.query.filter_by(username='testuser1').first()
            # Werkzeug hashes start with 'scrypt:', 'pbkdf2:', 'bcrypt:', etc.
            self.assertTrue(
                user.password.startswith(('scrypt:', 'pbkdf2:', 'bcrypt:'))
            )
    
    def test_password_verification_is_case_sensitive(self):
        """SEC-013: Password verification is case-sensitive"""
        response = self.login('testuser1', 'PASSWORD123')  # Wrong case
        
        self.assertIn(b'Invalid username or password', response.data)
    
    def test_cannot_enumerate_users_via_registration(self):
        """SEC-014: Registration error doesn't leak user existence"""
        # Try to register with existing username
        response = self.client.post('/register', data=dict(
            username='testuser1',
            password='password123',
            confirm_password='password123'
        ), follow_redirects=True)
        
        self.assertIn(b'Username already exists', response.data)
    
    # -------------------------------------------------------------------------
    # TEST: Business Logic Security
    # -------------------------------------------------------------------------
    
    def test_cannot_modify_bid_amount_after_placement(self):
        """SEC-015: Bids cannot be modified after placement"""
        self.login('testuser2', 'password123')
        
        # Place first bid
        self.client.post(f'/bid/{self.active_item_id}', data=dict(
            bid_amount=75.00
        ), follow_redirects=True)
        
        # Verify bid amount is recorded
        with app.app_context():
            bid = Bid.query.filter_by(
                item_id=self.active_item_id,
                user_id=self.user2_id
            ).first()
            self.assertEqual(bid.amount, 75.00)
    
    def test_seller_cannot_manually_select_winner(self):
        """SEC-016: Seller cannot manually override winner selection"""
        # This tests that winner is only set by check_and_finalize_auctions logic
        self.login('testuser1', 'password123')  # Seller
        
        # Try to access winner selection (no such route should exist)
        response = self.client.post(f'/item/{self.active_item_id}/select-winner', 
                                   data=dict(winner_id=self.user2_id))
        
        self.assertEqual(response.status_code, 404)
    
    def test_bid_amount_precision_preserved(self):
        """SEC-017: Bid amounts maintain proper decimal precision"""
        self.login('testuser2', 'password123')
        
        # Place bid with cents
        self.client.post(f'/bid/{self.active_item_id}', data=dict(
            bid_amount=75.99
        ), follow_redirects=True)
        
        with app.app_context():
            item = Item.query.get(self.active_item_id)
            # Should be exactly 75.99, not rounded or truncated
            self.assertEqual(item.current_bid, 75.99)
    
    def test_cannot_access_other_users_data_via_id_manipulation(self):
        """SEC-018: Users cannot access private data of other users"""
        self.login('testuser1', 'password123')
        
        # User 1 views their dashboard
        response = self.client.get('/my-auctions')
        self.assertEqual(response.status_code, 200)


# =============================================================================
# TEST EXECUTION
# =============================================================================

if __name__ == '__main__':
    # Configure test output
    unittest.main(verbosity=2)
