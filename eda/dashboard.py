import pandas as pd
import numpy as np
import tkinter as tk
from tkinter import ttk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import warnings
warnings.filterwarnings('ignore') # Ignore matplotlib warnings for clean output

# ==========================================
# 0. Load and Clean Your Data Here
# ==========================================
# Replace 'your_data.csv' with your actual dataset file path
print("Loading data...")
df = pd.read_csv('bayut_all_locations_transactions.csv') 

# --- Basic Data Cleaning (matches your previous notebook logic) ---
df['price(EAD)'] = df['price(EAD)'].astype(str).str.replace(',', '').str.strip()
df['price(EAD)'] = pd.to_numeric(df['price(EAD)'], errors='coerce')

df['built_up(sqft)'] = df['built_up(sqft)'].astype(str).str.replace(',', '').str.strip()
df['built_up(sqft)'] = pd.to_numeric(df['built_up(sqft)'], errors='coerce')

df['date'] = pd.to_datetime(df['date'], format='mixed', dayfirst=True, errors='coerce')
df['price_per_sqft_calc'] = df['price(EAD)'] / df['built_up(sqft)']

# Drop rows missing crucial graph data
df = df.dropna(subset=['main_location', 'sub_location', 'type', 'date', 'price_per_sqft_calc'])

# ==========================================
# 1. The Dashboard Application Class
# ==========================================
class RealEstateDashboard:
    def __init__(self, root, data):
        self.root = root
        self.root.title("📈 Real Estate Price Trends Dashboard")
        self.root.geometry("1100x750") # Width x Height of the floating window
        
        self.df = data
        
        # --- Top Control Panel (Dropdowns) ---
        control_frame = ttk.Frame(root, padding=15)
        control_frame.pack(side=tk.TOP, fill=tk.X)
        
        # 1. Location Dropdown
        ttk.Label(control_frame, text="Location:", font=('Arial', 11, 'bold')).pack(side=tk.LEFT, padx=5)
        self.loc_var = tk.StringVar()
        self.loc_cb = ttk.Combobox(control_frame, textvariable=self.loc_var, state="readonly", width=30)
        
        locs = sorted([str(loc) for loc in self.df['main_location'].unique()])
        self.loc_cb['values'] = locs
        if locs:
            self.loc_cb.set(locs[0]) # Set default
        self.loc_cb.pack(side=tk.LEFT, padx=5)
        self.loc_cb.bind("<<ComboboxSelected>>", self.update_sub_locations)
        # 2. Sub-Location Dropdown
        ttk.Label(control_frame, text="Sub-Loc:", font=('Arial', 11, 'bold')).pack(side=tk.LEFT, padx=(20, 5))
        self.sub_var = tk.StringVar()
        self.sub_cb = ttk.Combobox(control_frame, textvariable=self.sub_var, state="readonly", width=25)
        
        # Populate sub-locations initially based on the default main location
        initial_subs = ['All'] + sorted([str(s) for s in self.df[self.df['main_location'] == locs[0]]['sub_location'].dropna().unique()]) if locs else ['All']
        self.sub_cb['values'] = initial_subs
        self.sub_cb.set('All')
        self.sub_cb.pack(side=tk.LEFT, padx=5)
        self.sub_cb.bind("<<ComboboxSelected>>", self.update_buildings)

        # 3. Building Dropdown
        ttk.Label(control_frame, text="Building:", font=('Arial', 11, 'bold')).pack(side=tk.LEFT, padx=(20, 5))
        self.build_var = tk.StringVar()
        self.build_cb = ttk.Combobox(control_frame, textvariable=self.build_var, state="readonly", width=25)
        
        # Populate buildings based on initial sub location
        initial_builds = ['All']
        if initial_subs and initial_subs[0] != 'All':
            b_list = self.df[(self.df['main_location'] == locs[0]) & (self.df['sub_location'] == initial_subs[0])]['building_project'].dropna().unique()
            initial_builds += sorted([str(b) for b in b_list])
        
        self.build_cb['values'] = initial_builds
        self.build_cb.set('All')
        self.build_cb.pack(side=tk.LEFT, padx=5)
        self.build_cb.bind("<<ComboboxSelected>>", self.update_plot)

        # 3. Type Dropdown
        ttk.Label(control_frame, text="Property Type:", font=('Arial', 11, 'bold')).pack(side=tk.LEFT, padx=(20, 5))
        self.type_var = tk.StringVar()
        self.type_cb = ttk.Combobox(control_frame, textvariable=self.type_var, state="readonly", width=20)
        
        types = ['All'] + sorted([str(t) for t in self.df['type'].unique()])
        self.type_cb['values'] = types
        self.type_cb.set('All') # Set default
        self.type_cb.pack(side=tk.LEFT, padx=5)
        self.type_cb.bind("<<ComboboxSelected>>", self.update_plot)
        
        # 3. Off-Plan Dropdown
        if 'is_off_plan?' in self.df.columns:
            ttk.Label(control_frame, text="Off-Plan:", font=('Arial', 11, 'bold')).pack(side=tk.LEFT, padx=(20, 5))
            self.offplan_var = tk.StringVar()
            self.offplan_cb = ttk.Combobox(control_frame, textvariable=self.offplan_var, state="readonly", width=10)
            
            offplan_vals = ['All'] + sorted([str(v) for v in self.df['is_off_plan?'].dropna().unique()])
            self.offplan_cb['values'] = offplan_vals
            self.offplan_cb.set('All')
            self.offplan_cb.pack(side=tk.LEFT, padx=5)
            self.offplan_cb.bind("<<ComboboxSelected>>", self.update_plot)
            
        # 4. Vacant Dropdown
        if 'is_Vacant_at_time_of_sale?' in self.df.columns:
            ttk.Label(control_frame, text="Vacant:", font=('Arial', 11, 'bold')).pack(side=tk.LEFT, padx=(20, 5))
            self.vacant_var = tk.StringVar()
            self.vacant_cb = ttk.Combobox(control_frame, textvariable=self.vacant_var, state="readonly", width=10)
            
            vacant_vals = ['All'] + sorted([str(v) for v in self.df['is_Vacant_at_time_of_sale?'].dropna().unique()])
            self.vacant_cb['values'] = vacant_vals
            self.vacant_cb.set('All')
            self.vacant_cb.pack(side=tk.LEFT, padx=5)
            self.vacant_cb.bind("<<ComboboxSelected>>", self.update_plot)
        
        # --- Plotting Area ---
        self.figure, self.ax = plt.subplots(figsize=(10, 6))
        self.canvas = FigureCanvasTkAgg(self.figure, master=self.root)
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        # Draw the initial plot
        self.update_plot()
        
    def update_buildings(self, event=None):
        """Update Building options when Sub-Loc changes."""
        loc = self.loc_var.get()
        subloc = self.sub_var.get()
        
        if subloc == 'All':
            # Too many buildings, keep it simple
            self.build_cb['values'] = ['All']
            self.build_cb.set('All')
        else:
            builds = self.df[(self.df['main_location'] == loc) & (self.df['sub_location'] == subloc)]['building_project'].dropna().unique()
            new_options = ['All'] + sorted([str(b) for b in builds])
            self.build_cb['values'] = new_options
            self.build_cb.set('All')
            
        self.update_plot()
        
    def update_sub_locations(self, event=None):
        """Update Sub-Loc options when Main Location changes."""
        loc = self.loc_var.get()
        subs = self.df[self.df['main_location'] == loc]['sub_location'].dropna().unique()
        new_options = ['All'] + sorted([str(s) for s in subs])
        
        self.sub_cb['values'] = new_options
        self.sub_cb.set('All')
        self.update_buildings() # Trigger the building update cascade
        
    def update_plot(self, event=None):
        self.ax.clear() # Clear old graph
        
        loc = self.loc_var.get()
        subloc = getattr(self, 'sub_var', tk.StringVar()).get()
        build = getattr(self, 'build_var', tk.StringVar()).get()
        ptype = getattr(self, 'type_var', tk.StringVar()).get()
        
        if not loc:
            return
            
        # Filter dataframe by selected Main Location
        subset = self.df[self.df['main_location'] == loc].copy()
        
        # Then filter by Sub Location (if not All)
        if subloc and subloc != 'All':
            subset = subset[subset['sub_location'] == subloc]
            
        # Then filter by Building (if not All)
        if build and build != 'All':
            subset = subset[subset['building_project'] == build]
            
        # Then filter by Type
        if ptype and ptype != 'All':
            subset = subset[subset['type'] == ptype]
            
        # Then filter by Off-Plan
        if hasattr(self, 'offplan_var') and self.offplan_var.get() != 'All':
            subset = subset[subset['is_off_plan?'].astype(str) == self.offplan_var.get()]
            
        # Then filter by Vacant
        if hasattr(self, 'vacant_var') and self.vacant_var.get() != 'All':
            subset = subset[subset['is_Vacant_at_time_of_sale?'].astype(str) == self.vacant_var.get()]
            
        if subset.empty:
            self.ax.text(0.5, 0.5, "⚠️ No data available for this selection", 
                         ha='center', va='center', fontsize=14, color='red')
            self.canvas.draw()
            return
            
        # Removed median resampling to plot original individual transactions
        # Sort values by date so the line plot connects points chronologically
        subset = subset.sort_values(by='date')
        
        # Determine whether to group by sub_location or building_project based on what's selected
        if build and build != 'All':
            # If a specific building is chosen, plot lines for different types of rooms/configurations if they exist
            # but usually it's just one line
            color_entities = [build]
            entity_col = 'building_project'
            legend_title = "Building Project"
            subset['building_project'] = subset['building_project'].fillna(build)
            
        elif subloc != 'All':
            # If a specific sub-location is chosen, plot by building_project
            # Fill NaN buildings with the sub_location name so they don't get excluded from the legend
            subset['building_project'] = subset['building_project'].fillna('Independent / No Building Data')
            color_entities = sorted(subset['building_project'].unique())
            entity_col = 'building_project'
            legend_title = "Building Projects"
        else:
            # If subloc is ALL, plot lines by Sub-Location
            color_entities = sorted(subset['sub_location'].unique())
            entity_col = 'sub_location'
            legend_title = "Sub-Locations"
        
        for entity in color_entities:
            entity_data = subset[subset[entity_col] == entity]
            if entity_data.empty: continue
            
            # Plot individual transaction price vs date
            self.ax.plot(entity_data['date'], entity_data['price(EAD)'], marker='o', 
                         markersize=4, linestyle='-', linewidth=1.5, alpha=0.7, label=entity)
                
        # Format the graph
        display_sub = f" ({subloc})" if subloc != 'All' else ""
        display_build = f" > {build}" if build and build != 'All' else ""
        self.ax.set_title(f"{loc}{display_sub}{display_build} | {ptype}", fontsize=16, fontweight='bold', pad=15)
        self.ax.set_xlabel("Date", fontsize=12, fontweight='bold')
        self.ax.set_ylabel("Total Price (AED)", fontsize=12, fontweight='bold')
        self.ax.grid(True, linestyle='--', alpha=0.6)
        self.ax.tick_params(axis='x', rotation=45)
        
        # Add legend outside the plot so it doesn't cover the lines
        if len(color_entities) > 0:
            ncol = 2 if len(color_entities) > 15 else 1 # Split into 2 columns if there are a ton of locations
            self.ax.legend(title=legend_title, bbox_to_anchor=(1.02, 1), loc='upper left', 
                           ncol=ncol, fontsize='small', title_fontsize='medium')
            
        # Adjust layout so the legend fits inside the window
        self.figure.tight_layout()
        self.canvas.draw()

# ==========================================
# 2. Run the Application
# ==========================================
if __name__ == "__main__":
    print("Launching floating window dashboard...")
    # Initialize the Tkinter window
    root = tk.Tk()
    
    # Optional: Set a nice theme if available
    try:
        root.tk.call("source", "azure.tcl")
        root.tk.call("set_theme", "light")
    except:
        pass # Fallback to standard theme
        
    app = RealEstateDashboard(root, df)
    
    # Start the event loop (this keeps the window open)
    root.mainloop()
