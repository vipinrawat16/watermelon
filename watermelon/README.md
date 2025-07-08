# WaterMelon Login Application 🍉

A secure Flask-based login application with user authentication and registration.

## Features

- ✅ Secure user authentication with password hashing
- ✅ User registration system
- ✅ Flash message notifications
- ✅ SQLite database with SQLAlchemy ORM
- ✅ Responsive design with custom CSS
- ✅ Session management
- ✅ Clean and modern UI

## Project Structure

```
watermelon/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── test_db.py            # Database testing script
├── README.md             # This file
├── instance/
│   └── login_users.db    # SQLite database
├── templates/
│   ├── login.html        # Login page
│   ├── register.html     # Registration page
│   └── welcome.html      # Welcome page after login
└── static/
    ├── style.css         # Custom CSS styles
    └── watermelon_tab_img.png  # Favicon
```

## Installation & Setup

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the Application**:
   ```bash
   python app.py
   ```

3. **Access the Application**:
   Open your browser and go to: `http://localhost:5000`

## Test Users

The application comes with pre-configured test users:

| Username  | Password   |
|-----------|------------|
| admin     | admin123   |
| user1     | password1  |
| testuser  | test123    |
| john_doe  | john123    |

## Usage

### Login
1. Go to `http://localhost:5000`
2. Enter your username and password
3. Click "Login"

### Register New User
1. Go to `http://localhost:5000`
2. Click "Register here"
3. Enter a new username and password
4. Click "Register"
5. You'll be redirected to login with your new account

### Logout
- Click the "Logout" button on the welcome page

## Testing Database

Run the database test script to verify connectivity:

```bash
python test_db.py
```

## Security Features

- **Password Hashing**: Uses Werkzeug's secure password hashing
- **Session Management**: Secure session handling with Flask
- **Input Validation**: Form validation and error handling
- **Flash Messages**: User-friendly error and success notifications

## Development Notes

- The application runs in debug mode for development
- Database is automatically created on first run
- Static files are served by Flask
- Templates use Jinja2 templating engine

## Files Cleaned Up

✅ Removed all Django-related files and directories
✅ Removed old SQL script files
✅ Organized project structure properly

## Customization

- Modify `static/style.css` to change the appearance
- Update templates in `templates/` directory for UI changes
- Modify `app.py` for functionality changes

---

**Happy coding! 🍉**
