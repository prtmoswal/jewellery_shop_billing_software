import streamlit as st
import hashlib # For a simple hash of the password (not for production!)

# --- Configuration ---
# You would typically store these securely, e.g., in environment variables or a database
VALID_USERNAME = "user"
VALID_PASSWORD_HASH = hashlib.sha256("password123".encode()).hexdigest() # Hash "password123"

# --- Utility Functions ---
def hash_password(password):
    """Hashes a password using SHA256."""
    return hashlib.sha256(password.encode()).hexdigest()

def check_password(entered_password, stored_hash):
    """Checks if the entered password matches the stored hash."""
    return hash_password(entered_password) == stored_hash

# --- Streamlit App Functions ---

def login_page():
    """Displays the login form."""
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');
        body {
            font-family: 'Inter', sans-serif;
        }
        .stApp {
            background-color: #f0f2f6;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
        }
        # .login-container {
        #     background-color: red;
        #     padding: 1rem 2.5rem 2.5rem 2.5rem;
        #     border-radius: 0.75rem; /* rounded-xl */
        #     box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05); /* shadow-xl */
        #     width: 100%;
        #     max-width: 28rem; /* max-w-md */
        #     text-align: center;
        }
        .stTextInput > div > div > input {
            border-radius: 0.5rem; /* rounded-lg */
            border: 1px solid #d1d5db; /* border-gray-300 */
            padding: 0.75rem 1rem; /* px-4 py-3 */
            width: 100%;
            font-size: 1rem; /* text-base */
            margin-bottom: 1rem;
        }
        .stButton > button {
            background-color: #4f46e5; /* indigo-600 */
            color: white;
            padding: 0.75rem 1.5rem; /* py-3 px-6 */
            border-radius: 0.5rem; /* rounded-lg */
            font-weight: 600; /* font-semibold */
            width: 100%;
            transition: background-color 0.2s ease-in-out;
            border: none;
            cursor: pointer;
        }
        .stButton > button:hover {
            background-color: #4338ca; /* indigo-700 */
        }
        .stMarkdown h2 {
            font-size: 1.875rem; /* text-3xl */
            font-weight: 700; /* font-bold */
            color: #1f2937; /* gray-900 */
            margin-bottom: 1.5rem;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    #st.markdown('<div class="login-container">', unsafe_allow_html=True)
    st.markdown("<h2>Login to Your App</h2>", unsafe_allow_html=True)

    username = st.text_input("Username", key="username_input")
    password = st.text_input("Password", type="password", key="password_input")

    if st.button("Login", key="login_button"):
        if check_password(password, VALID_PASSWORD_HASH) and username == VALID_USERNAME:
            st.session_state.logged_in = True
            st.session_state.username = username
            st.success("Logged in successfully!")
            st.rerun() # Rerun to show the main app
        else:
            st.error("Invalid username or password.")
    st.markdown('</div>', unsafe_allow_html=True)
