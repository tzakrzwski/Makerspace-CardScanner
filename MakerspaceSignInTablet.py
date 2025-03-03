import customtkinter as ctk #graphics
from PIL import Image #graphics
import random #planned to add random effects and sounds on scan in for fun
import webbrowser #to open browser
import subprocess #to open other script
import time
import threading
import re
import CardReaderMakerspace
from MakerspaceLoginRecord import LoginEntry


orange_color = "#F56600" # Override the color theme to use the clemson orange

'''
Class for handling GUI elements, triggers, etc
'''
class UserInterface():

    def __init__(self, root: ctk.CTk):
        
        self.main_window = root # Root window / parent obejct for sign in; Includes main screen
        self.main_window_entry = None # Main entry field
        self.new_user_window = None # New user register window
        self.new_user_entry = None # Entry field for new user (username)
        self.welcome_window = None # Returning user window

        # Complete setup of root window
        self.setup_root()


    '''
    Starts the mainloop for the GUI
    '''
    def start(self):
        self.main_window.mainloop()


    '''
    Callback function to set the entry focus whenever the window is "configured" (aka switched to, loaded, etc)
    '''
    def set_focus(self, e):
        self.main_window_entry.focus()


    '''
    Format main window during initalization

    '''
    def setup_root(self):

        # Set window params: (Title, fullscreen)
        self.main_window.title("Sign In")
        self.main_window.attributes('-fullscreen', True)

        # Graphic Elements
        
        # Load and scale the background image
        screen_width = self.main_window.winfo_screenwidth()
        screen_height = self.main_window.winfo_screenheight()
        resized_image = Image.open("BackgroundTablet.png").resize((screen_width,screen_height), Image.NEAREST)
        
        # Create a label to display the image, set as the canvas background
        bg_label = ctk.CTkLabel(self.main_window, image=ctk.CTkImage(light_image=resized_image, size=(screen_width,screen_height)))
        bg_label.place(x=0, y=0, relwidth=1, relheight=1)

        # Create a text entry box with rounded corners and border
        entry_frame = ctk.CTkFrame(self.main_window, fg_color=orange_color, border_width=0)
        entry_frame.place(relx=0.5, rely=0.5, anchor='center')

        # Apply modern styling to the Entry widget
        self.main_window_entry = ctk.CTkEntry(entry_frame, font=("Vendeta", 30), justify='center', border_width=0, width=screen_width/4)
        self.main_window_entry.pack(ipadx=10, ipady=5, padx=10, pady=5)

        # Bindings

        # Bind the Enter key to process input
        self.main_window_entry.bind('<Return>', lambda e: handle_entry(e, self))

        # Exit the program when pressing 'Esc'
        self.main_window.bind('<Escape>', clean_up)

        # Set the focus when window is configured
        self.main_window.bind('<Configure>', self.set_focus)


    ''' 
    Opens a window for new user to enter their information (username)
    Returns: 1 if window opened, 0 if already opened
    '''
    def open_new_user_window(self):

        # Check if window is already exsists
        if self.new_user_window == None:

            # Create new window
            self.new_user_window = ctk.CTkToplevel(self.root_window)
            
            # Set window params: (Title, fullscreen, onTop)
            self.new_user_window.title("Username Entry")
            self.new_user_window.attributes("-fullscreen", True)
            self.new_user_window.attributes('-topmost', True)

            # Graphic Elements

            # Title label
            title_label = ctk.CTkLabel(self.new_user_window, text="Welcome to the Makerspace! Enter Your Clemson Username:", font=("Arial", 24), text_color=orange_color)
            title_label.pack(pady=30)

            # Label for username
            label = ctk.CTkLabel(master=root, text="The part before the @clemson.edu", font=("Arial", 18))
            label.pack(pady=10)

            # Entry for username
            self.new_user_entry = ctk.CTkEntry(master=root, width=300, height=50, placeholder_text="Enter username", font=("Arial", 16))
            self.new_user_entry.pack(pady=10)

            # Submit button with the orange color
            submit_button = ctk.CTkButton(master=root, text="Submit", command=submit_username, width=200, height=50, fg_color=orange_color, hover_color="#FF7800", font=("Arial", 18))
            submit_button.pack(pady=40)

            # Bindings

            # Bind the Enter key to submit the form
            root.bind('<Return>', submit_username)

            return 1

        else:
            # Window already exsists
            # Unhide window
            self.new_user_window.state('normal')

            # Set window and entry focus
            self.new_user_window.focus()
            self.new_user_entry.focus()

            return 0


    '''
    Opens a window to welcome the user
    '''
    def open_welcome_window(self):
        pass

'''
Handle input from the main entry
'''
def handle_entry(e, interface:UserInterface):

    # Get string from input field
    user_input = interface.main_window_entry.get()

    # Clear the entry box
    interface.main_window_entry.delete(0, ctk.END)  


    # Check if email entered
    if re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+.[a-zA-Z]{2,}$", user_input):
        print(f"Email entered: {user_input}")

        # Check if email is clemson.edu or g.clemson.edu
        if "clemson.edu" in user_input:

            # Clemson email, so strip the ending and treat as a username
            user_input = user_input.split('@',1)[0]

        # Regular email (most likely a VIP)
        else:
            print(f"Email entered: {user_input}")

            # Create login entry from email
            login = LoginEntry(username=user_input, bypass_registration=1)

            return 1


    # Check if input is username
    if re.match(r"^[a-z0-9_\-]+$", user_input):
        print(f"Username entered: {user_input}")

        # Create login entry with the username
        login = LoginEntry(username=user_input)

        # Check if the user is registered
        if login.is_registered():

            # Display welcome screen
            interface.open_welcome_window()

        # TODO -> Request info from user that we are missing
        else:
            print("User entered username, but are not registered")
            pass


    # Check if the input is User Scan
    if user_input.isdigit() and len(user_input) == 6:
        print(f"Hardware ID entered: {user_input}")

        # Create login entry with the user id
        login = LoginEntry(hardware_id=user_input)

        # Check if user is new
        # TODO: Functional Call to check if new
        if login.new_user:
            print("New user detected. Prompting for username.")
            
            # Open window for new user registration
            interface.open_new_user_window()

        else:


        if 'hardware_id' in globals():
            CardReaderMakerspace.main(hardware_id)
        elif 'username' in globals():
            CardReaderMakerspace.main(username)
        else:
            pass

        return 1


    # Invalid input
    else:
        print(f"Invalid input {user_input}")
        return 0


'''
Calls when the main window is escaped; Make sure to close processes gracefully
'''
def clean_up(e):

    # End the UI process
    root.destroy()


"""
Set-up
"""

# Set GUI parameters
ctk.set_appearance_mode("dark")  # Modes: "dark" or "light"
ctk.set_default_color_theme("blue")  # We will override the default colors manually

# Create the main window and user interface
root = ctk.CTk()
UI = UserInterface(root)


"""
Main Loop
"""


UI.start()

print("End of Program?")