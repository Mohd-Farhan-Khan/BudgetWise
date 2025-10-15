"""
Enhanced Indian Transaction Dataset Generator for BudgetWise AI
"""

import pandas as pd
import random
from datetime import datetime, timedelta
import numpy as np
import calendar
import os 

def get_user_input():
    """Get user preferences for dataset generation"""
    print("\n" + "="*50)
    print("💰 BudgetWise AI - Transaction Dataset Generator")
    print("="*50)
    
    # Choose generation type
    print("\nSelect dataset type:")
    print("1. Last N months from today")
    print("2. Specific months")
    print("3. Custom date range")
    
    choice = input("\nEnter your choice (1-3): ").strip()
    
    if choice == '1':
        months = int(input("Enter number of months (1-12): "))
        end_date = datetime.now()
        start_date = end_date - timedelta(days=months*30)
        return start_date, end_date, None
    
    elif choice == '2':
        print("\nAvailable months:")
        months_list = ['January', 'February', 'March', 'April', 'May', 'June',
                      'July', 'August', 'September', 'October', 'November', 'December']
        for i, month in enumerate(months_list, 1):
            print(f"{i}. {month}")
        
        selected_months = input("\nEnter month numbers separated by comma (e.g., 1,2,3): ").strip()
        selected_months = [int(m.strip()) for m in selected_months.split(',')]
        
        year = input("Enter year (e.g., 2024): ").strip()
        year = int(year) if year else datetime.now().year
        
        return None, None, {'months': selected_months, 'year': year}
    
    else:
        start = input("Enter start date (YYYY-MM-DD): ")
        end = input("Enter end date (YYYY-MM-DD): ")
        start_date = datetime.strptime(start, '%Y-%m-%d')
        end_date = datetime.strptime(end, '%Y-%m-%d')
        return start_date, end_date, None

def calculate_salary_range(monthly_expense):
    """Calculate appropriate salary based on expense patterns"""
    # Assuming savings rate of 20-30%
    return int(monthly_expense * 1.3), int(monthly_expense * 1.5)

def generate_transactions_enhanced(start_date=None, end_date=None, specific_months=None):
    """Generate realistic transaction data with salary"""
    
    # Transaction templates
    transaction_templates = {
        'Food & Dining': [
            ('Swiggy Order', (150, 500)),
            ('Zomato Delivery', (200, 600)),
            ('Dominos Pizza', (400, 800)),
            ('McDonald\'s', (200, 400)),
            ('KFC', (300, 600)),
            ('Burger King', (250, 450)),
            ('Subway', (200, 400)),
            ('Starbucks Coffee', (250, 500)),
            ('Cafe Coffee Day', (150, 350)),
            ('Local Restaurant', (300, 1500)),
            ('Haldiram\'s', (150, 400)),
            ('Barbeque Nation', (1200, 2000)),
            ('Pizza Hut', (500, 900)),
            ('Biryani Restaurant', (400, 800)),
            ('South Indian Restaurant', (200, 500)),
            ('Chinese Restaurant', (500, 1200)),
            ('Street Food', (50, 200)),
            ('Bakery Items', (100, 300)),
            ('Ice Cream Parlor', (100, 300)),
            ('Tea/Coffee Shop', (50, 150))
        ],
        'Transportation': [
            ('Uber Ride', (80, 400)),
            ('Ola Cab', (75, 350)),
            ('Rapido Bike', (40, 150)),
            ('Auto Rickshaw', (30, 200)),
            ('Metro Recharge', (100, 500)),
            ('Bus Ticket', (20, 100)),
            ('Petrol Pump', (500, 3000)),
            ('Train Booking IRCTC', (200, 2000)),
            ('Flight Booking', (2000, 10000)),
            ('Parking Fees', (20, 100)),
            ('Toll Charges', (50, 200)),
            ('Car Service', (1000, 5000)),
            ('Bike Service', (500, 2000))
        ],
        'Shopping': [
            ('Amazon Shopping', (500, 5000)),
            ('Flipkart Purchase', (400, 4000)),
            ('Myntra Fashion', (800, 3000)),
            ('Ajio Clothing', (600, 2500)),
            ('Nykaa Beauty', (500, 2000)),
            ('Decathlon Sports', (1000, 4000)),
            ('Croma Electronics', (1000, 15000)),
            ('Reliance Digital', (1000, 10000)),
            ('Lifestyle Store', (1500, 5000)),
            ('Westside Shopping', (1000, 3000)),
            ('Max Fashion', (800, 2000)),
            ('Big Bazaar', (1500, 4000)),
            ('D-Mart Shopping', (2000, 5000)),
            ('Local Market', (200, 1000))
        ],
        'Groceries': [
            ('BigBasket Order', (500, 2500)),
            ('Blinkit Delivery', (200, 800)),
            ('Zepto Quick', (150, 600)),
            ('Swiggy Instamart', (200, 700)),
            ('Dunzo Daily', (150, 500)),
            ('Reliance Fresh', (300, 1500)),
            ('More Supermarket', (400, 2000)),
            ('Spencer\'s Retail', (500, 2500)),
            ('Star Bazaar', (600, 3000)),
            ('Nature\'s Basket', (800, 3000)),
            ('Local Kirana Store', (100, 500)),
            ('Vegetable Vendor', (100, 400)),
            ('Milk Dairy', (50, 200)),
            ('Fruit Shop', (200, 600))
        ],
        'Entertainment': [
            ('Netflix Subscription', (199, 649)),
            ('Amazon Prime', (179, 179)),
            ('Disney+ Hotstar', (299, 1499)),
            ('Spotify Premium', (119, 119)),
            ('YouTube Premium', (139, 189)),
            ('PVR Movie Tickets', (300, 1500)),
            ('INOX Cinema', (300, 1200)),
            ('BookMyShow Events', (500, 3000)),
            ('Gaming Purchase', (100, 2000)),
            ('Concert Tickets', (1000, 5000)),
            ('Amusement Park', (500, 2000)),
            ('Bowling Alley', (300, 800))
        ],
        'Utilities': [
            ('Electricity Bill', (800, 3000)),
            ('Water Bill', (200, 600)),
            ('Internet Bill', (600, 1500)),
            ('Mobile Recharge', (200, 800)),
            ('DTH Recharge', (300, 600)),
            ('LPG Gas Cylinder', (900, 1100)),
            ('Maintenance Charges', (2000, 5000)),
            ('WiFi Bill', (500, 1200))
        ],
        'Healthcare': [
            ('Apollo Pharmacy', (200, 1500)),
            ('1mg Medicine Order', (300, 2000)),
            ('Doctor Consultation', (500, 1500)),
            ('Lab Tests', (500, 3000)),
            ('Gym Membership', (1000, 3000)),
            ('Health Insurance', (1000, 5000)),
            ('Dental Checkup', (1000, 3000)),
            ('Eye Checkup', (500, 2000))
        ],
        'Education': [
            ('Udemy Course', (400, 2000)),
            ('Coursera Subscription', (399, 500)),
            ('Book Purchase', (200, 1000)),
            ('Online Course', (500, 5000)),
            ('Skill Development', (1000, 3000)),
            ('Certification Exam', (2000, 10000))
        ],
        'Investment': [
            ('Mutual Fund SIP', (500, 10000)),
            ('Stock Purchase', (1000, 20000)),
            ('Gold Investment', (1000, 10000)),
            ('FD Deposit', (5000, 50000)),
            ('PPF Contribution', (500, 12500))
        ],
        'Transfer': [
            ('Google Pay Transfer', (100, 5000)),
            ('PhonePe Payment', (100, 3000)),
            ('Paytm Transfer', (100, 2000)),
            ('Bank Transfer', (500, 10000)),
            ('Friend Payment', (100, 2000)),
            ('Family Support', (1000, 10000)),
            ('Rent Payment', (10000, 40000)),
            ('EMI Payment', (5000, 30000))
        ]
    }
    
    transactions = []
    
    # Determine date ranges based on input
    if specific_months:
        date_ranges = []
        for month in specific_months['months']:
            month_start = datetime(specific_months['year'], month, 1)
            month_end = datetime(specific_months['year'], month, 
                                calendar.monthrange(specific_months['year'], month)[1])
            date_ranges.append((month_start, month_end))
    else:
        # Create monthly ranges
        date_ranges = []
        current = start_date
        while current <= end_date:
            month_start = current.replace(day=1)
            month_end = datetime(current.year, current.month, 
                               calendar.monthrange(current.year, current.month)[1])
            if month_end > end_date:
                month_end = end_date
            date_ranges.append((month_start, min(month_end, end_date)))
            
            # Move to next month
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1)
            else:
                current = current.replace(month=current.month + 1)
    
    # Generate transactions for each month
    for month_start, month_end in date_ranges:
        monthly_expenses = 0
        month_transactions = []
        
        # Generate daily transactions
        current_date = month_start
        while current_date <= month_end:
            # Number of transactions per day
            if current_date.weekday() in [5, 6]:  # Weekend
                num_transactions = random.randint(3, 10)
            else:  # Weekday
                num_transactions = random.randint(2, 7)
            
            # Category weights
            category_weights = {
                'Food & Dining': 0.30,
                'Transportation': 0.20,
                'Groceries': 0.15,
                'Shopping': 0.10,
                'Utilities': 0.08,
                'Entertainment': 0.07,
                'Healthcare': 0.05,
                'Transfer': 0.03,
                'Education': 0.01,
                'Investment': 0.01
            }
            
            daily_categories = random.choices(
                list(category_weights.keys()),
                weights=list(category_weights.values()),
                k=num_transactions
            )
            
            for category in daily_categories:
                template = random.choice(transaction_templates[category])
                description = template[0]
                amount_range = template[1]
                
                # Generate amount
                base_amount = random.randint(amount_range[0], amount_range[1])
                amount = round(base_amount / 10) * 10
                
                # Track monthly expenses
                monthly_expenses += amount
                
                # Add time
                hour = random.randint(6, 23)
                minute = random.randint(0, 59)
                transaction_datetime = current_date.replace(hour=hour, minute=minute)
                
                month_transactions.append({
                    'Date': transaction_datetime.strftime('%Y-%m-%d'),
                    'Time': transaction_datetime.strftime('%H:%M'),
                    'Description': description,
                    'Amount': -amount,  # Expenses are negative
                    'Category': category,
                    'Type': 'Expense',
                    'Payment Mode': random.choice(['UPI', 'Card', 'Cash', 'Net Banking']),
                    'Transaction ID': f"TXN{current_date.strftime('%Y%m%d')}{len(transactions):04d}"
                })
            
            current_date += timedelta(days=1)
        
        # Add salary transaction (once per month on 1st)
        salary_min, salary_max = calculate_salary_range(monthly_expenses)
        salary_amount = random.randint(salary_min, salary_max)
        salary_amount = round(salary_amount / 1000) * 1000  # Round to nearest 1000
        
        salary_date = month_start.replace(day=1, hour=10, minute=30)
        month_transactions.append({
            'Date': salary_date.strftime('%Y-%m-%d'),
            'Time': salary_date.strftime('%H:%M'),
            'Description': 'Salary Credited',
            'Amount': salary_amount,  # Income is positive
            'Category': 'Income',
            'Type': 'Income',
            'Payment Mode': 'Bank Transfer',
            'Transaction ID': f"SAL{salary_date.strftime('%Y%m%d')}001"
        })
        
        transactions.extend(month_transactions)
    
    # Create DataFrame and sort
    df = pd.DataFrame(transactions)
    df = df.sort_values(['Date', 'Time'])
    df = df.reset_index(drop=True)
    
    return df

def save_dataset(df, filename=None):
    """Save dataset to Desktop with appropriate filename"""
    desktop_path = r"C:\Users\tirth\OneDrive\Desktop"
    
    if filename is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"transactions_{timestamp}.csv"
    
    full_path = os.path.join(desktop_path, filename)
    df.to_csv(full_path, index=False)
    return full_path

def print_statistics(df):
    """Print detailed statistics about the dataset"""
    print("\n" + "="*60)
    print("📊 Dataset Statistics")
    print("="*60)
    
    print(f"\n📅 Date Range: {df['Date'].min()} to {df['Date'].max()}")
    print(f"📝 Total Transactions: {len(df)}")
    
    # Calculate totals
    total_income = df[df['Amount'] > 0]['Amount'].sum()
    total_expenses = abs(df[df['Amount'] < 0]['Amount'].sum())
    net_balance = total_income - total_expenses
    
    print(f"\n💰 Financial Summary:")
    print(f"   Total Income: ₹{total_income:,.2f}")
    print(f"   Total Expenses: ₹{total_expenses:,.2f}")
    print(f"   Net Balance: ₹{net_balance:,.2f}")
    print(f"   Average Daily Spending: ₹{total_expenses / df['Date'].nunique():,.2f}")
    
    # Category breakdown
    print(f"\n📂 Category Breakdown:")
    category_totals = df[df['Type'] == 'Expense'].groupby('Category')['Amount'].sum()
    category_totals = abs(category_totals).sort_values(ascending=False)
    
    for category, amount in category_totals.items():
        percentage = (amount / total_expenses) * 100
        print(f"   {category}: ₹{amount:,.2f} ({percentage:.1f}%)")
    
    # Monthly breakdown
    df['Month'] = pd.to_datetime(df['Date']).dt.to_period('M')
    monthly_income = df[df['Type'] == 'Income'].groupby('Month')['Amount'].sum()
    monthly_expenses = abs(df[df['Type'] == 'Expense'].groupby('Month')['Amount'].sum())
    
    print(f"\n📅 Monthly Breakdown:")
    for month in df['Month'].unique():
        income = monthly_income.get(month, 0)
        expense = monthly_expenses.get(month, 0)
        print(f"   {month}: Income: ₹{income:,.2f} | Expenses: ₹{expense:,.2f}")

# Main execution
if __name__ == "__main__":
    try:
        # Get user input
        start_date, end_date, specific_months = get_user_input()
        
        print("\n⏳ Generating transactions...")
        
        # Generate dataset
        df = generate_transactions_enhanced(start_date, end_date, specific_months)
        
        # Save dataset
        print("\n💾 Saving dataset...")
        filename = save_dataset(df)
        print(f"✅ Dataset saved as: {filename}")
        
        # Print statistics
        print_statistics(df)
        
        # Ask if user wants to generate another dataset
        another = input("\n\nGenerate another dataset? (y/n): ").strip().lower()
        if another == 'y':
            exec(open(__file__).read())
            
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        print("Please try again with valid inputs.")