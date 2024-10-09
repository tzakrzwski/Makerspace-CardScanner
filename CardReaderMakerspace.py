import sys
import customtkinter as ctk
from openpyxl import load_workbook
import tkinter as tk
from tkinter import simpledialog, Canvas, messagebox
from PIL import Image, ImageTk 
from screeninfo import get_monitors
import pygetwindow as gw
from datetime import datetime
from __main__ import *
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

#Path to excel sheet
file_path = "hardware_users.xlsx"
sheet_name = "Scans"
sheet2_name ="Users"

def load_excel():
    # Load the workbook and sheet
    workbook = load_workbook(filename=file_path)
    sheet = workbook[sheet_name] #this is a bit redundant but it works
    sheet2 = workbook[sheet2_name] 
    return workbook, sheet, sheet2

def load_hardware_ids(sheet):
    hardware_dict = {}
    # Load the hardware IDs and usernames into a dictionary
    for row in sheet.iter_rows(min_row=2, max_row=sheet.max_row, values_only=True):
        hardware_dict[str(row[0])] = row[1]  # Hardware ID as the key, username as the value

#def find_hardware_id(hardware_dict, hardware_id):
    # Perform a quick lookup in the dictionary
    #return hardware_dict.get(str(hardware_id))  # This is O(1)

def find_hardware_id(sheet2, hardware_id):
    # Loop through the rows starting from row 2 to skip headers (if any)
    for row in sheet2.iter_rows(min_row=2, max_row=sheet2.max_row, values_only=True):
        if str(row[1]) == str(hardware_id):  # Compare hardware_id in column B (index 1)
            return row[0]  # Return the username from column A (index 0)
    
    return None  # Return None if not found
def find_userdata(hardware_id,sheet2):
    # Loop through the rows starting from row 2 to skip headers
    for row in sheet2.iter_rows(min_row=2, max_row=sheet2.max_row, values_only=True):
        if str(row[1]) == str(hardware_id):  # Compare hardware_id in column B (index 1)
            # Return first_name (D, index 3), last_name (E, index 4), major (F, index 5)
            first_name = row[3]  # Column D (index 3 in zero-based)
            last_name = row[4]   # Column E (index 4 in zero-based)
            major = row[5]       # Column F (index 5 in zero-based)
            return first_name, last_name, major
    
    return None, None, None  # Return None for all if not found

def add_user_to_sheet(sheet, hardware_id, username,first_name,last_name,major):
    wb = load_workbook(filename=file_path)
    scans_sheet = wb[sheet_name]
    users_sheet = wb[sheet2_name]
    # Add the hardware ID and username to the next available row
    # First, update the "Users" sheet if a matching hardware_id is found
    user_updated = False
    for row in users_sheet.iter_rows(min_row=2, values_only=False):  # Skip header row
        cell_hardware_id = row[1].value  # Column B in "Users"
        if cell_hardware_id == hardware_id:
            # Update first name, last name, and major in columns D, E, and F
            row[3].value = first_name  # Column D
            row[4].value = last_name   # Column E
            row[5].value = major       # Column F
            user_updated = True
            break  # Stop after finding and updating the row
    now = datetime.now()
    timestamp = now.timestamp()
    scans_sheet.append([hardware_id, username, timestamp])
    print(f"add_user_to_sheet has ran")

    # Save the workbook after making changes
    wb.save(file_path)
    
    if user_updated:
        print(f"User {first_name} {last_name}'s information updated in 'Users' sheet.")
    else:
        print(f"New scan added for {username} in 'Scans' sheet.")


def scrape_user(username):
    # Set up Selenium with headless Chrome
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Run Chrome in headless mode
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")

        # Set up the driver
        driver = webdriver.Chrome(options=chrome_options)

        # Create da URL using username, change this id the directory changes url
        url = f"https://my.clemson.edu/#/directory/person/{username}"

        # Load da page
        driver.get(url)

        # Wait for the full name element to appear
        try:
            WebDriverWait(driver, 1).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '.personView .primaryInfo h2'))
            )
        except TimeoutException:
            print(f"Timeout while waiting for the element on the page for {username}.")
            driver.quit()
            return username, None, None  # Default values if element not found
        except Exception as e:
            print(f"Error during page load: {e}")
            driver.quit()
            return username, None, None  # Default values if there's an error
        # Get da page
        page_source = driver.page_source

        # Parse the page with BeautifulSoup
        soup = BeautifulSoup(page_source, 'html.parser')

        #Find da Name
        full_name_element = soup.select_one('.personView .primaryInfo h2') 
        if full_name_element:
            full_name = full_name_element.get_text().strip()

            # Split the full name by spaces
            name_parts = full_name.split()

            # Store the first name and last name (ignore middle name if present)
            first_name = name_parts[0]  # The first part of the name
            last_name = name_parts[-1]  # The last part of the name, if they have like a number or sr. or something after their last name itll fuck it up but it doesn't matter because we don't really need the last name that badly anyways
        else:
            first_name, last_name = None, None
            #Find major

        major_element = soup.select_one('.personView .primaryInfo .data p')
        if major_element:
            major = major_element.get_text().strip()
        else:
            major = None
        # Print the scraped information
        print(f"First Name: {first_name}")
        print(f"Last Name: {last_name}")
        print(f"Major: {major}")

        # Close the driver
        driver.quit()
        return first_name, last_name, major

def make_fullscreen_on_top(root):
    root.attributes('-fullscreen', True)
    root.attributes('-topmost', True)


def show_welcome_popup(root, username, first_name):
    # Set the background image

    image = Image.open("background.png")  # Replace with your image file
    bg_image = ImageTk.PhotoImage(image)
    root.bg_image = bg_image  # Keep a reference to avoid garbage collection
    # Create a label for the background
    background_label = tk.Label(root, image=bg_image)
    background_label.place(relwidth=1, relheight=1)  # Stretch to fit window
    
    # Add a welcome message
    if first_name == None:
        first_name = username
    message = f"Welcome back, {first_name}!"
    message_label = tk.Label(root, text=message, font=("Helvetica", 36, "bold"), fg="white", bg="black")
    message_label.place(relx=0.5, rely=0.5, anchor="center")  # Center the message

    # Load and place the logo below the text
    logo_image = Image.open("LogoBW.png")  # Replace with your logo image file
    logo_image = logo_image.resize((508, 128))  # Resize if needed
    logo_photo = ImageTk.PhotoImage(logo_image)

    logo_label = tk.Label(root, image=logo_photo)
    logo_label.place(relx=0.5, rely=0.7, anchor="center")
    root.after(3000, root.quit)  # Close the window after 3 seconds


def close_on_escape(event):
    """Function to close the program when the Escape key is pressed."""
    print("Escape key pressed. Exiting program...")
    sys.exit()  # Exit the program

def prompt_for_username():
    # Simple dialog to ask for a username
    root = tk.Tk()
    root.withdraw()  # Hide the main window
    def is_valid_username(entered_username):
        """Validate the username based on the provided rules."""
        if not entered_username.strip():
            return False, "Username cannot be blank."
        
        if entered_username.isdigit():
            return False, "Username cannot be all numbers."
        
        if "@" in entered_username and "." in entered_username:
            return False, "Username cannot be an email address."
        
        return True, "Valid username."
    
    def submit_username(event=None):
        """Check the username and store it if valid. Allow event for Enter key binding."""
        entered_username = entry.get()
        valid, message = is_valid_username(entered_username)
        
        if valid:
            nonlocal username  # Declare nonlocal to update username within the nested function
            username = entered_username  # Store the valid username
            root.quit()  # Optionally close the window after successful submission
        else:
            messagebox.showerror("Error", message)
    
    # Set up the username variable to hold the result
    username = None
    
    # Initialize the main window
    ctk.set_appearance_mode("dark")  # Modes: "dark" or "light"
    ctk.set_default_color_theme("blue")  # We will override the default colors manually
    
    root = ctk.CTk()
    root.title("Username Entry")
    root.geometry("1000x600")  # Setting a larger window size
    
    # Override the color theme to use the specified orange
    orange_color = "#F56600"
    
    # Title label
    title_label = ctk.CTkLabel(master=root, text="Welcome to the Makerspace! Enter Your Clemson Username:", font=("Arial", 24), text_color=orange_color)
    title_label.pack(pady=30)
    
    # Create a label and entry for the username
    label = ctk.CTkLabel(master=root, text="The part before the @clemson.edu", font=("Arial", 18))
    label.pack(pady=10)
    
    entry = ctk.CTkEntry(master=root, width=300, height=50, placeholder_text="Enter username", font=("Arial", 16))
    entry.pack(pady=10)
    
    # Create a submit button with the orange color
    submit_button = ctk.CTkButton(master=root, text="Submit", command=submit_username, width=200, height=50, fg_color=orange_color, hover_color="#FF7800", font=("Arial", 18))
    submit_button.pack(pady=40)
    
    # Bind the Enter key to submit the form
    root.bind('<Return>', submit_username)  # Bind Enter (Return) key to the submit function
    
    # Start the application loop
    root.mainloop()
    # Return the username after the window closes
    return username

# Example usage in the larger script:
# final_username = get_username()
    

    #username = simpledialog.askstring("Input", "Please enter your username:")
    #return username

def main():

    hardware_id = sys.argv[1] #This gets the hardware ID from the gloabl system variables as defined from the other script to pass along the variables.
    workbook,sheet,sheet2 = load_excel()
    username = find_hardware_id(sheet2, hardware_id)
    first_name=None
    root = tk.Tk()
    root.withdraw()  # Hide the root window initially
    # Bind the Escape key to close the program
    root.bind("<Escape>", close_on_escape)

    if username != None:
        print(f"User found: {username}")
        first_name,last_name,major = find_userdata(hardware_id, sheet2)
        show_welcome_popup(root,username,first_name)
        root.deiconify()  # Show the window
        make_fullscreen_on_top(root)
        root.mainloop()
    else:
        print("New user detected. Prompting for username.")
        username = prompt_for_username()
        #generic_welcome(username)
        first_name, last_name, major = scrape_user(username)
        add_user_to_sheet(sheet, hardware_id, username,first_name,last_name,major)
        workbook.save(file_path)
        print(f"User {username} added to sheet.")
            
    
if __name__ == "__main__":
    main()