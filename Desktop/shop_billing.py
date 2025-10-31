import mysql.connector
import customtkinter as ctk
from tkinter import ttk, messagebox
import datetime

# --- Matplotlib Imports for Graphing ---
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# --- DATABASE CONFIGURATION ---
# !!! IMPORTANT: UPDATE THESE DETAILS FOR YOUR MYSQL SERVER !!!
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root', # or your specific user
    'password': '5603', # your MySQL password
    'database': 'society_store' # the name of the database to use
}

def get_db_connection():
    """Establishes and returns a MySQL database connection."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except mysql.connector.Error as err:
        messagebox.showerror("Database Connection Error", f"Error: {err}\nPlease check your DB_CONFIG in the code.")
        return None

def setup_database():
    """Connects to MySQL and creates the database and tables if they don't exist."""
    try:
        # Connect without specifying a database first to create it
        initial_conn = mysql.connector.connect(
            host=DB_CONFIG['host'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password']
        )
        cursor = initial_conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_CONFIG['database']}")
        cursor.execute(f"USE {DB_CONFIG['database']}")
        print(f"Database '{DB_CONFIG['database']}' is ready.")
        initial_conn.close()

        # Now connect to the specific database to create tables
        conn = get_db_connection()
        if not conn: return
        
        cursor = conn.cursor()

        commands = [
            """
            CREATE TABLE IF NOT EXISTS ShopInfo (
                id INT PRIMARY KEY,
                shop_name VARCHAR(255) DEFAULT 'Your Shop Name',
                address VARCHAR(255) DEFAULT 'Your Address',
                phone VARCHAR(50) DEFAULT 'Your Phone Number',
                gst_number VARCHAR(50) DEFAULT 'Your GSTIN',
                current_gst_rate DECIMAL(5, 2) DEFAULT 18.00
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS Flats (
                flat_id INT AUTO_INCREMENT PRIMARY KEY,
                flat_number VARCHAR(50) NOT NULL UNIQUE,
                resident_name VARCHAR(255),
                credit_balance DECIMAL(10, 2) NOT NULL DEFAULT 0.00
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS Products (
                product_id INT AUTO_INCREMENT PRIMARY KEY,
                barcode VARCHAR(255) UNIQUE,
                name VARCHAR(255) NOT NULL,
                price DECIMAL(10, 2) NOT NULL,
                stock_quantity INT NOT NULL DEFAULT 0
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS Sales (
                sale_id INT AUTO_INCREMENT PRIMARY KEY,
                sale_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_amount DECIMAL(10, 2) NOT NULL,
                gst_amount DECIMAL(10, 2) NOT NULL,
                payment_method VARCHAR(50) NOT NULL,
                flat_id INT,
                FOREIGN KEY (flat_id) REFERENCES Flats (flat_id)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS SaleItems (
                sale_item_id INT AUTO_INCREMENT PRIMARY KEY,
                sale_id INT NOT NULL,
                product_id INT NOT NULL,
                quantity_sold INT NOT NULL,
                price_at_sale DECIMAL(10, 2) NOT NULL,
                FOREIGN KEY (sale_id) REFERENCES Sales(sale_id),
                FOREIGN KEY (product_id) REFERENCES Products(product_id)
            );
            """
        ]

        for command in commands:
            cursor.execute(command)

        # Add default ShopInfo if it doesn't exist
        cursor.execute("SELECT COUNT(*) FROM ShopInfo")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO ShopInfo (id) VALUES (1)")
        
        # Add sample flats for testing if none exist
        cursor.execute("SELECT COUNT(*) FROM Flats")
        if cursor.fetchone()[0] == 0:
            sample_flats = [(f"A-{101+i}", f"Resident {i+1}") for i in range(10)]
            cursor.executemany("INSERT INTO Flats (flat_number, resident_name) VALUES (%s, %s)", sample_flats)

        conn.commit()
        cursor.close()
        conn.close()
        print("Database setup complete.")

    except mysql.connector.Error as err:
        messagebox.showerror("Database Setup Error", f"Error: {err}")


# --- DIALOG FOR ADDING/EDITING PRODUCTS ---
class ProductDialog(ctk.CTkToplevel):
    def __init__(self, master, product_info=None):
        super().__init__(master)
        
        self.product_info = product_info
        self.result = None

        self.title("Add New Product" if not product_info else "Edit Product")
        self.geometry("400x300")
        self.transient(master)
        self.grab_set()

        self.name_label = ctk.CTkLabel(self, text="Product Name:")
        self.name_label.pack(pady=(10,0))
        self.name_entry = ctk.CTkEntry(self, width=250)
        self.name_entry.pack()

        self.price_label = ctk.CTkLabel(self, text="Price:")
        self.price_label.pack(pady=(10,0))
        self.price_entry = ctk.CTkEntry(self, width=250)
        self.price_entry.pack()

        self.stock_label = ctk.CTkLabel(self, text="Stock Quantity:")
        self.stock_label.pack(pady=(10,0))
        self.stock_entry = ctk.CTkEntry(self, width=250)
        self.stock_entry.pack()

        if product_info:
            self.name_entry.insert(0, product_info['name'])
            self.price_entry.insert(0, str(product_info['price']))
            self.stock_entry.insert(0, str(product_info['stock_quantity']))

        self.save_button = ctk.CTkButton(self, text="Save", command=self.save)
        self.save_button.pack(pady=20)

    def save(self):
        name = self.name_entry.get()
        price = self.price_entry.get()
        stock = self.stock_entry.get()

        if not all([name, price, stock]):
            messagebox.showerror("Input Error", "All fields are required.", parent=self)
            return
        
        try:
            price = float(price)
            stock = int(stock)
        except ValueError:
            messagebox.showerror("Input Error", "Price must be a number and Stock must be an integer.", parent=self)
            return

        self.result = {'name': name, 'price': price, 'stock': stock}
        if self.product_info:
            self.result['id'] = self.product_info['product_id']
        
        self.destroy()


# --- INVENTORY MANAGEMENT WINDOW ---
class InventoryWindow(ctk.CTkToplevel):
    def __init__(self, master=None):
        super().__init__(master)
        self.title("Inventory Management")
        self.geometry("800x600")
        self.transient(master)
        self.grab_set()

        self.search_frame = ctk.CTkFrame(self)
        self.search_frame.pack(pady=10, padx=10, fill="x")
        
        self.search_entry = ctk.CTkEntry(self.search_frame, placeholder_text="Search by name...")
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.search_button = ctk.CTkButton(self.search_frame, text="Search", command=self.search_products)
        self.search_button.pack(side="left")

        self.tree_frame = ctk.CTkFrame(self)
        self.tree_frame.pack(pady=10, padx=10, fill="both", expand=True)

        columns = ("id", "name", "price", "stock")
        self.tree = ttk.Treeview(self.tree_frame, columns=columns, show="headings")
        self.tree.heading("id", text="ID")
        self.tree.heading("name", text="Name")
        self.tree.heading("price", text="Price")
        self.tree.heading("stock", text="Stock")
        self.tree.pack(fill="both", expand=True)
        
        self.tree.column("id", width=50)
        self.tree.column("name", width=300)

        self.button_frame = ctk.CTkFrame(self)
        self.button_frame.pack(pady=10, padx=10, fill="x")

        self.add_button = ctk.CTkButton(self.button_frame, text="Add Product", command=self.add_product)
        self.add_button.pack(side="left", padx=5)
        self.edit_button = ctk.CTkButton(self.button_frame, text="Edit Selected", command=self.edit_product)
        self.edit_button.pack(side="left", padx=5)
        self.delete_button = ctk.CTkButton(self.button_frame, text="Delete Selected", command=self.delete_product)
        self.delete_button.pack(side="left", padx=5)

        self.load_products()

    def load_products(self, search_term=None):
        for item in self.tree.get_children():
            self.tree.delete(item)

        conn = get_db_connection()
        if not conn: return
        cursor = conn.cursor(dictionary=True)
        
        query = "SELECT product_id, name, price, stock_quantity FROM Products"
        params = []
        if search_term:
            query += " WHERE name LIKE %s"
            params.append(f"%{search_term}%")
        
        cursor.execute(query, params)
        for row in cursor.fetchall():
            self.tree.insert("", "end", values=(row['product_id'], row['name'], f"{row['price']:.2f}", row['stock_quantity']))
        
        cursor.close()
        conn.close()

    def search_products(self):
        self.load_products(self.search_entry.get())

    def add_product(self):
        dialog = ProductDialog(self)
        self.wait_window(dialog)
        
        if dialog.result:
            res = dialog.result
            conn = get_db_connection()
            if not conn: return
            cursor = conn.cursor()
            try:
                cursor.execute("INSERT INTO Products (name, price, stock_quantity) VALUES (%s, %s, %s)",
                               (res['name'], res['price'], res['stock']))
                conn.commit()
                self.load_products()
            except mysql.connector.Error as err:
                messagebox.showerror("Database Error", f"Failed to add product: {err}", parent=self)
            finally:
                cursor.close()
                conn.close()

    def edit_product(self):
        selected_item = self.tree.focus()
        if not selected_item:
            messagebox.showwarning("Selection Error", "Please select a product to edit.", parent=self)
            return

        item_values = self.tree.item(selected_item, 'values')
        product_info = {
            'product_id': item_values[0],
            'name': item_values[1],
            'price': item_values[2],
            'stock_quantity': item_values[3]
        }
        
        dialog = ProductDialog(self, product_info)
        self.wait_window(dialog)

        if dialog.result:
            res = dialog.result
            conn = get_db_connection()
            if not conn: return
            cursor = conn.cursor()
            try:
                cursor.execute("UPDATE Products SET name=%s, price=%s, stock_quantity=%s WHERE product_id=%s",
                               (res['name'], res['price'], res['stock'], res['id']))
                conn.commit()
                self.load_products()
            except mysql.connector.Error as err:
                messagebox.showerror("Database Error", f"Failed to update product: {err}", parent=self)
            finally:
                cursor.close()
                conn.close()

    def delete_product(self):
        selected_item = self.tree.focus()
        if not selected_item:
            messagebox.showwarning("Selection Error", "Please select a product to delete.", parent=self)
            return

        product_id = self.tree.item(selected_item, 'values')[0]
        
        if messagebox.askyesno("Confirm Delete", "Are you sure you want to delete this product?", parent=self):
            conn = get_db_connection()
            if not conn: return
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT COUNT(*) FROM SaleItems WHERE product_id = %s", (product_id,))
                if cursor.fetchone()[0] > 0:
                    messagebox.showerror("Deletion Error", "Cannot delete product as it is part of a past sale.", parent=self)
                    return
                
                cursor.execute("DELETE FROM Products WHERE product_id = %s", (product_id,))
                conn.commit()
                self.load_products()
            except mysql.connector.Error as err:
                messagebox.showerror("Database Error", f"Failed to delete product: {err}", parent=self)
            finally:
                cursor.close()
                conn.close()

# --- NEW: FLATS MANAGEMENT WINDOW ---
class FlatsWindow(ctk.CTkToplevel):
    def __init__(self, master=None):
        super().__init__(master)
        self.title("Flats Credit Management")
        self.geometry("800x600")
        self.transient(master)
        self.grab_set()

        self.search_frame = ctk.CTkFrame(self)
        self.search_frame.pack(pady=10, padx=10, fill="x")
        
        self.search_entry = ctk.CTkEntry(self.search_frame, placeholder_text="Search by flat number or resident name...")
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.search_button = ctk.CTkButton(self.search_frame, text="Search", command=self.search_flats)
        self.search_button.pack(side="left")

        self.tree_frame = ctk.CTkFrame(self)
        self.tree_frame.pack(pady=10, padx=10, fill="both", expand=True)

        columns = ("id", "flat_number", "resident_name", "credit_balance")
        self.tree = ttk.Treeview(self.tree_frame, columns=columns, show="headings")
        self.tree.heading("id", text="ID")
        self.tree.heading("flat_number", text="Flat Number")
        self.tree.heading("resident_name", text="Resident Name")
        self.tree.heading("credit_balance", text="Credit Balance (₹)")
        self.tree.pack(fill="both", expand=True)
        
        self.tree.column("id", width=50)
        self.tree.column("flat_number", width=150)
        self.tree.column("resident_name", width=250)
        self.tree.column("credit_balance", width=150)

        self.button_frame = ctk.CTkFrame(self)
        self.button_frame.pack(pady=10, padx=10, fill="x")

        self.payment_button = ctk.CTkButton(self.button_frame, text="Record Payment", command=self.record_payment)
        self.payment_button.pack(side="left", padx=5)

        self.load_flats()

    def load_flats(self, search_term=None):
        for item in self.tree.get_children():
            self.tree.delete(item)

        conn = get_db_connection()
        if not conn: return
        cursor = conn.cursor(dictionary=True)
        
        query = "SELECT flat_id, flat_number, resident_name, credit_balance FROM Flats"
        params = []
        if search_term:
            query += " WHERE flat_number LIKE %s OR resident_name LIKE %s"
            params.extend([f"%{search_term}%", f"%{search_term}%"])
        
        query += " ORDER BY credit_balance DESC"
        
        cursor.execute(query, params)
        for row in cursor.fetchall():
            self.tree.insert("", "end", values=(row['flat_id'], row['flat_number'], row['resident_name'], f"{row['credit_balance']:.2f}"))
        
        cursor.close()
        conn.close()

    def search_flats(self):
        self.load_flats(self.search_entry.get())

    def record_payment(self):
        selected_item = self.tree.focus()
        if not selected_item:
            messagebox.showwarning("Selection Error", "Please select a flat to record a payment.", parent=self)
            return

        item_values = self.tree.item(selected_item, 'values')
        flat_id = item_values[0]
        flat_number = item_values[1]
        current_credit = float(item_values[3])

        if current_credit <= 0:
            messagebox.showinfo("No Dues", f"Flat {flat_number} has no outstanding credit.", parent=self)
            return

        dialog = ctk.CTkInputDialog(text=f"Enter payment amount for {flat_number}\n(Current Due: ₹{current_credit:.2f}):", title="Record Payment")
        payment_str = dialog.get_input()

        if payment_str:
            try:
                payment_amount = float(payment_str)
                if payment_amount <= 0:
                    raise ValueError("Payment must be positive.")
                if payment_amount > current_credit:
                    messagebox.showerror("Error", "Payment cannot be more than the outstanding credit.", parent=self)
                    return

                conn = get_db_connection()
                if not conn: return
                cursor = conn.cursor()
                cursor.execute("UPDATE Flats SET credit_balance = credit_balance - %s WHERE flat_id = %s", (payment_amount, flat_id))
                conn.commit()
                cursor.close()
                conn.close()
                
                messagebox.showinfo("Success", f"Payment of ₹{payment_amount:.2f} recorded for flat {flat_number}.", parent=self)
                self.load_flats()

            except (ValueError, TypeError):
                messagebox.showerror("Invalid Input", "Please enter a valid payment amount.", parent=self)

# --- NEW: SALES REPORTS WINDOW ---
class ReportsWindow(ctk.CTkToplevel):
    def __init__(self, master=None):
        super().__init__(master)
        self.title("Sales Reports")
        self.geometry("900x700")
        self.transient(master)
        self.grab_set()

        # --- Top Frame for Controls ---
        self.controls_frame = ctk.CTkFrame(self)
        self.controls_frame.pack(pady=10, padx=10, fill="x")

        self.product_label = ctk.CTkLabel(self.controls_frame, text="Select Product:")
        self.product_label.pack(side="left", padx=(10,5))
        
        self.product_combo = ctk.CTkComboBox(self.controls_frame, width=300, command=self.on_product_select)
        self.product_combo.pack(side="left", padx=5)
        self.load_products_for_combo()

        # --- Main content frame ---
        self.content_frame = ctk.CTkFrame(self)
        self.content_frame.pack(pady=10, padx=10, fill="both", expand=True)
        self.content_frame.grid_columnconfigure(0, weight=1)
        self.content_frame.grid_rowconfigure(1, weight=1)

        # Frame for stats
        self.stats_frame = ctk.CTkFrame(self.content_frame)
        self.stats_frame.grid(row=0, column=0, pady=10, padx=10, sticky="ew")
        
        self.total_sold_label = ctk.CTkLabel(self.stats_frame, text="Total Units Sold (Last 30 Days): N/A", font=("Arial", 14))
        self.total_sold_label.pack(pady=2)
        self.total_revenue_label = ctk.CTkLabel(self.stats_frame, text="Total Revenue (Last 30 Days): N/A", font=("Arial", 14))
        self.total_revenue_label.pack(pady=2)

        # Frame for the graph
        self.graph_frame = ctk.CTkFrame(self.content_frame, fg_color="white")
        self.graph_frame.grid(row=1, column=0, pady=10, padx=10, sticky="nsew")

        self.fig = Figure(figsize=(5, 4), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.graph_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        
        self.show_placeholder_graph()

    def load_products_for_combo(self):
        conn = get_db_connection()
        if not conn: return
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT product_id, name FROM Products ORDER BY name")
        self.products = {row['name']: row['product_id'] for row in cursor.fetchall()}
        self.product_combo.configure(values=list(self.products.keys()))
        cursor.close()
        conn.close()

    def on_product_select(self, selected_product_name):
        product_id = self.products.get(selected_product_name)
        if not product_id: return

        conn = get_db_connection()
        if not conn: return
        cursor = conn.cursor(dictionary=True)
        
        # Query for sales data in the last 30 days
        query = """
            SELECT 
                DATE(s.sale_date) as sale_day, 
                SUM(si.quantity_sold) as total_quantity,
                SUM(si.quantity_sold * si.price_at_sale) as daily_revenue
            FROM Sales s
            JOIN SaleItems si ON s.sale_id = si.sale_id
            WHERE si.product_id = %s AND s.sale_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
            GROUP BY sale_day
            ORDER BY sale_day;
        """
        cursor.execute(query, (product_id,))
        data = cursor.fetchall()
        cursor.close()
        conn.close()

        if not data:
            self.show_placeholder_graph(f"No sales data for '{selected_product_name}' in the last 30 days.")
            self.total_sold_label.configure(text="Total Units Sold (Last 30 Days): 0")
            self.total_revenue_label.configure(text="Total Revenue (Last 30 Days): ₹0.00")
            return

        dates = [row['sale_day'].strftime('%b %d') for row in data]
        quantities = [row['total_quantity'] for row in data]
        
        total_sold = sum(quantities)
        total_revenue = sum(row['daily_revenue'] for row in data)

        self.total_sold_label.configure(text=f"Total Units Sold (Last 30 Days): {total_sold}")
        self.total_revenue_label.configure(text=f"Total Revenue (Last 30 Days): ₹{total_revenue:.2f}")
        
        self.ax.clear()
        self.ax.bar(dates, quantities, color='#3498db')
        self.ax.set_title(f"Daily Sales for {selected_product_name}")
        self.ax.set_ylabel("Quantity Sold")
        self.ax.tick_params(axis='x', rotation=45)
        self.fig.tight_layout()
        self.canvas.draw()

    def show_placeholder_graph(self, text="Select a product to see its sales graph"):
        self.ax.clear()
        self.ax.text(0.5, 0.5, text, ha='center', va='center', fontsize=12, wrap=True)
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        self.canvas.draw()


# --- CHECKOUT DIALOG ---
class CheckoutDialog(ctk.CTkToplevel):
    def __init__(self, master, total_amount):
        super().__init__(master)
        self.title("Checkout")
        self.geometry("400x300")
        self.transient(master)
        self.grab_set()

        self.total_amount = total_amount
        self.result = None

        self.main_label = ctk.CTkLabel(self, text=f"Total Amount: ₹{total_amount:.2f}", font=("Arial", 20))
        self.main_label.pack(pady=20)

        self.payment_method_var = ctk.StringVar(value="Cash/Card")
        self.cash_radio = ctk.CTkRadioButton(self, text="Cash/Card", variable=self.payment_method_var, value="Cash/Card", command=self.toggle_flat_select)
        self.cash_radio.pack(pady=5)
        self.credit_radio = ctk.CTkRadioButton(self, text="Add to Flat Credit", variable=self.payment_method_var, value="Credit", command=self.toggle_flat_select)
        self.credit_radio.pack(pady=5)

        self.flat_combo = ctk.CTkComboBox(self, state="disabled")
        self.flat_combo.pack(pady=10)
        self.load_flats()

        self.confirm_button = ctk.CTkButton(self, text="Confirm Payment", command=self.confirm)
        self.confirm_button.pack(pady=20)

    def load_flats(self):
        conn = get_db_connection()
        if not conn: return
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT flat_id, flat_number, resident_name FROM Flats ORDER BY flat_number")
        self.flats = {f"{row['flat_number']} ({row['resident_name'] or ''})": row['flat_id'] for row in cursor.fetchall()}
        self.flat_combo.configure(values=list(self.flats.keys()))
        cursor.close()
        conn.close()

    def toggle_flat_select(self):
        if self.payment_method_var.get() == "Credit":
            self.flat_combo.configure(state="readonly")
        else:
            self.flat_combo.configure(state="disabled")

    def confirm(self):
        payment_method = self.payment_method_var.get()
        flat_id = None
        if payment_method == "Credit":
            selected_flat_display = self.flat_combo.get()
            if not selected_flat_display:
                messagebox.showerror("Input Error", "Please select a flat for credit payment.", parent=self)
                return
            flat_id = self.flats.get(selected_flat_display)
        
        self.result = {"payment_method": payment_method, "flat_id": flat_id}
        self.destroy()


# --- MAIN APPLICATION ---
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Society StorePro")
        self.geometry("1100x700")

        self.cart = {} # {product_id: {'name': str, 'price': float, 'quantity': int}}
        self.gst_rate = 18.0 # Default, will be loaded from DB

        # --- Main Layout ---
        self.grid_columnconfigure(0, weight=2)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Left Frame (Product Selection)
        self.left_frame = ctk.CTkFrame(self)
        self.left_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        self.left_frame.grid_rowconfigure(2, weight=1) # Make product list frame expand

        # Menu Bar
        self.menu_frame = ctk.CTkFrame(self.left_frame, height=40)
        self.menu_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10,0))
        
        self.inventory_button = ctk.CTkButton(self.menu_frame, text="Manage Inventory", command=self.open_inventory)
        self.inventory_button.pack(side="left", padx=5, pady=5)
        # --- NEW MENU BUTTONS ---
        self.flats_button = ctk.CTkButton(self.menu_frame, text="Manage Flats", command=self.open_flats_window)
        self.flats_button.pack(side="left", padx=5, pady=5)
        self.reports_button = ctk.CTkButton(self.menu_frame, text="Sales Reports", command=self.open_reports_window)
        self.reports_button.pack(side="left", padx=5, pady=5)
        
        self.product_search_entry = ctk.CTkEntry(self.left_frame, placeholder_text="Search and add product by name...")
        self.product_search_entry.grid(row=1, column=0, sticky="ew", padx=10, pady=10)
        self.product_search_entry.bind("<Return>", self.add_product_to_cart_by_name)

        self.product_list_frame = ctk.CTkScrollableFrame(self.left_frame, label_text="Available Products")
        self.product_list_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=10)

        # Right Frame (Cart)
        self.right_frame = ctk.CTkFrame(self, fg_color="#2B2B2B")
        self.right_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")

        self.cart_label = ctk.CTkLabel(self.right_frame, text="Shopping Cart", font=("Arial", 20))
        self.cart_label.pack(pady=10)

        self.cart_display_frame = ctk.CTkScrollableFrame(self.right_frame, label_text="Items")
        self.cart_display_frame.pack(pady=10, padx=10, fill="both", expand=True)

        self.total_frame = ctk.CTkFrame(self.right_frame)
        self.total_frame.pack(pady=10, padx=10, fill="x")
        
        self.subtotal_label = ctk.CTkLabel(self.total_frame, text="Subtotal: ₹0.00")
        self.subtotal_label.pack()
        self.gst_label = ctk.CTkLabel(self.total_frame, text="GST (18%): ₹0.00")
        self.gst_label.pack()
        self.grand_total_label = ctk.CTkLabel(self.total_frame, text="Total: ₹0.00", font=("Arial", 16, "bold"))
        self.grand_total_label.pack()

        self.checkout_button = ctk.CTkButton(self.right_frame, text="Checkout", command=self.checkout)
        self.checkout_button.pack(pady=10, fill="x", padx=10)
        
        self.load_gst_rate()
        self.populate_product_list()

    def populate_product_list(self):
        for widget in self.product_list_frame.winfo_children():
            widget.destroy()

        conn = get_db_connection()
        if not conn: return
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT product_id, name, price, stock_quantity FROM Products WHERE stock_quantity > 0 ORDER BY name")
        
        products = cursor.fetchall()
        cursor.close()
        conn.close()

        if not products:
            info_label = ctk.CTkLabel(self.product_list_frame, 
                                      text="No products in stock.\n\nPlease add products using the\n'Manage Inventory' button.",
                                      font=("Arial", 14), text_color="gray50")
            info_label.pack(pady=50, padx=10, expand=True)
        else:
            for product in products:
                btn_text = f"{product['name']} - ₹{product['price']:.2f} (In Stock: {product['stock_quantity']})"
                btn = ctk.CTkButton(self.product_list_frame, text=btn_text, 
                                    command=lambda p=product: self.add_product_to_cart(p))
                btn.pack(pady=4, padx=5, fill="x")

    def add_product_to_cart_by_name(self, event=None):
        name = self.product_search_entry.get()
        if not name: return
        
        conn = get_db_connection()
        if not conn: return
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM Products WHERE name LIKE %s AND stock_quantity > 0 LIMIT 1", (f"%{name}%",))
        product = cursor.fetchone()
        cursor.close()
        conn.close()

        if product:
            self.add_product_to_cart(product)
            self.product_search_entry.delete(0, 'end')
        else:
            messagebox.showinfo("Not Found", f"No product matching '{name}' found or it is out of stock.")

    def add_product_to_cart(self, product):
        product_id = product['product_id']
        current_stock = product['stock_quantity']
        
        if product_id in self.cart:
            if self.cart[product_id]['quantity'] < current_stock:
                self.cart[product_id]['quantity'] += 1
            else:
                messagebox.showwarning("Stock Limit", f"No more '{product['name']}' in stock.")
        else:
            self.cart[product_id] = {
                'name': product['name'],
                'price': float(product['price']),
                'quantity': 1
            }
        self.update_cart_display()

    def update_cart_display(self):
        for widget in self.cart_display_frame.winfo_children():
            widget.destroy()

        subtotal = 0.0
        for product_id, item in self.cart.items():
            item_total = item['price'] * item['quantity']
            subtotal += item_total
            
            item_frame = ctk.CTkFrame(self.cart_display_frame)
            item_frame.pack(fill="x", pady=5, padx=5)
            
            label_text = f"{item['name']} ({item['quantity']} x ₹{item['price']:.2f}) = ₹{item_total:.2f}"
            ctk.CTkLabel(item_frame, text=label_text).pack(side="left", padx=5, expand=True, anchor="w")
            
            remove_button = ctk.CTkButton(item_frame, text="X", width=30, fg_color="red", hover_color="#C40000",
                                          command=lambda pid=product_id: self.remove_from_cart(pid))
            remove_button.pack(side="right", padx=5)

        gst = subtotal * (self.gst_rate / 100.0)
        grand_total = subtotal + gst

        self.subtotal_label.configure(text=f"Subtotal: ₹{subtotal:.2f}")
        self.gst_label.configure(text=f"GST ({self.gst_rate}%): ₹{gst:.2f}")
        self.grand_total_label.configure(text=f"Total: ₹{grand_total:.2f}")

    def remove_from_cart(self, product_id):
        if product_id in self.cart:
            self.cart[product_id]['quantity'] -= 1
            if self.cart[product_id]['quantity'] == 0:
                del self.cart[product_id]
        self.update_cart_display()

    def load_gst_rate(self):
        conn = get_db_connection()
        if not conn: return
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT current_gst_rate FROM ShopInfo WHERE id = 1")
        result = cursor.fetchone()
        if result:
            self.gst_rate = float(result['current_gst_rate'])
        cursor.close()
        conn.close()

    def checkout(self):
        if not self.cart:
            messagebox.showwarning("Empty Cart", "Cannot checkout with an empty cart.")
            return

        subtotal = sum(item['price'] * item['quantity'] for item in self.cart.values())
        gst = subtotal * (self.gst_rate / 100.0)
        grand_total = subtotal + gst

        dialog = CheckoutDialog(self, grand_total)
        self.wait_window(dialog)
        
        if dialog.result:
            self.process_sale(grand_total, gst, dialog.result)

    def process_sale(self, total_amount, gst_amount, result):
        conn = get_db_connection()
        if not conn: return
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                "INSERT INTO Sales (total_amount, gst_amount, payment_method, flat_id) VALUES (%s, %s, %s, %s)",
                (total_amount, gst_amount, result['payment_method'], result['flat_id'])
            )
            sale_id = cursor.lastrowid

            sale_items_data = []
            for product_id, item in self.cart.items():
                sale_items_data.append((sale_id, product_id, item['quantity'], item['price']))
                cursor.execute(
                    "UPDATE Products SET stock_quantity = stock_quantity - %s WHERE product_id = %s",
                    (item['quantity'], product_id)
                )
            
            cursor.executemany(
                "INSERT INTO SaleItems (sale_id, product_id, quantity_sold, price_at_sale) VALUES (%s, %s, %s, %s)",
                sale_items_data
            )

            if result['payment_method'] == 'Credit' and result['flat_id']:
                cursor.execute(
                    "UPDATE Flats SET credit_balance = credit_balance + %s WHERE flat_id = %s",
                    (total_amount, result['flat_id'])
                )

            conn.commit()
            messagebox.showinfo("Success", "Sale recorded successfully!")
            self.cart.clear()
            self.update_cart_display()
            self.populate_product_list()

        except mysql.connector.Error as err:
            conn.rollback()
            messagebox.showerror("Sale Error", f"An error occurred: {err}")
        finally:
            cursor.close()
            conn.close()

    def open_inventory(self):
        win = InventoryWindow(self)
        win.protocol("WM_DELETE_WINDOW", lambda: (self.populate_product_list(), win.destroy()))

    # --- NEW: Functions to open the new windows ---
    def open_flats_window(self):
        FlatsWindow(self)

    def open_reports_window(self):
        ReportsWindow(self)


if __name__ == "__main__":
    setup_database()
    
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    
    app = App()
    app.mainloop()
